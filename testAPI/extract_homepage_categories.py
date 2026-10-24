import json
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_FILE = SCRIPT_DIR / "直连主页.txt"
OUTPUT_FILE = SCRIPT_DIR / "直连主页分类.txt"
TYPE_NAME_PATTERN = re.compile(r'"type_name"\s*:\s*("(?:\\.|[^"\\])*")')


def extract_type_names(text):
    names = []
    seen = set()
    for match in TYPE_NAME_PATTERN.finditer(text):
        name = json.loads(match.group(1))
        if name not in seen:
            names.append(name)
            seen.add(name)
    return names


def main():
    text = SOURCE_FILE.read_text(encoding="utf-8-sig")
    names = extract_type_names(text)
    if not names:
        raise ValueError('没有找到 "type_name" 字段。')

    quoted_names = [json.dumps(name, ensure_ascii=False) + "," for name in names]
    output = "\n".join(quoted_names) + "\n"
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print("提取分类名称: {}".format(len(names)))
    print("输出文件: {}".format(OUTPUT_FILE))
    print(output, end="")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit("提取失败: {}".format(error))
