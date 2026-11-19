# SCOUT Tracking Intelligence v0.1

This increment extends the existing SCOUT Intelligence Fabric. It is a bounded one-page public HTML fingerprint scan—not a crawler, dashboard, platform, or campaign-performance analyzer.

## Run

From `scout-intelligence-fabric/`:

```bash
python -m pip install -e ".[dev]"
scout-track https://example.org --json tracking-profile.json --markdown tracking-assessment.md
pytest
```

The command performs one explicit scan. It emits JSON and Markdown files when requested; otherwise JSON is written to stdout.

## Scope

Initial fingerprints cover Meta Pixel, Google Tag Manager, Google Analytics 4, Google Ads conversion, TikTok Pixel, LinkedIn Insight Tag, Snap Pixel, Microsoft Clarity, Hotjar, and HubSpot.

Evidence is based on signatures in the returned HTML, script sources, and inline scripts. Multiple independent matched signatures raise the detector confidence from medium to high. Confidence describes detection evidence only; it is not a probability that campaigns are active.

## Evidence contract

Each detection generates an observation using the existing SCOUT Observation shape:

- stable observation ID derived from resolved URL, technology ID, and source HTML hash
- subject and narrowly worded claim
- state `observed`
- confidence, technology ID, category, matched signatures, and detector version in attributes
- provenance with source URL, observed/collected timestamps, collection method, adapter, and source HTML SHA-256 reference

The profile includes scan-level source integrity, coverage, explicit limitations, interpretation, opportunities, and unknowns. It does not infer ad spend, audience size, active campaigns, conversion rates, or profitability.

## Safety and coverage

- one public page per scan; no link crawling
- static HTML only; JavaScript is not executed
- 15-second timeout and 1 MB response cap
- limited manual redirects, with public-address validation on targets
- blocks credentials in URLs and targets resolving to non-public addresses
- no authenticated pages, access-control bypass, anti-bot evasion, or private data collection

The public-IP validation is best-effort and does not fully eliminate DNS-rebinding risk. Use only authorized targets. Server-side, dynamic, blocked, or consent-gated tracking may not appear. "Not observed" is not evidence of absence.

## Deliberately out of scope

Dashboards, scheduling, multi-page crawling, browser automation, persistence/database changes, broad signature catalogs, deployment, and campaign-performance claims.
