#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_shp_baseline_taipei.py — 臺北移植版 A1：淹水潛勢圖 → 區級經驗表 → H2 錨定表

對應臺南 v0.19.1 shp_baseline_corrected_v0191.csv 與 v0.21.2 build_h2_district_conditional_table_v0212.py。
- 輸入：水利署臺北市淹水潛勢圖 10 情境（6h150/250/350、12h200/300/400、24h200/350/500/650），
  每檔 5 個 GRIDCODE 多邊形（1=0.3–0.5 m、2=0.5–1、3=1–2、4=2–3、5=>3 m；<0.3 m 不繪）。
- 深度分級對齊臺南：臺南 GC2..GC6 ＝ 臺北 GC1..GC5 → FD2=GC1、FD3=GC2、FD4=GC3、FD5=GC4+GC5；
  FD1 = 區面積 − 淹水面積（≥0.3 m）。
- 雨級 ↔ 情境群 mapping 與 epsilon floor 完全沿臺南 v0212。
輸出：
  bn_engine/results/taipei_v1/shp_baseline_taipei_v1.csv（欄位同臺南 v0191）
  bn_engine/cpt_priors/h2_district_conditional_table_taipei_v1.json
"""
import csv
import glob
import io
import json
import re
import sys
from datetime import date

import numpy as np
import pyogrio
from shapely import make_valid

from taipei_paths import CPT, OUT, districts_gdf, unzip_dir

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
RAINFALL_SCENARIO_MAP = {"豪雨": ["6h150", "12h200", "24h200"], "大豪雨": ["6h250", "12h300", "24h350"],
                         "超大豪雨": ["6h350", "12h400", "24h500"], "極端降雨": ["24h650"]}
FD_STATES = ["FD1", "FD2", "FD3", "FD4", "FD5"]
EPS = 1e-6
MID = {1: 0.4, 2: 0.75, 3: 1.5, 4: 2.5, 5: 3.5}     # 各級代表深度 m（p90/mean 估計用）
TOP = {1: 0.5, 2: 1.0, 3: 2.0, 4: 3.0, 5: 4.0}


def scen_name(fn):
    m = re.search(r"tp_(\d+)h_r(\d+)", fn)
    return f"{int(m.group(1))}h{m.group(2)}"


def main():
    dist = districts_gdf()
    shp_dir = unzip_dir("flood_potential_taipei_10scenarios_shp.zip")
    rows = []
    for shp in sorted(glob.glob(str(shp_dir / "tp_*_polygon_class_1.shp"))):
        scen = scen_name(shp)
        g = pyogrio.read_dataframe(shp).to_crs(3826)
        g["geometry"] = g.geometry.apply(make_valid)
        for _, d in dist.iterrows():
            town = d.geometry.area
            a = {k: 0.0 for k in range(1, 6)}
            npoly = 0
            for _, f in g.iterrows():
                inter = f.geometry.intersection(d.geometry)
                if not inter.is_empty:
                    a[int(f["GRIDCODE"])] += inter.area
                    npoly += len(getattr(inter, "geoms", [inter]))
            flooded = sum(a.values())
            mean_flooded = sum(MID[k] * a[k] for k in a) / flooded if flooded > 0 else 0.0
            cum, p90 = 0.0, 0.0
            for k in range(1, 6):
                cum += a[k]
                if flooded > 0 and cum >= 0.9 * flooded:
                    p90 = MID[k]
                    break
            maxd = max([TOP[k] for k in a if a[k] > 0], default=0.0)
            rows.append({
                "district": d["district"], "scenario": scen,
                "flooded_area_pct": 100.0 * flooded / town,
                "mean_depth_m": mean_flooded * flooded / town,
                "mean_depth_flooded_only_m": mean_flooded, "max_depth_m": maxd, "p90_depth_m": p90,
                "n_polygons_flooded": npoly, "flooded_area_m2": flooded, "town_area_m2": town,
                "area_d2_m2": a[1], "area_d3_m2": a[2], "area_d4_m2": a[3], "area_d5_m2": a[4], "area_d6_m2": a[5],
            })
        print(scen, {r["district"]: round(r["flooded_area_pct"], 2) for r in rows if r["scenario"] == scen})
    out_csv = OUT / "shp_baseline_taipei_v1.csv"
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- H2 條件經驗表（沿 v0212 district_profile）----
    def profile(rs):
        a_fd = np.zeros(5)
        a_town = a_fl = 0.0
        for r in rs:
            a_town += r["town_area_m2"]
            a_fl += r["flooded_area_m2"]
            a_fd[0] += max(0.0, r["town_area_m2"] - r["flooded_area_m2"])
            a_fd[1] += r["area_d2_m2"]
            a_fd[2] += r["area_d3_m2"]
            a_fd[3] += r["area_d4_m2"]
            a_fd[4] += r["area_d5_m2"] + r["area_d6_m2"]
        p = a_fd / a_fd.sum()
        p = np.maximum(p, EPS)
        p = p / p.sum()
        return p, 100.0 * a_fl / a_town

    by = {}
    for r in rows:
        by.setdefault((r["district"], r["scenario"]), []).append(r)
    table, pooled = {}, {}
    for d in dist["district"]:
        table[d] = {}
        for s, scens in RAINFALL_SCENARIO_MAP.items():
            rs = [x for sc in scens for x in by.get((d, sc), [])]
            p, pct = profile(rs)
            table[d][s] = {"p_FD1_5": [round(x, 6) for x in p], "flooded_area_pct": round(pct, 3), "scenarios": scens}
    for s, scens in RAINFALL_SCENARIO_MAP.items():
        rs = [x for sc in scens for d in dist["district"] for x in by.get((d, sc), [])]
        p, pct = profile(rs)
        pooled[s] = {"p_FD1_5": [round(x, 6) for x in p], "flooded_area_pct": round(pct, 3)}
    out = {
        "version": "taipei_v1", "release_date": date.today().isoformat(),
        "title": "P_shp(H2 | H1, district) — 臺北市士林、北投 2 區 × 4 雨級 × 5 淹水級 條件經驗表（臺南 v0.21.2 同法移植）",
        "source": "水利署臺北市淹水潛勢圖（2016 二次更新版，10 情境，GRIDCODE 1-5 = 0.3-0.5/0.5-1/1-2/2-3/>3 m）",
        "depth_class_mapping": "FD1=區面積−淹水面積(≥0.3 m)；FD2=臺北GC1(0.3-0.5 m)；FD3=GC2(0.5-1 m)；FD4=GC3(1-2 m)；FD5=GC4+GC5(>2 m)；epsilon floor 1e-6",
        "difference_vs_tainan": "臺南潛勢圖 GC1 為 <0.3 m（自分母剔除）、GC2-GC6 對應臺北 GC1-GC5；本表已換算，FD 定義一致",
        "h1_states": list(RAINFALL_SCENARIO_MAP), "h2_states": FD_STATES,
        "rainfall_scenario_mapping": RAINFALL_SCENARIO_MAP,
        "table": table, "two_district_pooled": pooled,
    }
    out_json = CPT / "h2_district_conditional_table_taipei_v1.json"
    json.dump(out, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved", out_csv.name, out_json.name)
    for d in table:
        for s in table[d]:
            print(d, s, table[d][s]["flooded_area_pct"], table[d][s]["p_FD1_5"])


if __name__ == "__main__":
    main()
