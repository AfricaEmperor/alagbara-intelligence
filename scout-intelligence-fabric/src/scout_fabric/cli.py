"""Command-line entry point for one explicit public-page acquisition."""
import argparse
import json
import sys

from .acquire import acquire_public_page

def main() -> int:
    parser = argparse.ArgumentParser(description="Capture one authorized public HTML page as evidence JSON.")
    parser.add_argument("url", help="Absolute HTTP(S) URL to retrieve")
    parser.add_argument("--output", "-o", help="Write JSON to this path; stdout by default")
    args = parser.parse_args()
    try:
        record = json.dumps(acquire_public_page(args.url).to_dict(), ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as stream:
                stream.write(record + "\n")
        else:
            print(record)
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"scout: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())


def intake_main() -> int:
    """scout-intake: build a candidate bundle from a locally supplied authorized HTML file."""
    from .intake import IntakeRefused, build_bundle, load_registry

    ap = argparse.ArgumentParser(description="Build a SCOUT candidate bundle from authorized, supplied HTML.")
    ap.add_argument("--registry", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--url", required=True, help="URL the HTML was obtained from")
    ap.add_argument("--html-file", required=True)
    ap.add_argument("--output", "-o")
    a = ap.parse_args()
    try:
        source = load_registry(a.registry)[a.source]
        with open(a.html_file, encoding="utf-8") as fh:
            bundle = build_bundle(source, a.url, fh.read())
    except (KeyError, IntakeRefused, ValueError, OSError) as exc:
        print(f"scout-intake: refused: {exc}", file=sys.stderr)
        return 2
    out = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    if a.output:
        open(a.output, "w", encoding="utf-8").write(out)
    else:
        print(out, end="")
    return 0
