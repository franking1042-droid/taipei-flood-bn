#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_shp_baseline_village.py — taipei_v2 A1：淹水潛勢圖 → 里級經驗表 → 里級 H2 錨定表

與 v1 的 build_shp_baseline_taipei.py 完全同法（臺南 v0.19.1 / v0.21.2），只把空間單元從 2 區換成 93 里：
- 潛勢圖 10 情境多邊形（GRIDCODE 1–5）以 geopandas overlay 裁到民政局里界，逐里加總各深度級面積。
- FD 對齊、雨級分群、epsilon floor 與 v1 相同；每里一張 P_shp(FD1..FD5 | 雨級)。
- 另由 93 里加總回推 2 區的表，與 v1 的區級表比對（差異應在浮點誤差內），作為里級裁切的正確性檢核。
輸出：
  bn_engine/results/taipei_v2_village/shp_baseline_village_v2.csv
  bn_engine/cpt_priors/h2_village_conditional_table_taipei_v2.json
"""
import csv
import glob
import io
import json
import sys
from datetime import date

import geopandas as gpd
import numpy as np
import pyogrio
from shapely import make_valid

from build_shp_baseline_taipei import EPS, FD_STATES, MID, RAINFALL_SCENARIO_MAP, TOP, scen_name
from taipei_paths import CPT, OUT_V2, unzip_dir, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


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


def main():
    vil = villages_gdf()
    vil["geometry"] = vil.geometry.make_valid()
    shp_dir = unzip_dir("flood_potential_taipei_10scenarios_shp.zip")
    rows = []
    for shp in sorted(glob.glob(str(shp_dir / "tp_*_polygon_class_1.shp"))):
        scen = scen_name(shp)
        g = pyogrio.read_dataframe(shp).to_crs(3826)
        g["geometry"] = g.geometry.apply(make_valid)
        g = g[["GRIDCODE", "geometry"]].explode(index_parts=False)
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
        ov = gpd.overlay(g, vil[["unit", "geometry"]], how="intersection", keep_geom_type=True)
        ov["a"] = ov.geometry.area
        piv = ov.groupby(["unit", "GRIDCODE"])["a"].sum().unstack(fill_value=0.0).reindex(columns=[1, 2, 3, 4, 5], fill_value=0.0)
        npoly = ov.groupby("unit").size()
        for _, v in vil.iterrows():
            town = v.geometry.area
            a = {k: float(piv.loc[v.unit, k]) if v.unit in piv.index else 0.0 for k in range(1, 6)}
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
                "unit": v.unit, "district": v.district, "village": v.village, "scenario": scen,
                "flooded_area_pct": 100.0 * flooded / town,
                "mean_depth_m": mean_flooded * flooded / town,
                "mean_depth_flooded_only_m": mean_flooded, "max_depth_m": maxd, "p90_depth_m": p90,
                "n_polygons_flooded": int(npoly.get(v.unit, 0)), "flooded_area_m2": flooded, "town_area_m2": town,
                "area_d2_m2": a[1], "area_d3_m2": a[2], "area_d4_m2": a[3], "area_d5_m2": a[4], "area_d6_m2": a[5],
            })
        sub = [r for r in rows if r["scenario"] == scen]
        print(scen, "里有淹水:", sum(1 for r in sub if r["flooded_area_m2"] > 0), "/ 93；最高",
              max(sub, key=lambda r: r["flooded_area_pct"])["unit"], round(max(r["flooded_area_pct"] for r in sub), 2), "%", flush=True)
    out_csv = OUT_V2 / "shp_baseline_village_v2.csv"
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    by = {}
    for r in rows:
        by.setdefault((r["unit"], r["scenario"]), []).append(r)
    table = {}
    for u in vil["unit"]:
        table[u] = {}
        for s, scens in RAINFALL_SCENARIO_MAP.items():
            rs = [x for sc in scens for x in by.get((u, sc), [])]
            p, pct = profile(rs)
            table[u][s] = {"p_FD1_5": [round(x, 6) for x in p], "flooded_area_pct": round(pct, 3), "scenarios": scens}
    # 由里加總回推區級，與 v1 區級表比對
    district_from_villages = {}
    v1 = json.load(open(CPT / "h2_district_conditional_table_taipei_v1.json", encoding="utf-8"))["table"]
    max_diff = 0.0
    for d in sorted(vil["district"].unique()):
        district_from_villages[d] = {}
        units = vil.loc[vil.district == d, "unit"].tolist()
        for s, scens in RAINFALL_SCENARIO_MAP.items():
            rs = [x for u in units for sc in scens for x in by.get((u, sc), [])]
            p, pct = profile(rs)
            district_from_villages[d][s] = {"p_FD1_5": [round(x, 6) for x in p], "flooded_area_pct": round(pct, 3)}
            diff = float(np.max(np.abs(np.array(p) - np.array(v1[d][s]["p_FD1_5"]))))
            max_diff = max(max_diff, diff)
    out = {
        "version": "taipei_v2_village", "release_date": date.today().isoformat(),
        "title": "P_shp(H2 | H1, village) — 臺北市士林、北投 93 里 × 4 雨級 × 5 淹水級 條件經驗表（臺南 v0.21.2 同法，空間單元＝里）",
        "source": "水利署臺北市淹水潛勢圖（2016 二次更新版，10 情境，GRIDCODE 1-5 = 0.3-0.5/0.5-1/1-2/2-3/>3 m）× 民政局里界圖（456 里，取士林 51 里＋北投 42 里）",
        "spatial_unit": "里（unit = 區名＋里名）",
        "depth_class_mapping": "FD1=里面積−淹水面積(≥0.3 m)；FD2=臺北GC1(0.3-0.5 m)；FD3=GC2(0.5-1 m)；FD4=GC3(1-2 m)；FD5=GC4+GC5(>2 m)；epsilon floor 1e-6",
        "h1_states": list(RAINFALL_SCENARIO_MAP), "h2_states": FD_STATES,
        "rainfall_scenario_mapping": RAINFALL_SCENARIO_MAP,
        "n_units": len(table),
        "table": table,
        "district_pooled_from_villages": district_from_villages,
        "check_vs_v1_district_table": {"max_abs_diff_p_FD": round(max_diff, 6), "note": "93 里加總回推 2 區，與 v1 區級錨定表的最大差異（應 <1e-3，差異來自里界與 dissolve 區界的邊界切割）"},
    }
    out_json = CPT / "h2_village_conditional_table_taipei_v2.json"
    json.dump(out, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", out_csv.name, out_json.name, "| 區級回推 vs v1 最大差異", round(max_diff, 6))
    top = sorted(((u, table[u]["超大豪雨"]["flooded_area_pct"]) for u in table), key=lambda x: -x[1])[:12]
    print("超大豪雨 淹水面積% 前 12 里:", top)


if __name__ == "__main__":
    main()
