
import csv
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

station_lines = defaultdict(list)

# 读取1—8号线
for line in range(1, 9):
    file_path = DATA_DIR / f"line{line}_stations.csv"

    with open(file_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            station = row["station"].strip()
            station_lines[station].append(str(line))

# 提取重复站名
transfers = []

for station, lines in station_lines.items():
    if len(lines) > 1:
        transfers.append({
            "station": station,
            "lines": ";".join(lines),
            "line_count": len(lines)
        })

transfers.sort(key=lambda x: x["station"])

# 保存结果
output_path = DATA_DIR / "transfer_candidates.csv"

with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["station", "lines", "line_count"]
    )
    writer.writeheader()
    writer.writerows(transfers)

print("=== 换乘站自动识别结果 ===")
print("疑似换乘站数量：", len(transfers))

for item in transfers:
    print(
        item["station"],
        "：",
        item["lines"].replace(";", "、"),
        "号线"
    )

print("结果保存至：", output_path)
