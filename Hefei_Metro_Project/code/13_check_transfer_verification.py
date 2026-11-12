
import csv
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

file_path = DATA_DIR / "transfer_edge_verification.csv"

with open(file_path, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

print("=== 换乘核验表检查 ===")

print("记录总数：", len(rows))

# 检查重复记录
keys = [
    (r["station"], r["line_a"], r["line_b"])
    for r in rows
]

duplicates = [
    k for k, v in Counter(keys).items() if v > 1
]

print("重复记录数：", len(duplicates))

# 检查状态分布
status_count = Counter(r["transfer_status"] for r in rows)

print("\n=== 核验状态统计 ===")
for status, count in status_count.items():
    print(status, "：", count)

# 检查换乘时间
filled_times = [
    r for r in rows if r["transfer_time_min"].strip()
]

print("\n已填写换乘时间的记录：", len(filled_times))

# 检查空字段
print("\n=== 数据完整性 ===")

required = ["station", "line_a", "line_b", "transfer_status"]

errors = [
    i + 2
    for i, r in enumerate(rows)
    if any(not r[field].strip() for field in required)
]

print("必要字段缺失记录：", len(errors))

print("\n检查完成！")
