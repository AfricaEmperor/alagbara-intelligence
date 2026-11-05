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
