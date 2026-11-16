# -*- coding: utf-8 -*-
"""B 项一键复现脚本：校验网络 → 中心性排名 → 路径评价/单站中断 → 图表。

用法（项目根目录下）::

    python src/run_b.py

每一步都会打印参数与关键结果，全部输出写入 results/tables 与 results/figures。
不写入任何编造的运行分钟数或换乘分钟数。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

import build_network
import centrality
import experiments
import figures
import routing


def banner(title: str) -> None:
    print()
    print("#" * 72)
    print(f"# {title}")
    print("#" * 72)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    start = time.perf_counter()

    banner("步骤 1/4：重建并校验网络（与 A 项 GraphML 对照）")
    build_network.build_all()
    cmp = build_network.compare_with_saved_graphml()
    print(f"与 A 项 GraphML 一致：{cmp.get('consistent')}")
    if cmp.get("consistent") is not True:
        print("警告：重建网络与 A 项结果不一致，后续结果需谨慎解释。", file=sys.stderr)

    banner("步骤 2/4：物理车站网络中心性与基础排名")
    centrality.main()

    banner("步骤 3/4：路径评价与单站换乘中断实验")
    experiments.main()

    banner("步骤 4/4：生成图表")
    figures.setup_chinese_font()
    figures.FIG_DIR.mkdir(parents=True, exist_ok=True)
    made = [
        figures.fig_physical_network_with_key_stations(),
        figures.fig_station_loss_bar(),
        figures.fig_centrality_vs_loss(),
        figures.fig_cost_model_sensitivity(),
        figures.fig_case_alternatives("紫庐"),
    ]
    for p in made:
        print("  ", p)

    elapsed = time.perf_counter() - start
    banner(f"完成，用时 {elapsed:.1f} 秒")
    print("交付物：")
    print("  基础排名   ：results/tables/B01_*.csv, B02_*.csv, B03_*.csv")
    print("  逐站损失表 ：results/tables/B04_single_transfer_disruption.csv")
    print("  排名对照   ：results/tables/B08_centrality_vs_loss.csv")
    print("  参数与种子 ：results/tables/B09_run_parameters.json")
    print("  图表       ：results/figures/B_fig1..5_*.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
