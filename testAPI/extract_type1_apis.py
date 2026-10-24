import json
import re
from pathlib import Path
from urllib.parse import urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_path(filename):
    path = Path(filename).expanduser()
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path.resolve()


def api_identity(api):
    if not isinstance(api, str):
        return None

    parts = urlsplit(api.strip())
    if not parts.scheme or not parts.netloc:
        return api.strip()

    path = re.sub(r"/+", "/", parts.path).rstrip("/")
    return parts.netloc.lower() + path + ("?" + parts.query if parts.query else "")


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def main():
    source_name = input("请输入源 JSON 文件名: ").strip()
    target_name = input("请输入目标 JSON 文件名: ").strip()
    if not source_name or not target_name:
        raise ValueError("源文件名和目标文件名都不能为空。")

    source_path = resolve_path(source_name)
    target_path = resolve_path(target_name)
    if source_path == target_path:
        raise ValueError("源文件和目标文件不能是同一个文件。")

    source = load_json(source_path)
    if not isinstance(source, dict) or not isinstance(source.get("sites"), list):
        raise ValueError("源 JSON 必须包含 sites 数组。")

    if target_path.exists():
        target = load_json(target_path)
        if not isinstance(target, dict) or not isinstance(target.get("sites"), list):
            raise ValueError("目标 JSON 必须包含 sites 数组。")
    else:
        target = {"spider": "", "sites": []}

    existing_apis = {
        api_identity(site.get("api"))
        for site in target["sites"]
        if isinstance(site, dict)
    }
    existing_keys = {
        site.get("key")
        for site in target["sites"]
        if isinstance(site, dict) and site.get("key") is not None
    }

    added = []
    skipped_api = 0
    skipped_key = 0
    skipped_invalid_api = 0
    for site in source["sites"]:
        if not isinstance(site, dict) or site.get("type") != 1:
            continue

        api = site.get("api")
        if not isinstance(api, str) or not api.strip():
            skipped_invalid_api += 1
            continue
        identity = api_identity(api)
        if identity in existing_apis:
            skipped_api += 1
            continue
        if site.get("key") is not None and site["key"] in existing_keys:
            skipped_key += 1
            continue

        added.append(site)
        existing_apis.add(identity)
        if site.get("key") is not None:
            existing_keys.add(site["key"])

    target["sites"].extend(added)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(target, file, ensure_ascii=False, indent=4)
        file.write("\n")

    print("新增 type 1 接口: {}".format(len(added)))
    print("跳过重复 API: {}".format(skipped_api))
    print("跳过重复 key: {}".format(skipped_key))
    print("跳过无效 API: {}".format(skipped_invalid_api))
    print("目标文件: {}".format(target_path))


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit("处理失败: {}".format(error))
