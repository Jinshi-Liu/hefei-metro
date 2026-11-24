"""用已下载的高德 JSON、历史客流 JS、WorldPop 栅格和 OSM PBF 生成实验三输入。"""
import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .build_network import ROOT, build_weighted_network

OUT = ROOT / "data/dynamic_demand"
RADIUS_M = 800
EARTH_M = 6_371_000
AMAP = "https://map.amap.com/service/subway?srhdata=3401_drw_hefei.json"
HISTORY = "https://luowenpeng.com/hf-metro-passenger-data.js"
WORLDPOP_ID = "chn_pop_2025_CN_100m_R2025A_v1"
WORLDPOP = "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/CHN/v1/100m/constrained/" + WORLDPOP_ID + ".tif"
OSM = "https://download.openstreetmap.fr/extracts/asia/china/anhui-latest.osm.pbf"
POI_TYPES = ("office", "education", "hospital", "retail", "hub")


def save_rows(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def gcj_to_wgs(lon, lat):
    """数值反解高德 GCJ-02 加偏；用于百米尺度的地理匹配，不作测绘。"""
    def forward(lo, la):
        x, y = lo - 105, la - 35
        s = math.sin
        dx = 300 + x + 2*y + .1*x*x + .1*x*y + .1*math.sqrt(abs(x))
        dy = -100 + 2*x + 3*y + .2*y*y + .1*x*y + .2*math.sqrt(abs(x))
        common = (20*s(6*x*math.pi) + 20*s(2*x*math.pi))*2/3
        dx += common + (20*s(x*math.pi)+40*s(x*math.pi/3)
                        +150*s(x*math.pi/12)+300*s(x*math.pi/30))*2/3
        dy += common + (20*s(y*math.pi)+40*s(y*math.pi/3)
                        +160*s(y*math.pi/12)+320*s(y*math.pi/30))*2/3
        rad = math.radians(la)
        e2 = .006693421622965943
        magic = 1-e2*s(rad)**2
        a = 6378245
        return (lo + math.degrees(dx*math.sqrt(magic)/(a*math.cos(rad))),
                la + math.degrees(dy*magic**1.5/(a*(1-e2))))
    lo, la = lon, lat
    for _ in range(5):
        x, y = forward(lo, la)
        lo += lon-x
        la += lat-y
    return lo, la


def on_sphere(lon, lat):
    x, y = map(np.radians, (lon, lat))
    return np.column_stack((np.cos(x)*np.cos(y), np.sin(x)*np.cos(y), np.sin(y))) * EARTH_M


def stations_from_amap(path):
    reference = defaultdict(set)
    for attrs in build_weighted_network().nodes.values():
        reference[attrs["station"]].add(attrs["line"])
    memberships, coords = defaultdict(set), defaultdict(set)
    for line in json.loads(path.read_text(encoding="utf-8-sig"))["l"]:
        lid = re.fullmatch(r"(\d+)号线|(S\d+)线", line["ln"])
        if not lid:
            raise ValueError(f"未知线路名：{line['ln']}")
        for station in line["st"]:
            if station.get("su") != "1":
                continue
            name = station["n"]
            memberships[name].add(lid[1] or lid[2])
            coords[name].add(tuple(map(float, station["sl"].split(","))))
    if memberships != reference:
        raise ValueError("高德站序快照与项目参考图的站名/线路不一致，禁止隐式丢站")
    output = []
    for i, name in enumerate(sorted(reference), 1):
        points = sorted(coords[name])
        lon, lat = gcj_to_wgs(*np.mean(points, axis=0))
        if not (116.7 < lon < 118 and 31.4 < lat < 32.5):
            raise ValueError(f"合肥站点坐标异常：{name} {(lon, lat)}")
        output.append(dict(station_id=f"HF{i:03d}", station=name, lines=";".join(sorted(reference[name])),
                           wgs84_lon=round(lon, 7), wgs84_lat=round(lat, 7)))
    return output


def aggregate_population(path, bbox, tree, n):
    import rasterio
    from rasterio.windows import from_bounds

    with rasterio.open(path) as f:
        if f.crs.to_epsg() != 4326:
            raise ValueError("预期 WorldPop WGS84 坐标")
        window = from_bounds(*bbox, transform=f.transform).round_offsets().round_lengths()
        pop = f.read(1, window=window, masked=True)
        transform = f.window_transform(window)
        iy, ix = np.where((~np.ma.getmaskarray(pop)) & (pop.data > 0))
        lon, lat = transform * (ix + .5, iy + .5)
    dist, where = tree.query(on_sphere(lon, lat))
    keep = dist <= RADIUS_M
    return np.bincount(where[keep], weights=pop.data[iy[keep], ix[keep]], minlength=n)


def poi_type(tags):
    amenity = tags.get("amenity")
    if ((tags.get("railway") == "station"
         and tags.get("station") not in {"subway", "light_rail", "tram"}
         and tags.get("subway") != "yes")
            or tags.get("aeroway") == "terminal"):
        return "hub"
    if amenity in {"university", "college"}:
        return "education"
    if amenity == "hospital":
        return "hospital"
    if tags.get("shop") in {"mall", "department_store", "supermarket"}:
        return "retail"
    if tags.get("office") not in {None, "no", "vacant", "abandoned"}:
        return "office"
    return None


def aggregate_poi(path, bbox, tree, n):
    import osmium

    west, south, east, north = bbox

    class Sites(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.records = []

        def add(self, kind, tags, x, y):
            if west <= x <= east and south <= y <= north:
                name = tags.get("name:zh") or tags.get("name") or ""
                self.records.append((kind, name.strip().casefold(), x, y))

        def node(self, node):
            kind = poi_type(node.tags)
            if kind and node.location.valid():
                self.add(kind, node.tags, node.lon, node.lat)

        def way(self, way):
            kind = poi_type(way.tags)
            if kind:
                coords = [(p.lon, p.lat) for p in way.nodes if p.location.valid()]
                if coords:
                    self.add(kind, way.tags, *np.mean(sorted(set(coords)), axis=0))

    reader = osmium.io.Reader(str(path))
    try:
        timestamp = reader.header().get("osmosis_replication_timestamp")
    finally:
        reader.close()
    sites = Sites()
    sites.apply_file(str(path), locations=True)
    counts = {k: np.zeros(n, dtype=int) for k in POI_TYPES}
    if not sites.records:
        raise ValueError("OSM 文件没有匹配的站点周边设施")
    kinds, names, lon, lat = zip(*sorted(sites.records))
    xyz = on_sphere(np.array(lon, dtype=float), np.array(lat, dtype=float))
    dist, where = tree.query(xyz)
    seen = defaultdict(list)
    for i in np.flatnonzero(dist <= RADIUS_M):
        # 点与面都可能标注同一个场所；同类同名、150 m 内合并。
        key = kinds[i], names[i]
        if names[i] and any(np.linalg.norm(xyz[i]-p) <= 150 for p in seen[key]):
            continue
        if names[i]:
            seen[key].append(xyz[i])
        counts[kinds[i]][where[i]] += 1
    return counts, timestamp


def historical_rows(path):
    content = path.read_text(encoding="utf-8-sig")
    start = re.search(r"var\s+hfMetroPassengerData\s*=\s*", content)
    if not start:
        raise ValueError("未知客流数据库格式")
    records, _ = json.JSONDecoder().raw_decode(content[start.end():])
    rows = []
    # 仅存所用训练窗口。节日及调休由预测脚本排除，保留在原始摘录表中便于查核。
    for r in records:
        if date(2026, 9, 1) <= date.fromisoformat(r["date"]) <= date(2026, 11, 4):
            rows.append({"service_date": r["date"], "network_10k": r["total"],
                         **{str(i): r.get(f"line{i}", "") for i in range(1, 9)}})
    if len(rows) < 50:
        raise ValueError("历史日客流训练样本不全")
    return rows


def manifest_file(path, url):
    with path.open("rb") as f:
        return {"url": url, "sha256": hashlib.file_digest(f, "sha256").hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("amap", "ridership-js", "pop-tif", "osm-pbf"):
        parser.add_argument("--"+flag, type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    data = stations_from_amap(args.amap)
    lon = np.array([r["wgs84_lon"] for r in data])
    lat = np.array([r["wgs84_lat"] for r in data])
    tree = cKDTree(on_sphere(lon, lat))
    bbox = lon.min()-.015, lat.min()-.015, lon.max()+.015, lat.max()+.015
    pop = aggregate_population(args.pop_tif, bbox, tree, len(data))
    poi, osm_timestamp = aggregate_poi(args.osm_pbf, bbox, tree, len(data))
    for i, r in enumerate(data):
        r["population_worldpop"] = round(pop[i], 3)
        r.update({f"poi_{k}": v[i] for k, v in poi.items()})
    history = historical_rows(args.ridership_js)
    args.output.mkdir(parents=True, exist_ok=True)
    save_rows(args.output / "station_features.csv", data)
    save_rows(args.output / "ridership_history.csv", history)
    manifest = dict(radius_m=RADIUS_M, overlap="nearest station only",
                    coordinates=manifest_file(args.amap, AMAP), history=manifest_file(args.ridership_js, HISTORY),
                    worldpop=manifest_file(args.pop_tif, WORLDPOP),
                    osm={**manifest_file(args.osm_pbf, OSM), "snapshot_utc": osm_timestamp})
    (args.output / "source_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"{len(data)} stations, {len(history)} daily records, {pop.sum():,.0f} population proxy, "
          f"{sum(v.sum() for v in poi.values())} OSM facilities; {args.output}")


if __name__ == "__main__":
    main()
