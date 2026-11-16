
import csv
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"

station_lines = defaultdict(set)
line_counts = {}

# 读取1—8号线的数据
for line in range(1, 9):
    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    line_counts[line] = len(rows)

    for row in rows:
        station = row["station"].strip()
        station_lines[station].add(str(line))

print("=== 各线路站点数量 ===")
for line, count in line_counts.items():
    print(f"{line}号线：{count}站")

print("\n=== 网络基础统计 ===")
print("线路站点记录总数：", sum(line_counts.values()))
print("不同站名数量：", len(station_lines))

print("\n=== 疑似换乘站 ===")
for station, lines in sorted(station_lines.items()):
    if len(lines) > 1:
        print(station, "：", "、".join(sorted(lines)) + "号线")

print("\n=== 数据完整性检查 ===")

for line in range(1, 9):
    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    stations = [row["station"].strip() for row in rows]
    sequences = [int(row["sequence"]) for row in rows]

    if len(stations) != len(set(stations)):
        print(f"{line}号线：存在重复站名！")
    elif sequences != list(range(1, len(rows) + 1)):
        print(f"{line}号线：站点顺序编号异常！")
    else:
        print(f"{line}号线：基础格式检查通过")
