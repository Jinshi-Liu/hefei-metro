"""现场演示：指定车站或某一对站，实时算换乘中断后的失联与绕行。

不写文件、不改结果，只读 results/metro.graphml，用于答辩现场提问即算。

    python -m src.demo --list
    python -m src.demo --station 西七里塘
    python -m src.demo --station 西七里塘 --station 合肥南站
    python -m src.demo --od 东区 科大先研院
    python -m src.demo --station 西七里塘 --examples 5 --transfer 3
"""

import argparse
import time
import unicodedata
from pathlib import Path

import networkx as nx
import numpy as np

from .build_network import GRAPH_FILE
from .transfer_ablation import MetroAblation

EXAMPLE_LIMIT = 3


def pair_names(metro):
    i, j = metro.od
    return [(metro.stations[a], metro.stations[b]) for a, b in zip(i, j)]


def fmt(minutes):
    if not np.isfinite(minutes):
        return "不可达"
    return f"{minutes:.1f} 分钟"


def width(text):
    """终端里的显示宽度：中文和全角符号占两列。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text, cells):
    return text + " " * max(0, cells - width(text))


def station_report(metro, closed, transfer, examples):
    base = metro.distances(transfer_minutes=transfer)
    after = metro.distances(closed, transfer)
    reachable = np.isfinite(after)
    extra = after[reachable] - base[reachable]
    lost, slower = ~reachable, extra > 1e-9
    names = pair_names(metro)

    print(f"\n关闭换乘：{'、'.join(closed)}（换乘 {transfer:g} 分钟，"
          f"涉及 {sum(len(metro.transfer_edges[s]) for s in closed)} 条换乘边）")
    print(f"全网 {len(base)} 对物理站：失联 {int(lost.sum())} 对（{lost.mean():.2%}），"
          f"仍可达但变慢 {int(slower.sum())} 对（{slower.mean():.2%}）")
    if reachable.any():
        print(f"仍可达者的额外时间：平均 +{extra.mean():.1f} 分钟，"
              f"中位 +{np.median(extra):.1f}，最大 +{extra.max():.1f}（{names[int(extra.argmax())][0]} → "
              f"{names[int(extra.argmax())][1]}）")
    if slower.any():
        print(f"只算变慢的 {int(slower.sum())} 对：平均 +{extra[slower].mean():.1f} 分钟")
    efficiency = (1 / after[reachable]).sum() / (1 / base).mean() / len(base)
    print(f"相对出行效率：{efficiency:.4f}（1 为正常）")

    if lost.any():
        print(f"\n失联示例（原 {examples} 对，按原有时间从短到长取）：")
        lost_idx = np.flatnonzero(lost)
        lost_idx = lost_idx[np.argsort(base[lost_idx])][:examples]
        for k in lost_idx:
            print(f"  {names[k][0]} → {names[k][1]}：原 {fmt(base[k])} → 无路可走")
    if slower.any():
        print(f"\n绕行示例（额外时间最多的 {examples} 对）：")
        slower_idx = np.flatnonzero(slower)
        slower_idx = slower_idx[np.argsort(-extra[slower_idx])][:examples]
        for k in slower_idx:
            print(f"  {names[k][0]} → {names[k][1]}：{fmt(base[k])} → {fmt(after[k])}"
                  f"（+{extra[k]:.1f}）")


def od_report(metro, start, end, transfer):
    unknown = [n for n in (start, end) if n not in metro.stations]
    if unknown:
        raise SystemExit(f"没有这些站：{'、'.join(unknown)}")
    base = metro.distances(transfer_minutes=transfer)
    i, j = metro.stations.index(start), metro.stations.index(end)
    if i > j:
        i, j = j, i
    positions = {tuple(pair): k for k, pair in enumerate(zip(*metro.od))}
    k = positions.get((i, j))
    if k is None:
        k = positions[(j, i)]
    print(f"\n{start} → {end}（换乘 {transfer:g} 分钟）：正常 {fmt(base[k])}")
    for station in sorted(metro.transfer_edges):
        after = metro.distances([station], transfer)
        print(f"  若 {station} 不能换乘：{'不可达' if not np.isfinite(after[k]) else fmt(after[k])}"
              f"{'' if not np.isfinite(after[k]) else f'（+{after[k] - base[k]:.1f}）'}")


def ranking(metro, transfer):
    base = metro.distances(transfer_minutes=transfer)
    rows = []
    for station in sorted(metro.transfer_edges):
        after = metro.distances([station], transfer)
        reachable = np.isfinite(after)
        lost = int((~reachable).sum())
        extra = after[reachable] - base[reachable]
        rows.append((lost, float(extra.mean()), station, "、".join(sorted(metro.lines[station]))))
    rows.sort(key=lambda row: (-row[0], -row[1], row[2]))
    total = len(base)
    print(f"\n{len(rows)} 座换乘站的单站消融排名（换乘 {transfer:g} 分钟）")
    print("".join(pad(h, c) for h, c in [("排名", 6), ("站名", 16), ("换乘线路", 14)])
          + "".join(f"{h:>10}" for h in ("失联 OD", "占比", "仍可达平均 +分钟")))
    for rank, (lost, added, station, lines) in enumerate(rows, 1):
        print("".join(pad(v, c) for v, c in [(str(rank), 6), (station, 16), (lines, 14)])
              + "".join(f"{v:>10}" for v in (lost, f"{lost / total:.2%}", f"{added:.2f}")))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=GRAPH_FILE)
    parser.add_argument("--station", action="append", default=[], help="不能换乘的站，可重复")
    parser.add_argument("--od", nargs=2, metavar=("起点", "终点"), help="查一对站")
    parser.add_argument("--transfer", type=float, default=None, help="换乘分钟，默认取图上的基准值")
    parser.add_argument("--examples", type=int, default=EXAMPLE_LIMIT, help="每类列举几个例子")
    parser.add_argument("--list", action="store_true", help="列出可用的换乘站")
    parser.add_argument("--rank", action="store_true", help="打印全部换乘站的单站消融排名")
    args = parser.parse_args()

    started = time.perf_counter()
    metro = MetroAblation(nx.read_graphml(args.graph))
    transfer = metro.transfer_minutes if args.transfer is None else args.transfer
    print(f"线网：{len(metro.stations)} 座物理站，{len(metro.transfer_edges)} 座换乘站，"
          f"{len(metro.od[0])} 对物理站（读图 {time.perf_counter() - started:.2f} 秒）")

    if args.list:
        for station in sorted(metro.transfer_edges):
            print(f"  {station}：{'、'.join(sorted(metro.lines[station]))}")
        return
    if args.od:
        od_report(metro, *args.od, transfer)
        return
    if args.rank:
        ranking(metro, transfer)
        return
    if not args.station:
        parser.error("至少给一个 --station，或用 --list、--rank、--od")

    unknown = [s for s in args.station if s not in metro.transfer_edges]
    if unknown:
        raise SystemExit(f"不是换乘站：{'、'.join(unknown)}；用 --list 查看可用站名")
    station_report(metro, args.station, transfer, max(1, args.examples))


if __name__ == "__main__":
    main()
