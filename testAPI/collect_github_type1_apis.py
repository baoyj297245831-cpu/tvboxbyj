import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from extract_type1_apis import api_identity


SCRIPT_DIR = Path(__file__).resolve().parent
DIRECT_API_FILE = SCRIPT_DIR / "直连API.json"
CANDIDATE_FILE = SCRIPT_DIR / "github_type1_candidates.json"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
REQUEST_TIMEOUT = 20


def normalize_json_url(value):
    parts = urllib.parse.urlsplit(value.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("请输入可访问的 HTTP/HTTPS JSON 文件地址。")
    if parts.username or parts.password:
        raise ValueError("地址中不能包含用户名或密码。")

    if not urllib.parse.unquote(parts.path).lower().endswith(".json"):
        raise ValueError("地址路径必须以 .json 结尾。")
    host = (parts.hostname or "").lower()
    if host == "github.com" and parts.scheme.lower() == "https":
        segments = parts.path.strip("/").split("/")
        if len(segments) >= 5 and segments[2] == "blob":
            owner, repo, _, branch = segments[:4]
            file_path = "/".join(segments[4:])
            raw_path = "/{}/{}/{}/{}".format(owner, repo, branch, file_path)
            return urllib.parse.urlunsplit(
                ("https", "raw.githubusercontent.com", raw_path, parts.query, "")
            )

    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, parts.query, "")
    )


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def parse_json_with_comments(text):
    output = []
    index = 0
    in_string = False
    escaped = False

    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""

        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
        elif char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
        elif char == "/" and next_char == "*":
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("GitHub JSON 含有未闭合的块注释。")
            output.extend("\n" for skipped in text[index:end + 2] if skipped == "\n")
            index = end + 2
        else:
            output.append(char)
            index += 1

    return json.loads("".join(output))


def fetch_remote_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tvboxbyj-api-candidate-collector",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("GitHub JSON 文件超过 10 MiB。")
    return parse_json_with_comments(body.decode("utf-8-sig"))


def write_json_atomically(path, data):
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=str(path.parent),
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write("\n")
        os.replace(str(temporary_path), str(path))
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main():
    entered_url = input("请输入可访问的 JSON 文件地址: ").strip()
    if not entered_url:
        raise ValueError("JSON 文件地址不能为空。")
    source_url = normalize_json_url(entered_url)

    source = fetch_remote_json(source_url)
    if not isinstance(source, dict) or not isinstance(source.get("sites"), list):
        raise ValueError("远程 JSON 必须包含 sites 数组。")

    direct = load_json(DIRECT_API_FILE)
    if not isinstance(direct, dict) or not isinstance(direct.get("sites"), list):
        raise ValueError("直连API.json 必须包含 sites 数组。")

    if CANDIDATE_FILE.exists():
        candidates = load_json(CANDIDATE_FILE)
        if not isinstance(candidates, dict) or not isinstance(candidates.get("sites"), list):
            raise ValueError("候选文件格式无效，必须包含 sites 数组。")
    else:
        candidates = {"sources": [], "sites": []}

    known_apis = set()
    known_keys = set()
    for site in direct["sites"] + candidates["sites"]:
        if not isinstance(site, dict):
            continue
        identity = api_identity(site.get("api"))
        if identity:
            known_apis.add(identity)
        if site.get("key") is not None:
            known_keys.add(site["key"])

    added = []
    skipped_api = 0
    skipped_key = 0
    skipped_invalid = 0
    for site in source["sites"]:
        if (
            not isinstance(site, dict)
            or type(site.get("type")) is not int
            or site.get("type") != 1
        ):
            continue

        api = site.get("api")
        if not isinstance(api, str):
            skipped_invalid += 1
            continue
        api_parts = urllib.parse.urlsplit(api.strip())
        if api_parts.scheme not in ("http", "https") or not api_parts.netloc:
            skipped_invalid += 1
            continue

        identity = api_identity(api)
        if identity in known_apis:
            skipped_api += 1
            continue
        if site.get("key") is not None and site["key"] in known_keys:
            skipped_key += 1
            continue

        added.append(site)
        known_apis.add(identity)
        if site.get("key") is not None:
            known_keys.add(site["key"])

    candidates["sites"].extend(added)
    if source_url not in candidates.get("sources", []):
        candidates.setdefault("sources", []).append(source_url)
    write_json_atomically(CANDIDATE_FILE, candidates)

    print("新增待审核 type 1 接口: {}".format(len(added)))
    print("跳过重复 API: {}".format(skipped_api))
    print("跳过重复 key: {}".format(skipped_key))
    print("跳过无效 API: {}".format(skipped_invalid))
    print("候选文件: {}".format(CANDIDATE_FILE))
    print("未请求候选接口；审核后再手动测试并加入直连API.json。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit("收集失败: {}".format(error))
