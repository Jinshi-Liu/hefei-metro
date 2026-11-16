
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "processed"

input_path = DATA_DIR / "transfer_edges.csv"
output_path = DATA_DIR / "transfer_edge_verification.csv"

with open(input_path, encoding="utf-8-sig") as f:
    edges = list(csv.DictReader(f))

fields = [
    "station",
    "line_a",
    "line_b",
    "transfer_type",
    "transfer_status",
    "transfer_time_min",
    "source",
    "notes"
]

with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    for edge in edges:
        writer.writerow({
            "station": edge["station"],
            "line_a": edge["line_a"],
            "line_b": edge["line_b"],
            "transfer_type": "",
            "transfer_status": "pending_verification",
            "transfer_time_min": "",
            "source": "",
            "notes": ""
        })

print("=== 换乘边核验表生成成功 ===")
print("核验记录数：", len(edges))
print("保存位置：", output_path)
