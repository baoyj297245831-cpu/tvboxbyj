import sys

def txt_to_m3u(input_file, output_file):
    current_group = "未分组"
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        fout.write("#EXTM3U\n")
        for line in fin:
            line = line.strip()
            if not line:
                continue
            if line.endswith(",#genre#"):
                current_group = line.replace(",#genre#", "")
            elif "," in line:
                name, url = line.split(",", 1)
                name = name.strip()
                url = url.strip()
                if name and url:
                    fout.write(f'#EXTINF:-1 group-title="{current_group}",{name}\n')
                    fout.write(f'{url}\n')

if __name__ == "__main__":
    txt_to_m3u("自用直播油管源.txt", "自用直播油管源.m3u")
    print("转换完成！")