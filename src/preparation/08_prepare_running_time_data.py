
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"

output_path = DATA_DIR / "segment_running_times.csv"

all_segments = []

# 读取1—8号线及S1线
for line in [str(i) for i in range(1, 9)] + ["S1"]:

    filename = (
        "s1_stations.csv"
        if line == "S1"
        else f"line{line}_stations.csv"
    )

    file_path = DATA_DIR / filename

    with open(file_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    stations = [row["station"].strip() for row in rows]

    # 生成相邻车站区间
    for i in range(len(stations) - 1):

        all_segments.append({
            "line": line,
            "from_station": stations[i],
            "to_station": stations[i + 1],
            "running_time_min": "",
            "status": "trial" if line == "S1" else "operating",
            "source": ""
        })

# 保存CSV
with open(output_path, "w", newline="", encoding="utf-8-sig") as f:

    fieldnames = [
        "line",
        "from_station",
        "to_station",
        "running_time_min",
        "status",
        "source"
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_segments)

print("=== 区间运行时间表生成成功 ===")
print("区间总数：", len(all_segments))
print("正式运营线路区间：", sum(
    1 for x in all_segments if x["status"] == "operating"
))
print("S1试乘线路区间：", sum(
    1 for x in all_segments if x["status"] == "trial"
))
print("保存位置：", output_path)
