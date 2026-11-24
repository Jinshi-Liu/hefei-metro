# 合肥地铁｜换乘消融实验

**如果事故导致一座或多座车站暂时不能换乘，但列车仍正常运行，哪些行程会走不通，哪些还能到但要多花时间？**

- **课程答辩（USTC Beamer）**：[PowerPoint 放映版](docs/ustcbeamer-2.2.2/合肥地铁换乘可达性_答辩.pptx) · [矢量 PDF](docs/ustcbeamer-2.2.2/合肥地铁换乘可达性_答辩.pdf) · [可编辑母稿](docs/ustcbeamer-2.2.2/main.tex) · [20 分钟汇报与复核说明](docs/ustcbeamer-2.2.2/汇报说明.md)。
- [换乘消融实验](docs/换乘消融实验.md)：某站不能换乘时的失联与绕行。
- [夜间换乘消融实验](docs/夜间换乘消融实验.md)：按班次逐步消融上车机会，比较逐线加开及 2、3、6 号线同时加开的可达性。
- [分时客流与关键站预测](docs/分时客流与关键站预测.md)：用公开线路日报、站周边人口和设施估算全网有向 OD，比较 204 站的分时关键性。
- [按出行时间布局的加权网络图](results/metro_weighted_layout.png) · [全线网示意图](results/metro_map.png) · [离线互动地图](results/metro_map.html)（下载后用浏览器打开）
- [分钟线网 GraphML](results/metro.graphml) · [原始边表](data/metro_edges.csv) · [静态结果](results/transfer_ablation/) · [夜间结果](results/night_ablation/)

## 线网与数据

- **范围**：2026-11-23 快照，1–8 号线及 S1；204 座物理站、225 个站点—线路节点、216 条运行边、22 条换乘边，涉及 20 座换乘站。线网为无向拓扑，不含地理轨迹、站外接驳或热门地点。
- **站序与换乘关系**：核对[高德合肥地铁线网](https://www.amap.com/ssr/subway/hefei-3401)。表中列示的连接在基线假定双向可用，不表示运营通道均已实地核实。
- **运行边**：来自 [MetroMan 合肥路线规划](https://www.metroman.cn/en/planner/hefei) 的双向同车逐站时刻。每线每方向各取一趟中午规划行程，用同一趟的相邻站时刻相减，再取双向均值。例如 7 号线紫庐—嵩山路，正向 3 分钟、反向 2 分钟，权重为 **2.5 分钟**。四个时刻与两个来源链接逐行保存在边表。这是规划估计，不是实测。
- **换乘边**：同一物理站不同线路的节点之间连接，基准统一 **5 分钟**；敏感性检验另试 3 和 7 分钟。出行分钟不含初次候车、进出站、拥挤或实时延误。

边表以 `(station_a, line_a)` 和 `(station_b, line_b)` 标识两端，`edge_type` 区分运行／换乘，`sequence` 标记运行区间在本线的顺序，`minutes` 为基准边权。保存的 GraphML 使用 `weight`（分钟），节点含站名、线路和站序，换乘边保留核验标签。

两类可视化都直接读取 GraphML。全线网示意图用 [`data/metro_layout.csv`](data/metro_layout.csv) 中的 [MetroMan 示意坐标](https://www.metroman.cn/en/maps/hefei)排版；这些坐标不参与建网和实验。加权网络图用 NetworkX 的 `kamada_kawai_layout(weight="weight")` 拟合最短出行时间，保留站点—线路节点，用虚线标出换乘边。边越短通常耗时越少，但布局是二维近似，不能用图上距离反推分钟。

## 复现

从仓库根目录运行：

```bash
python -m pip install -r requirements.txt
python -m src.build_network
python -m src.visualize_network
python -m src.visualize_weighted_network
python -m src.transfer_ablation
python -m src.night_ablation
python -m src.dynamic_demand
python -m unittest discover -s tests -v
```

- [建网代码](src/build_network.py)只读一张边表，校验站序和权重，写出 `results/metro.graphml`。
- [实验代码](src/transfer_ablation.py)读取保存的图，输出单站表、多站汇总表、参数与复核摘要、两张图。默认随机序列 100 条；试跑可用 `--repeats 5 --output /path/to/output`。若图中文字显示为方框，请安装适用的中文字体（如 Microsoft YaHei 或 Noto Sans CJK SC）。

- [夜间实验代码](src/night_ablation.py)用[逐班逐站时刻](data/night_trips.csv)与[逐站末班校对表](data/night_last_departures.csv)计算最晚首程、逐线加班结果和[三线组合曲线](results/night_ablation/three_line_reachability.csv)。不使用客流。
- [客流实验代码](src/dynamic_demand.py)读取[客流日报](data/line_ridership.csv)和[地理及历史输入](data/dynamic_demand/)，输出[分时 OD、区间负荷和动态名次](results/dynamic_demand/)。分时数据是估算，并非刷卡记录。

原 1–8 号线、等效站数的 B/C 代码和交付文件可在 Git `b0f0b0b` 查阅。[原研究计划书](docs/合肥轨道交通研究计划书.pdf)和[早期末班车预研摘录](docs/last-train/)仅供追溯。
