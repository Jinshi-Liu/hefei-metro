
import csv
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

station_lines = defaultdict(list)

# 读取1—8号线和S1线
for line in [str(i) for i in range(1, 9)] + ["S1"]:

    file_path = DATA_DIR / (
        f"s1_stations.csv" if line == "S1"
        else f"line{line}_stations.csv"
    )

    with open(file_path, encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)

        for row in rows:
            station = row["station"].strip()
            station_lines[station].append(line)

print("=== S1与原有线路重名站点检查 ===")

for station, lines in station_lines.items():
    if "S1" in lines and len(lines) > 1:
        print(f"{station}：{lines}")

print("\n检查完成！")
