"""CLI for a single bounded tracking-intelligence scan."""
from __future__ import annotations

import argparse
import sys

from .tracking import json_dumps, render_markdown, scan_tracking


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fingerprint supported tracking technologies on one authorized public HTML page."
    )
    parser.add_argument("url", help="Public HTTP(S) URL to inspect")
    parser.add_argument("--json", dest="json_path", help="Write JSON report to this file")
    parser.add_argument("--markdown", dest="markdown_path", help="Write Markdown assessment to this file")
    args = parser.parse_args()

    try:
        report = scan_tracking(args.url)
        json_text = json_dumps(report)
        markdown_text = render_markdown(report)
        if args.json_path:
            with open(args.json_path, "w", encoding="utf-8") as stream:
                stream.write(json_text + "\n")
        if args.markdown_path:
            with open(args.markdown_path, "w", encoding="utf-8") as stream:
                stream.write(markdown_text + "\n")
        if not args.json_path and not args.markdown_path:
            print(json_text)
        elif not args.json_path:
            print(json_text)
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"scout-track: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
