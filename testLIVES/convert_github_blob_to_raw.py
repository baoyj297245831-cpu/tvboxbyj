#!/usr/bin/env python3
"""Convert GitHub blob file URLs into raw.githubusercontent.com URLs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "待转化源地址.txt"
DEFAULT_OUTPUT = SCRIPT_DIR / "转换后源地址.txt"
GITHUB_BLOB_URL = re.compile(
    r"https://github\.com/([^/\s]+)/([^/\s]+)/blob/([^/\s]+)/([^\s)\]]+)"
)


def convert_url(url: str) -> str:
    """Convert one GitHub blob URL; leave all other URLs unchanged."""
    match = GITHUB_BLOB_URL.fullmatch(url)
    if not match:
        return url

    owner, repository, branch, path = match.groups()
    path = path.rstrip(".,;!?")
    return f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}/{path}"


def convert_text(text: str) -> str:
    """Convert GitHub blob URLs found in plain or Markdown text."""
    return GITHUB_BLOB_URL.sub(
        lambda match: convert_url(match.group(0)),
        text,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert GitHub blob URLs to TVBox-compatible raw URLs."
    )
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8")
    args.output.write_text(convert_text(source), encoding="utf-8")
    print(f"已转换并保存到：{args.output}")


if __name__ == "__main__":
    main()
