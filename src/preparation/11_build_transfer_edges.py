
import csv
from pathlib import Path
from itertools import combinations

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"

input_path = DATA_DIR / "transfer_candidates.csv"
output_path = DATA_DIR / "transfer_edges.csv"

edges = []

with open(input_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)

    for row in reader:
        station = row["station"].strip()
        lines = row["lines"].split(";")

        # 生成线路两两组合
        for line_a, line_b in combinations(lines, 2):
            edges.append({
                "station": station,
                "line_a": line_a,
                "line_b": line_b,
                "edge_type": "candidate_transfer",
                "status": "pending_verification"
            })

# 保存结果
fields = [
    "station",
    "line_a",
    "line_b",
    "edge_type",
    "status"
]

with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(edges)

print("=== 候选换乘边生成完成 ===")
print("候选换乘站数量：", len(set(e["station"] for e in edges)))
print("候选换乘边数量：", len(edges))

for edge in edges:
    print(
        edge["station"],
        f'{edge["line_a"]}号线-{edge["line_b"]}号线'
    )

print("文件保存至：", output_path)
