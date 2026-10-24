import locale
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
COLLECT_SCRIPT = SCRIPT_DIR / "collect_github_type1_apis.py"
EXTRACT_SCRIPT = SCRIPT_DIR / "extract_type1_apis.py"
CANDIDATE_FILE = "github_type1_candidates.json"
DIRECT_API_FILE = SCRIPT_DIR / "直连API.json"


def run_script(script, input_text):
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(SCRIPT_DIR),
        input=input_text,
        text=True,
        encoding=locale.getpreferredencoding(False),
        check=True,
    )


def main():
    source_url = input("请输入可访问的 HTTP/HTTPS JSON 文件地址: ").strip()
    if not source_url:
        raise ValueError("GitHub JSON 地址不能为空。")

    print("\n步骤 1/2：收集并去重 type 1 接口")
    run_script(COLLECT_SCRIPT, source_url + "\n")

    if not DIRECT_API_FILE.is_file():
        raise FileNotFoundError("目标文件不存在: {}".format(DIRECT_API_FILE))
    backup_path = DIRECT_API_FILE.with_name(
        "{}.{}.bak".format(
            DIRECT_API_FILE.name,
            datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        )
    )
    shutil.copy2(str(DIRECT_API_FILE), str(backup_path))

    print("\n步骤 2/2：合并候选接口到直连API.json")
    run_script(
        EXTRACT_SCRIPT,
        "{}\n{}\n".format(CANDIDATE_FILE, DIRECT_API_FILE.name),
    )
    print("合并前备份: {}".format(backup_path))
    print(
        "\n自动收集和合并完成。为避免自动请求来源配置中的任意第三方主机，"
        "接口可用性检查未自动运行。需要检查时请单独运行："
    )
    print("python check_direct_api_json.py")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        raise SystemExit("自动更新失败: {}".format(error))
