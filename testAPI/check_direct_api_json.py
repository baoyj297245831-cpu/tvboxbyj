import concurrent.futures
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


API_FILE = Path(__file__).resolve().parent / "直连API.json"
REQUEST_TIMEOUT = 10
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_WORKERS = 4


def url_with_list_action(api):
    parts = urllib.parse.urlsplit(api)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    if not any(key == "ac" for key, _ in query):
        query.append(("ac", "list"))
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment)
    )


def response_is_json(body):
    try:
        json.loads(body.decode("utf-8-sig"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def check_site(indexed_site):
    index, site = indexed_site
    api = site.get("api")
    result = {"index": index, "key": site.get("key", "(无 key)"), "api": api}
    if not isinstance(api, str) or not api.startswith(("http://", "https://")):
        result.update(status="unknown", detail="不是有效的 HTTP/HTTPS 地址")
        return result

    request = urllib.request.Request(
        url_with_list_action(api),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, */*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                result.update(status="unknown", detail="响应超过 4 MiB，未作删除判断")
            else:
                result.update(
                    status="json" if response_is_json(body) else "non-json",
                    detail="HTTP {}".format(response.status),
                )
    except urllib.error.HTTPError as error:
        body = error.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            result.update(status="unknown", detail="HTTP {}，响应超过 4 MiB".format(error.code))
        else:
            result.update(
                status="json" if response_is_json(body) else "non-json",
                detail="HTTP {}".format(error.code),
            )
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        result.update(status="unknown", detail=str(error))

    return result


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
    with API_FILE.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("sites"), list):
        raise ValueError("JSON 文件必须包含 sites 数组。")

    sites = data["sites"]
    if any(not isinstance(site, dict) for site in sites):
        raise ValueError("sites 数组中的每一项都必须是 JSON 对象。")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_site, enumerate(sites)))

    for result in results:
        print(
            "[{}] {} | {} | {}".format(
                result["status"].upper(),
                result["key"],
                result["api"],
                result["detail"],
            )
        )

    remove_indexes = {
        result["index"]
        for result in results
        if result["status"] != "json"
    }
    non_json_count = sum(result["status"] == "non-json" for result in results)
    unknown_count = sum(result["status"] == "unknown" for result in results)
    print(
        "\n检查完成: {} 个，JSON: {}，非 JSON: {}，未能确认: {}".format(
            len(results),
            sum(result["status"] == "json" for result in results),
            non_json_count,
            unknown_count,
        )
    )

    if not remove_indexes:
        print("没有非 JSON 或未能确认的接口，无需修改文件。")
        return

    remaining_sites = [
        site for index, site in enumerate(sites) if index not in remove_indexes
    ]
    backup_path = API_FILE.with_name(
        "{}.{}.bak".format(API_FILE.name, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    )
    shutil.copy2(str(API_FILE), str(backup_path))
    data["sites"] = remaining_sites
    write_json_atomically(API_FILE, data)
    print("已删除 {} 个接口。".format(len(sites) - len(remaining_sites)))
    print("备份文件: {}".format(backup_path))
    print("删除未能确认的接口: {} 个。".format(unknown_count))


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit("检查失败: {}".format(error))
