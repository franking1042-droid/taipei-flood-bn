#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_E_exposure_taipei.py — 臺北移植版 B2：潛勢區分層暴露存量（E 節點）＋ 以臺南五分位邊界離散化

方法完全沿臺南 v0.21.3 compute_E_exposure_v0213.py / discretize_E_nodes_v0213.py：
  - 潛勢區：24h350、24h500 情境，深度 ≥0.3 m（臺北 GRIDCODE 1-5 全部），dissolve。
  - 建築暴露：LULC LCODE_C1=05 多邊形之代表點落在潛勢區內 → flooded_building_area_pct；農地 01 同法。
  - 人口分層沿建築分布：E_pop_x = pop_x × flooded_building_area_pct。
  - 離散化：臺南 37 區「情境內五分位」沒有絕對切點；為保持兩市可比，臺北值以
    臺南 E_node_levels_v0213.csv 各級的邊界（level k 最大值與 level k+1 最小值之中點）歸級。
    FloodZone_Vulnerable_Ratio = (E_65p + E_0_14 + E_disability) / pop_total（v0214a 定義）。
輸出：bn_engine/results/taipei_v1/E_stratified_exposure_taipei_v1.csv、E_node_levels_taipei_v1.csv
"""
import glob
import io
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from shapely import STRtree, make_valid
from shapely.ops import unary_union

from taipei_common import district_population_strata
from taipei_paths import DISTRICTS, OUT, REF, districts_gdf, unzip_dir

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SCENARIOS = ["24h350", "24h500"]
LAB = {1: "very_low", 2: "low", 3: "medium", 4: "high", 5: "very_high"}


def tainan_boundaries():
    """{(node, scenario): [cut1..cut4]}：臺南 level k 最大值與 k+1 最小值的中點。"""
    e = pd.read_csv(REF / "E_node_levels_v0213.csv", encoding="utf-8-sig")
    vr = pd.read_csv(REF / "FloodZone_Vulnerable_Ratio_levels_v0214a.csv", encoding="utf-8-sig")
    e = pd.concat([e, vr], ignore_index=True)
    cuts = {}
    for (node, sc), g in e.groupby(["node", "scenario"]):
        gg = g.groupby("level")["value"].agg(["min", "max"])
        c = []
        for k in range(1, 5):
            hi = gg.loc[k, "max"] if k in gg.index else np.nan
            lo = gg.loc[k + 1, "min"] if k + 1 in gg.index else np.nan
            c.append(float(np.nanmean([hi, lo])))
        cuts[(node, sc)] = c
    return cuts


def level_of(v, cuts):
    for i, c in enumerate(cuts):
        if v <= c:
            return i + 1
    return 5


def main():
    dist = districts_gdf()
    strata = district_population_strata()
    shp_dir = unzip_dir("flood_potential_taipei_10scenarios_shp.zip")
    lulc_dir = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    lulc = gpd.read_file(glob.glob(str(lulc_dir / "*.shp"))[0], encoding="utf-8")
    lulc["c1"] = lulc["LCODE_C1"].astype(str).str.zfill(2)
    lulc = lulc[lulc["c1"].isin(["01", "05"])].reset_index(drop=True)
    lulc["a"] = lulc.geometry.area
    pts = lulc.representative_point()
    rows = []
    for sc in SCENARIOS:
        f = pyogrio.read_dataframe(glob.glob(str(shp_dir / f"tp_{sc[:2]}h_r{sc[3:]}_*.shp"))[0]).to_crs(3826)
        zone = make_valid(unary_union([make_valid(x) for x in f.geometry]))
        parts = list(getattr(zone, "geoms", [zone]))
        tree = STRtree(parts)
        li, _ = tree.query(pts.values, predicate="within")
        inz = np.zeros(len(lulc), bool)
        inz[np.unique(li)] = True
        lulc["inz"] = inz
        for d in DISTRICTS:
            sub = lulc[lulc["TNAME"] == d]
            bld = sub[sub.c1 == "05"]
            agr = sub[sub.c1 == "01"]
            b_all, b_fl = bld["a"].sum() / 1e6, bld.loc[bld.inz, "a"].sum() / 1e6
            a_all, a_fl = agr["a"].sum() / 1e6, agr.loc[agr.inz, "a"].sum() / 1e6
            pct_b = 100 * b_fl / b_all if b_all else 0.0
            pct_a = 100 * a_fl / a_all if a_all else 0.0
            geom = dist.loc[dist.district == d, "geometry"].iloc[0]
            fl_pct = 100 * zone.intersection(geom).area / geom.area
            s = strata.loc[d]
            r = {"district": d, "scenario": sc, "flooded_area_pct": round(fl_pct, 2),
                 "building_area_km2": round(b_all, 4), "flooded_building_area_km2": round(b_fl, 4),
                 "flooded_building_area_pct": round(pct_b, 2),
                 "agri_area_km2": round(a_all, 4), "flooded_agri_area_km2": round(a_fl, 4),
                 "flooded_agri_area_pct": round(pct_a, 2),
                 "pop_total": int(s.pop_total), "pop_65p": int(s.pop_65p), "pop_0_14": int(s.pop_0_14),
                 "pop_alone_elderly": int(s.pop_alone_elderly), "pop_disability": int(s.pop_disability)}
            for k in ["total", "65p", "0_14", "alone_elderly", "disability"]:
                r[f"E_pop_{k}"] = round(r[f"pop_{k}"] * pct_b / 100, 1)
            rows.append(r)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "E_stratified_exposure_taipei_v1.csv", index=False, encoding="utf-8-sig")
    print(res.T.to_string())
    cuts = tainan_boundaries()
    NODES = {
        "FloodZone_Population_Ratio": res.E_pop_total / res.pop_total,
        "FloodZone_Elderly_Count": res.E_pop_65p,
        "FloodZone_ElderlyAlone_Count": res.E_pop_alone_elderly,
        "FloodZone_Disability_Count": res.E_pop_disability,
        "FloodZone_Children_Count": res.E_pop_0_14,
        "FloodZone_Building_Pct": res.flooded_building_area_pct,
        "FloodZone_Agri_km2": res.flooded_agri_area_km2,
        "FloodZone_Vulnerable_Ratio": (res.E_pop_65p + res.E_pop_0_14 + res.E_pop_disability) / res.pop_total,
    }
    lv = []
    for node, vals in NODES.items():
        for (_, r), v in zip(res.iterrows(), vals):
            c = cuts[(node, r.scenario)]
            k = level_of(v, c)
            lv.append({"district": r.district, "scenario": r.scenario, "node": node, "value": round(float(v), 4),
                       "level": k, "level_label": LAB[k], "tainan_cuts": "|".join(f"{x:.4g}" for x in c)})
    lv = pd.DataFrame(lv)
    lv.to_csv(OUT / "E_node_levels_taipei_v1.csv", index=False, encoding="utf-8-sig")
    print(lv.pivot_table(index=["node"], columns=["district", "scenario"], values="level_label", aggfunc="first").to_string())


if __name__ == "__main__":
    main()
