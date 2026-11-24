"""从仓库的边表和结果表制图，不读取其他演示文稿。"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, patheffects
from matplotlib.collections import LineCollection
from matplotlib.ticker import PercentFormatter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "figures/report"
BLUE, TEAL, RUST = "#004398", "#007D78", "#B04D2F"
INK, SLATE, GRID = "#19334E", "#607488", "#DAE2E9"
PALETTE = dict(zip(("1", "2", "3", "4", "5", "6", "7", "8", "S1"),
                   ("#B95560", "#496EAA", "#1A806A", "#BC7C3E", "#9366A0",
                    "#549AA1", "#A98527", "#7C879E", "#0069AE")))


def rows(path):
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    fonts = {f.name for f in font_manager.fontManager.ttflist}
    face = next((n for n in ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans CN",
                             "PingFang SC", "SimHei") if n in fonts), None)
    if not face:
        raise RuntimeError("绘图需安装中文无衬线字体，例如 Noto Sans CJK SC。")
    plt.rcParams.update({
        "font.family": face, "font.size": 13, "axes.unicode_minus": False,
        "text.color": INK, "axes.labelcolor": INK, "xtick.color": SLATE, "ytick.color": SLATE,
        "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": GRID, "axes.axisbelow": True, "lines.solid_capstyle": "round",
    })


def save(fig, name, transparent=False):
    fig.savefig(OUT / (name + ".pdf"), transparent=transparent,
                metadata={"Creator": "hefei-metro / make_figures.py", "CreationDate": None})
    plt.close(fig)


def routes():
    positions = {r["station"]: (int(r["x"]), -int(r["y"])) for r in rows("data/metro_layout.csv")}
    edges = rows("data/metro_edges.csv")
    transfers = {r["station_a"] for r in edges if r["edge_type"] == "transfer"}
    for cover in (False, True):
        fig, ax = plt.subplots(figsize=(5.9, 3.92) if not cover else (4.8, 4.8))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        ax.set_aspect("equal")
        for line, color in PALETTE.items():
            ride = [r for r in edges if r["edge_type"] == "running" and r["line_a"] == line]
            seg = [[positions[r["station_a"]], positions[r["station_b"]]] for r in ride]
            ax.add_collection(LineCollection(seg, colors="#68AFE3" if cover else color,
                              linewidths=1.7 if cover else 1.9, alpha=.65 if cover else 1))
        x, y = zip(*positions.values())
        ax.scatter(x, y, s=6, c="#9BC9E8" if cover else "white",
                   edgecolors="#9BC9E8" if cover else "#788D9F", linewidth=.45, zorder=3)
        tx, ty = zip(*(positions[s] for s in sorted(transfers)))
        ax.scatter(tx, ty, s=28, facecolors="#164675" if cover else "white",
                   edgecolors="#B9DEEF" if cover else INK, linewidth=1.1, zorder=4)
        if not cover:
            # Offsets are annotations on the published schematic, not geographic coordinates.
            for station, label, dx, dy, align in [
                ("新桥2号航站楼", "新桥 2 号航站楼", -9, 13, "center"),
                ("合肥西站", "合肥西站", -13, -19, "right"),
                ("合肥南站", "合肥南站", 20, 6, "left"),
                ("紫庐", "紫庐", 18, -4, "left"),
                ("繁华大道", "繁华大道", -11, -15, "right"),
            ]:
                ax.annotate(label, positions[station], xytext=(dx, dy), textcoords="offset points",
                            ha=align, va="center", fontsize=12.5, color=INK,
                            path_effects=[patheffects.withStroke(linewidth=3, foreground="white")],
                            arrowprops=dict(arrowstyle="-", color=SLATE, lw=.65), zorder=5)
        ax.autoscale()
        ax.margins(.045)
        ax.axis("off")
        save(fig, "cover-network" if cover else "network", transparent=cover)


def ranks():
    stations = rows("results/transfer_ablation/single_station.csv")
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    fig.subplots_adjust(left=.12, right=.97, top=.94, bottom=.21)
    ax.set(xlim=(0, 21), ylim=(21, 0), xticks=[1, 5, 10, 15, 20], yticks=[1, 5, 10, 15, 20],
           xlabel="原始介数名次", ylabel="单站损失名次")
    ax.grid(color=GRID, lw=.6)
    ax.plot([1, 20], [1, 20], color="#97A7B6", lw=1.2, ls="--")
    labels = {"合肥西站": (-10, -6, "right", RUST), "合肥南站": (8, 2, "left", TEAL),
              "洪岗": (8, -5, "left", BLUE)}
    for r in stations:
        x, y = int(r["betweenness_rank"]), int(r["loss_rank"])
        s = r["station"]
        ax.scatter(x, y, s=75 if s in labels else 40,
                   c=labels[s][-1] if s in labels else "#829AB0", edgecolors="white", zorder=3)
        if s in labels:
            dx, dy, align, col = labels[s]
            ax.annotate(s, (x, y), (dx, dy), textcoords="offset points", ha=align, va="center",
                        fontsize=12.5, color=col, path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])
    save(fig, "rank-comparison")


def simultaneous():
    table = rows("results/transfer_ablation/multi_station.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.05))
    fig.subplots_adjust(left=.067, right=.984, top=.80, bottom=.235, wspace=.26)
    for ax, (metric, title) in zip(axes, [("unreachable_share", "不可达站点对比例"),
                                         ("efficiency_ratio", "相对出行效率")]):
        ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=5)
        for strategy, color, style, label in [
            ("random", SLATE, "--", "随机顺序（100 次均值）"),
            ("betweenness", TEAL, "-", "原始介数顺序"), ("single_loss", RUST, "-", "单站损失顺序"),
        ]:
            rr = sorted((r for r in table if r["strategy"] == strategy), key=lambda r: int(r["k"]))
            x = [int(r["k"]) for r in rr]
            if strategy == "random":
                ax.fill_between(x, [float(r[metric+"_p025"]) for r in rr],
                                [float(r[metric+"_p975"]) for r in rr], color="#DCE4EC", linewidth=0)
            ax.plot(x, [float(r[metric+"_mean"]) for r in rr], style, color=color, lw=2, label=label)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set(xlim=(0,20), xticks=[0,5,10,15,20], xlabel="不能换乘的站数")
        ax.grid(axis="y", color=GRID, lw=.7)
    axes[0].set(ylim=(-.025,.90), yticks=[0,.2,.4,.6,.8])
    axes[1].set(ylim=(.32,1.03), yticks=[.4,.6,.8,1.])
    axes[0].plot(3,.1892,"o",color=RUST,ms=5)
    axes[0].annotate("18.92%", (3,.1892), xytext=(7,13), textcoords="offset points", color=RUST, fontsize=12)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.54,1.005),
               ncol=3, frameon=False, fontsize=12, columnspacing=1.6)
    save(fig, "closure-curves")


def detour():
    """显示介数顺序的全程走势，并标出固定样本复核所用的一步。"""
    base = "results/transfer_ablation"
    cohort = json.loads((ROOT / base / "summary.json").read_text(encoding="utf-8"))["fixed_cohort"]
    series = sorted((r for r in rows(base + "/multi_station.csv") if r["strategy"] == cohort["strategy"]),
                    key=lambda r: int(r["k"]))
    x = [int(r["k"]) for r in series]
    y = [float(r["mean_added_min_reachable_mean"]) for r in series]
    k0, k1 = cohort["before_k"], cohort["after_k"]
    a, b = y[x.index(k0)], y[x.index(k1)]
    fig, ax = plt.subplots(figsize=(5.95, 3.75))
    fig.subplots_adjust(left=.14, right=.96, top=.93, bottom=.20)
    ax.grid(axis="y", color=GRID, lw=.7)
    ax.axvspan(k0, k1, color="#F6E5DF", zorder=0)
    ax.plot(x, y, color=TEAL, lw=2.4)
    ax.plot([k0, k1], [a, b], "o-", color=RUST, lw=2.8, ms=6)
    for k, val, offset in [(k0, a, (-33, 8)), (k1, b, (6, 6))]:
        ax.annotate(f"{val:.2f}", (k, val), xytext=offset, textcoords="offset points",
                    color=RUST, fontsize=14, weight="bold",
                    path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])
    ax.set(xlim=(0, max(x)), ylim=(0, max(y)*1.22), xticks=[0, 5, 10, 15, 20],
           xlabel="不能换乘的站数（按原始介数顺序）", ylabel="仍可达 OD 平均额外分钟")
    save(fig, "detour")


def campus_rows():
    """从基线列抽取固定起点的首程截止时刻，不把站外接驳计为轨道行程。"""
    table = rows("results/night_ablation/latest_boarding.csv")
    latest = {(r["origin"], r["destination"]): r["latest_boarding"] for r in table}
    origins = ["北城高铁站", "新桥2号航站楼", "合肥火车站", "合肥南站", "中国科大东区", "图书馆"]
    destinations = ["科大先研院", "复兴集"]  # 列顺序与 main.tex 的表头一致
    lines = [" & ".join([o, *(latest[o, d] for d in destinations)]) + r" \\" for o in origins]
    macro = "\\newcommand{\\campusrows}{%\n" + "\n".join(lines) + "%\n}\n"
    (OUT / "campus-boarding.tex").write_text(macro, encoding="utf-8")


def night():
    rr = rows("results/night_ablation/reachability.csv")
    def minute(t):
        h, m = map(int, t.split(":"))
        return h*60+m
    x = np.array([minute(r["time"]) for r in rr])
    y = np.array([int(r["baseline"]) for r in rr]) / max(int(r["baseline"]) for r in rr)
    fig, ax = plt.subplots(figsize=(6.15, 3.45))
    fig.subplots_adjust(left=.125, right=.955, top=.91, bottom=.23)
    ax.fill_between(x, y, step="post", color="#E4EFF9")
    ax.step(x, y, where="post", color=BLUE, lw=2.6)
    ax.axhline(.5, color=SLATE, ls="--", lw=1)
    i = next(i for i,v in enumerate(y) if v < .5)
    ax.scatter(x[i], y[i], color=RUST, s=54, zorder=3)
    ax.annotate(rr[i]["time"], (x[i],y[i]), (10,9), textcoords="offset points", color=RUST, weight="bold")
    ticks = ["21:00","22:00","23:00","24:00"]
    ax.set(xlim=(x[0],x[-1]), ylim=(-.015,1.035), xticks=[minute(t) for t in ticks],
           xticklabels=ticks, yticks=[0,.25,.5,.75,1], xlabel="起点站台就绪时刻", ylabel="可达 OD 比例")
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.grid(axis="y", color=GRID, lw=.6)
    save(fig,"night-coverage")


def gains():
    rr = rows("results/night_ablation/line_gain.csv")
    rr.sort(key=lambda r: -int(r["total_window_gain_od_min"]))
    fig, ax = plt.subplots(figsize=(5.4, 3.62))
    fig.subplots_adjust(left=.13, right=.86, top=.97, bottom=.20)
    vals = [int(r["total_window_gain_od_min"]) for r in rr]
    ax.barh(range(len(rr)),vals, height=.61,
            color=[BLUE if i==0 else TEAL if i==1 else "#A1B6CA" for i in range(len(rr))])
    for i,v in enumerate(vals):
        ax.text(v+1200,i,f"{v:,}", va="center", fontsize=12)
    ax.set(yticks=range(len(rr)), yticklabels=[r["line"] for r in rr], xlim=(0,95000),
           xticks=[0,40000,80000], xticklabels=["0","40,000","80,000"],
           xlabel="全晚窗口增量（OD·分钟）", ylabel="线路")
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, lw=.6)
    save(fig,"line-gains")


def night_three_lines():
    table = rows("results/night_ablation/three_line_reachability.csv")
    x = [int(r["time"][:2])*60 + int(r["time"][3:]) for r in table]
    fig, ax = plt.subplots(figsize=(7.3, 3.85))
    fig.subplots_adjust(left=.10, right=.96, top=.78, bottom=.20)
    for key, col, style, label in [
        ("baseline", SLATE, "--", "原班次"),
        ("plus_2", "#855AA0", "-", "只加 2 号线"),
        ("plus_3", RUST, "-", "只加 3 号线"),
        ("plus_6", TEAL, "-", "只加 6 号线"),
        ("plus_2_3_6", BLUE, "-", "2、3、6 号线同时加开"),
    ]:
        ax.step(x, [int(r[key])/10000 for r in table], where="post", color=col, linestyle=style,
                lw=2.7 if key == "plus_2_3_6" else 1.5, label=label)
    for t in (22*60+30, 23*60):
        ax.axvline(t, color=GRID, ls=":", lw=1.2)
    ticks = range(22*60+15, 23*60+46, 15)
    ax.set(xlim=(ticks[0],ticks[-1]), xticks=ticks,
           xticklabels=[f"{t//60}:{t%60:02d}" for t in ticks],
           ylim=(0,3.1), xlabel="起点站台就绪时刻", ylabel="可达 OD（万对）")
    ax.grid(axis="y", color=GRID, lw=.65)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", bbox_to_anchor=(.54,.99),
               ncol=3, fontsize=11, frameon=False, columnspacing=1.35)
    save(fig, "night-three-lines")


def dynamic_ranking():
    table = rows("results/dynamic_demand/station_ranks.csv")
    hours = sorted({r["hour"] for r in table})
    focus = ("08:00", "12:00", "18:00")
    lookup = {(r["station"], r["hour"]): r for r in table}
    triplets = {r["station"]: [int(lookup[r["station"], h]["rank"]) for h in focus]
                for r in table if r["hour"] == focus[0]}
    # Show all top-five stations at the three representative hours and a mover from ranks 6–30.
    names = sorted((s for s, r in triplets.items() if min(r) <= 5),
                   key=lambda s: (min(triplets[s]), int(lookup[s, focus[0]]["rank"]), s))
    movers = [(s, r) for s, r in triplets.items() if 5 < min(r) <= 30 and max(r) > min(r)]
    if movers:
        names.append(min(movers, key=lambda item: (min(item[1])-max(item[1]), min(item[1]), item[0]))[0])
    arr = np.array([[int(lookup[s, h]["rank"]) for h in hours] for s in names])
    fig, ax = plt.subplots(figsize=(10.8, max(2.75, 1.23 + .31*len(names))))
    fig.subplots_adjust(left=.155, right=.97, top=.80, bottom=.20)
    from matplotlib.colors import LinearSegmentedColormap
    palette = LinearSegmentedColormap.from_list("rank", ["#004398", "#78AECF", "#E8F0F7", "#F6F8FA"])
    ax.imshow(np.minimum(12, arr), cmap=palette, vmin=1, vmax=12, aspect="auto")
    labels = [h[:2]+":00" if i%2 == 0 or h in focus else "" for i, h in enumerate(hours)]
    ax.set(xticks=range(len(hours)), xticklabels=labels, yticks=range(len(names)), yticklabels=names)
    ax.xaxis.tick_top()
    ax.tick_params(axis="both", length=0, pad=5, labelsize=10)
    ax.set_xticks(np.arange(-.5, len(hours)), minor=True)
    ax.set_yticks(np.arange(-.5, len(names)), minor=True)
    ax.grid(which="minor", color="white", lw=.8)
    ax.tick_params(which="minor", length=0)
    for i, s in enumerate(names):
        for j, h in enumerate(hours):
            rank = arr[i,j]
            ax.text(j, i, str(rank), va="center", ha="center", color="white" if rank <= 3 else INK,
                    fontsize=10.3, weight="bold" if h in focus else "normal")
        topo = lookup[s,hours[0]]["topology_rank"]
        ax.text(-1.10, i, topo, va="center", ha="center", color=SLATE, fontsize=10, clip_on=False)
    ax.set_xlim(-1.62, len(hours)-.5)
    ax.text(-1.10,-.83,"静态",va="bottom",ha="center",color=SLATE,fontsize=10)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(.145,.04, "按最早出发小时分组 · 格内数字是全网名次；颜色越深，名次越靠前",
             fontsize=10.2, color=SLATE)
    save(fig,"dynamic-ranking")


if __name__ == "__main__":
    setup()
    routes()
    ranks()
    simultaneous()
    detour()
    campus_rows()
    night()
    gains()
    night_three_lines()
    dynamic_ranking()
