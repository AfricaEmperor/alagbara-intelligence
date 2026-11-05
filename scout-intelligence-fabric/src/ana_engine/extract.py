"""ANA event extraction: poster/video text -> schema-validated FieldClaims. No invention.

Every claim is DERIVED (rule-based reading of text) or UNVERIFIED (text typed by an operator);
never OBSERVED. Missing fields are listed in `unknown`; weekday-only dates stay unknown.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from radar_contracts import FieldClaim

EXTRACTION_VERSION = "ana-extract-1.0.0"

MONTHS = {
    "janvier": 1, "janv": 1, "january": 1, "jan": 1, "fevrier": 2, "fevr": 2, "fev": 2, "february": 2,
    "feb": 2, "mars": 3, "march": 3, "mar": 3, "avril": 4, "april": 4, "avr": 4, "apr": 4, "mai": 5,
    "may": 5, "juin": 6, "june": 6, "jun": 6, "juillet": 7, "juil": 7, "july": 7, "jul": 7,
    "aout": 8, "august": 8, "aug": 8, "septembre": 9, "sept": 9, "sep": 9, "september": 9,
    "octobre": 10, "oct": 10, "october": 10, "novembre": 11, "nov": 11, "november": 11,
    "decembre": 12, "dec": 12, "december": 12,
}
WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DISTRICTS = ("haie vive", "fidjrosse", "akpakpa", "cadjehoun", "ganhi", "zogbo", "gbegamey",
             "jonquet", "sainte rita", "ste rita", "agla", "menontin", "godomey", "calavi",
             "cotonou centre", "placodji", "vodje", "togoudo", "saint michel", "st michel")
CATEGORIES = {
    "afrobeats": "club_night", "amapiano": "club_night", "soiree": "club_night", "night": "club_night",
    "clubbing": "club_night", "dj set": "club_night", "concert": "concert", "live": "concert",
    "showcase": "concert", "festival": "festival", "brunch": "brunch", "karaoke": "karaoke",
    "after work": "afterwork", "afterwork": "afterwork", "pool party": "pool_party",
    "stand-up": "comedy", "comedy": "comedy",
}
VENUE_TRIGGERS = r"(?:lieu|venue|location|adresse|@|au|chez|at)\s*[:\-]?\s*"
ORG_TRIGGERS = r"\b(?:organis[ée]e?\s+par|pr[ée]sent[ée]e?\s+par|presented\s+by|une\s+production|organi[sz]ed\s+by)\b"
PROMO_TRIGGERS = r"(?:promoteur|promoter|promo)\s*[:\-]?"


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


@dataclass
class Extraction:
    claims: list[FieldClaim] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    partial_date: dict | None = None  # e.g. {"day": 14, "month": 11} when year is absent


def _claim(name: str, value: str, state: str, ev: str, snippet: str, method: str) -> FieldClaim:
    return FieldClaim(name, value, state, (ev,), snippet.strip()[:200], method)


def extract_event(text: str, observation_id: str, text_state: str = "derived",
                  text_method: str = "rule") -> Extraction:
    """text_state is the provenance of the *text* (derived OCR vs unverified sidecar); claims inherit
    the weaker of that and 'derived'."""
    state = "unverified" if text_state == "unverified" else "derived"
    method = f"rule:{text_method}"
    out = Extraction()
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    folded = [fold(ln) for ln in lines]
    joined = fold(" ".join(lines))

    # ---- date -------------------------------------------------------------------------------
    date_val = None
    for ln, fl in zip(lines, folded):
        m = re.search(r"\b(\d{1,2})\s*(?:er)?\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(20\d{2})\b", fl)  # dd/mm/yyyy
        if m:
            d, mo, y = int(m[1]), int(m[2]), int(m[3])
            date_val = (y, mo, d, ln)
            break
        m = re.search(r"\b(\d{1,2})\s*(?:er)?\s+([a-z]{3,9})\.?\s*(20\d{2})?\b", fl)
        if m and m[2] in MONTHS:
            d, mo = int(m[1]), MONTHS[m[2]]
            if m[3]:
                date_val = (int(m[3]), mo, d, ln)
                break
            out.partial_date = {"day": d, "month": mo}
            out.notes.append(f"date has day+month ({d:02d}/{mo:02d}) but no year; calendar date not inferred")
    if date_val and 1 <= date_val[1] <= 12 and 1 <= date_val[2] <= 31:
        y, mo, d, snip = date_val
        out.claims.append(_claim("start_date", f"{y:04d}-{mo:02d}-{d:02d}", state, observation_id, snip, method))
    else:
        out.unknown.append("start_date")
        wd = next((w for w in WEEKDAYS if re.search(rf"\b{w}\b", joined)), None)
        if wd:
            out.notes.append(f"weekday '{wd}' stated without a calendar date; date left unknown")

    # ---- times ------------------------------------------------------------------------------
    t_re = r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?"
    rng = re.search(rf"(?:de|from)?\s*{t_re}\s*(?:a|à|to|-|–)\s*{t_re}", joined.replace("à", "a"))
    start_t = end_t = None
    snippet_t = ""
    if rng and 0 <= int(rng[1]) <= 23 and 0 <= int(rng[3]) <= 23:
        start_t = f"{int(rng[1]):02d}:{int(rng[2] or 0):02d}"
        end_t = f"{int(rng[3]):02d}:{int(rng[4] or 0):02d}"
        snippet_t = rng[0]
    else:
        m = re.search(rf"(?:a partir de|des|from|doors|portes|@|a)\s*{t_re}\b", joined) or \
            re.search(rf"\b{t_re}\b", joined)
        if m and 0 <= int(m[1]) <= 23 and not re.search(r"\d{1,2}\s*h\s*\d{2}\s*(?:ans)", m[0]):
            start_t = f"{int(m[1]):02d}:{int(m[2] or 0):02d}"
            snippet_t = m[0]
    if start_t:
        out.claims.append(_claim("start_time", start_t, state, observation_id, snippet_t, method))
    else:
        out.unknown.append("start_time")
    if end_t:
        out.claims.append(_claim("end_time", end_t, state, observation_id, snippet_t, method))
    else:
        out.unknown.append("end_time")

    # ---- district / venue -----------------------------------------------------------------
    district = next((d for d in DISTRICTS if d in joined), None)
    if district:
        out.claims.append(_claim("district", district.title(), state, observation_id, district, method))
    else:
        out.unknown.append("district")

    venue_val = venue_snip = None
    for ln in lines:
        m = re.search(VENUE_TRIGGERS + r"([A-ZÀ-Ý0-9][^\n,|•·–-]{2,50})", ln, re.IGNORECASE)
        if m:
            cand = re.split(r"\b(?:\d{1,2}\s*h|le\s+\d|à partir)\b", m[1].strip(), flags=re.IGNORECASE)[0].strip(" .:-")
            if cand and fold(cand) not in WEEKDAYS and not re.fullmatch(r"[\d\s/h:.]+", cand):
                venue_val, venue_snip = cand, ln
                break
    if venue_val and district and fold(venue_val).endswith(district):  # "Club X Haie Vive" -> "Club X"
        venue_val = venue_val[: len(venue_val) - len(district)].strip(" ,-")
    if venue_val:
        out.claims.append(_claim("venue", venue_val, state, observation_id, venue_snip, method))
    else:
        out.unknown.append("venue")

    # ---- organizer / promoter (kept separate from performers) -----------------------------
    org = None
    for ln in lines:
        m = re.search(ORG_TRIGGERS + r"\s*[:\-]?\s*([A-Za-zÀ-ÿ0-9&' ._]{2,40})", ln, re.IGNORECASE)
        if m and not re.match(r"\s*dj\b", m[1], re.IGNORECASE):
            org = (m[1].strip(" .-"), ln)
            break
    if org:
        out.claims.append(_claim("organizer", org[0], state, observation_id, org[1], method))
    else:
        out.unknown.append("organizer")
    for ln in lines:
        m = re.search(PROMO_TRIGGERS + r"\s*([A-Za-zÀ-ÿ0-9&' ._]{2,40})", ln, re.IGNORECASE)
        if m:
            out.claims.append(_claim("promoter", m[1].strip(" .-"), state, observation_id, ln, method))
            break

    # ---- performers: DJs and artists ------------------------------------------------------
    seen: set[str] = set()
    for ln in lines:
        for m in re.finditer(r"\bDJ\s+([A-Za-z0-9][A-Za-z0-9_.'-]*(?:\s+[A-Z][A-Za-z0-9_.'-]*)?)", ln):
            name = "DJ " + m[1].strip()
            if fold(name) not in seen:
                seen.add(fold(name))
                out.claims.append(_claim("performer", name, state, observation_id, ln, method + ":dj"))
        m = re.search(r"\b(?i:feat\.?|ft\.?|live|avec|with|special guest|invit[ée]\s+sp[ée]cial)\s*[:\-]?\s*"
                      r"([A-ZÀ-Ý][\wÀ-ÿ'.-]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'.-]*){0,2})", ln)
        if m and not m[1].upper().startswith("DJ") and fold(m[1]) not in seen:
            seen.add(fold(m[1]))
            out.claims.append(_claim("performer", m[1].strip(), state, observation_id, ln, method + ":artist"))
    if not seen:
        out.unknown.append("performer")

    # ---- ticket / contact ------------------------------------------------------------------
    tk = re.search(r"(gratuit|free entry|free|entree libre|\b\d[\d .]{2,8}\s*(?:f\s*cfa|fcfa|xof|cfa)\b|vip\s*[:\-]?\s*\d[\d .]*)", joined)
    if tk:
        out.claims.append(_claim("ticket", tk[1].strip(), state, observation_id, tk[0], method))
    else:
        out.unknown.append("ticket")
    phones = re.findall(r"(?:\+?229[\s.-]?)?(?:01|0[2-9])?[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}\b", text)
    phone = next((p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 8), None)
    if phone:
        out.claims.append(_claim("contact", phone, state, observation_id, phone, method))

    # ---- title and category ----------------------------------------------------------------
    skip = re.compile(r"(\d{1,2}\s*h\b|\d{4}|lieu|venue|organis|pr[ée]sent|entr[ée]e|ticket|fcfa|xof|contact|"
                      r"\+?229|^dj\b|@)", re.IGNORECASE)
    title = next((ln for ln in lines if 3 <= len(ln) <= 80 and not skip.search(ln)
                  and fold(ln) not in WEEKDAYS and not any(m in fold(ln).split() for m in MONTHS)), None)
    if title:
        out.claims.append(_claim("title", title.strip(" -–|•"), state, observation_id, title, method))
    else:
        out.unknown.append("title")
    for kw, cat in CATEGORIES.items():
        if re.search(rf"\b{re.escape(kw)}\b", joined):
            out.claims.append(_claim("category", cat, state, observation_id, kw, method))
            break
    else:
        out.unknown.append("category")
    return out
