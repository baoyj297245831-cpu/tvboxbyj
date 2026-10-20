#!/usr/bin/env python3
"""Add reachable TVBox JSON configurations from README and this repository."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "cangkulist" / "自用单仓.json"
README = ROOT / "README.md"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 15
README_URL_PATTERN = re.compile(r"https?://[^\s)<>]+", re.IGNORECASE)


def is_playable_config(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    sites = data.get("sites")
    return isinstance(sites, list) and any(
        isinstance(site, dict)
        and any(
            isinstance(site.get(field), str) and site[field].strip()
            for field in ("api", "url")
        )
        for site in sites
    )


def is_adult_source(source: dict[str, str]) -> bool:
    name = source.get("name", "")
    url = source.get("url", "")
    decoded = unquote(f"{name} {url}").replace("＋", "+").lower()
    path_segments = (
        name.replace("\\", "/").lower().split("/")
        + urlsplit(unquote(url)).path.lower().split("/")
    )
    return "18+" in decoded or "18＋" in decoded or "18" in path_segments


def is_live_source(source: dict[str, str]) -> bool:
    name = source.get("name", "")
    url = source.get("url", "")
    decoded = unquote(f"{name} {url}").replace("\\", "/").lower()
    return "直播源" in decoded or "直播" in decoded.split("/")


def read_remote_config(url: str) -> bool:
    request = Request(
        encode_url(url), headers={"User-Agent": "tvboxbyj-source-check/1.0"}
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
    return is_playable_config(json.loads(payload.decode("utf-8-sig")))


def encode_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError(f"invalid source URL: {url}")
    hostname = hostname.encode("idna").decode("ascii")
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    path = quote(parsed.path, safe="/%:@!$&'()*+,;=-._~")
    query = quote(parsed.query, safe="/?%:@!$&'()*+,;=-._~")
    return urlunsplit((parsed.scheme, netloc, path, query, parsed.fragment))


def readme_candidates() -> list[dict[str, str]]:
    candidates = []
    seen_urls = set()
    text = README.read_text(encoding="utf-8")
    for raw_url in README_URL_PATTERN.findall(text):
        url = raw_url.rstrip(".,;")
        parsed = urlsplit(url)
        if parsed.path.lower().endswith(".json") and url not in seen_urls:
            name = Path(unquote(parsed.path)).stem or url
            candidate = {"name": name, "url": url}
            if not is_adult_source(candidate) and not is_live_source(candidate):
                candidates.append(candidate)
            seen_urls.add(url)
    return candidates


def local_candidates() -> list[dict[str, str]]:
    repository = os.environ.get(
        "GITHUB_REPOSITORY", "baoyj297245831-cpu/tvboxbyj"
    )
    owner, repo = repository.split("/", 1)
    base_url = f"https://{owner}.github.io/{repo}/"
    candidates = []

    for path in sorted(ROOT.rglob("*.json")):
        relative = path.relative_to(ROOT)
        if any(part.startswith(".") for part in relative.parts):
            continue
        candidate = {
            "name": f"自动收录 · {relative.as_posix()[:-5]}",
            "url": f"{base_url}{quote(relative.as_posix(), safe='/')}",
        }
        if is_adult_source(candidate) or is_live_source(candidate):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            print(f"Skipping invalid local JSON {relative}: {error}", file=sys.stderr)
            continue
        if is_playable_config(data):
            candidates.append(candidate)
    return candidates


def collect_valid_readme_candidates(
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    valid = []
    for candidate in candidates:
        try:
            if read_remote_config(candidate["url"]):
                valid.append(candidate)
            else:
                print(
                    f"Skipping non-TVBox JSON source: {candidate['url']}",
                    file=sys.stderr,
                )
        except (URLError, OSError, UnicodeError, ValueError) as error:
            print(
                f"Could not validate {candidate['url']}: {error}",
                file=sys.stderr,
            )
    return valid


def update_manifest(candidates: list[dict[str, str]]) -> int:
    manifest = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("urls"), list):
        raise ValueError(f"{TARGET} must contain a 'urls' array")

    original_entries = manifest["urls"]
    manifest["urls"] = [
        entry
        for entry in original_entries
        if not isinstance(entry, dict)
        or not (is_adult_source(entry) or is_live_source(entry))
    ]
    removed_count = len(original_entries) - len(manifest["urls"])
    existing_urls = {
        entry.get("url")
        for entry in manifest["urls"]
        if isinstance(entry, dict) and isinstance(entry.get("url"), str)
    }
    added = []
    for candidate in candidates:
        if (
            not is_adult_source(candidate)
            and not is_live_source(candidate)
            and candidate["url"] not in existing_urls
        ):
            manifest["urls"].append(candidate)
            existing_urls.add(candidate["url"])
            added.append(candidate)

    if added or removed_count:
        TARGET.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
    if removed_count:
        print(f"Removed {removed_count} excluded source(s).")
    for candidate in added:
        print(f"Added {candidate['name']}: {candidate['url']}")
    print(f"Added {len(added)} source(s).")
    return len(added)


def main() -> int:
    manifest = json.loads(TARGET.read_text(encoding="utf-8-sig"))
    existing_urls = {
        entry.get("url")
        for entry in manifest["urls"]
        if isinstance(entry, dict) and isinstance(entry.get("url"), str)
    }
    external_candidates = [
        candidate
        for candidate in readme_candidates()
        if candidate["url"] not in existing_urls
    ]
    candidates = local_candidates() + collect_valid_readme_candidates(
        external_candidates
    )
    update_manifest(candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
