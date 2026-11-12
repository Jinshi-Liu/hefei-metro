
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv(filename):
    with open(DATA_DIR / filename, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {
            row["station"].strip(): row
            for row in reader
            if row.get("station")
        }


candidates = read_csv("transfer_candidates.csv")
verified = read_csv("transfer_verification.csv")

candidate_names = set(candidates)
verified_names = set(verified)

missing = candidate_names - verified_names
extra = verified_names - candidate_names

print("=== 换乘数据表完整比较 ===")
print("自动识别数量：", len(candidates))
print("人工核验记录：", len(verified))

print("\n=== 自动识别表中缺少的记录 ===")
if missing:
    for station in sorted(missing):
        print(station)
else:
    print("无")

print("\n=== 人工核验表中额外的记录 ===")
if extra:
    for station in sorted(extra):
        print(station, "：", verified[station]["lines"])
else:
    print("无")

print("\n=== 线路对应关系不一致 ===")
mismatch = []

for station in candidate_names & verified_names:
    a = set(candidates[station]["lines"].split(";"))
    b = set(verified[station]["lines"].split(";"))

    if a != b:
        mismatch.append(station)
        print(station, "自动识别：", a, "核验表：", b)

if not mismatch:
    print("无")

print("\n=== 比较总结 ===")
print("共同记录：", len(candidate_names & verified_names))
print("缺少记录：", len(missing))
print("额外记录：", len(extra))
print("线路不一致：", len(mismatch))

print("\n比较完成！")
