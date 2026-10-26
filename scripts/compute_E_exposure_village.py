#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_E_exposure_village.py — taipei_v2 B2：里級潛勢區分層暴露存量（8 個 FloodZone_* E 節點）

方法沿臺南 v0.21.3 與 v1 compute_E_exposure_taipei.py，空間單元改為 93 里：
  - 潛勢區：24h350、24h500 情境，深度 ≥0.3 m，dissolve。
  - 建築／農地暴露：LULC 05／01 多邊形的代表點落在哪個里（point-in-polygon）、是否落在潛勢區內。
  - 人口分層沿建築分布：E_pop_x = 里 pop_x × 里 flooded_building_area_pct（pop_x 見 village_population_strata）。
  - 離散化（基線）：沿用 v1 的「臺南 37 區各級邊界中點」絕對切點（`level`／`level_label`），語意＝放進臺南 37 區分布屬第幾級。
    計數型節點（*_Count、Agri_km2）在里尺度數值天生較小，多數里會落在 very_low；這是「單位變小、絕對暴露量變小」的真實結果。
  - 離散化（替代）：`level_q93`＝士林北投 93 里「情境內」相對分級（0 暴露 → 1；非 0 者依四分位 → 2–5），
    對應臺南 v0213「情境內五分位」的做法，供敏感度比較，推論不用。
輸出：bn_engine/results/taipei_v2_village/E_stratified_exposure_village_v2.csv、E_node_levels_village_v2.csv
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

from compute_E_exposure_taipei import LAB, SCENARIOS, level_of, tainan_boundaries
from taipei_common import village_population_strata
from taipei_paths import OUT_V2, unzip_dir, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def q93_level(vals):
    """0 → 1；非 0 依四分位 → 2..5（同情境、同節點、93 里內的相對位置）。"""
    v = np.asarray(vals, dtype=float)
    out = np.ones(len(v), dtype=int)
    nz = v > 0
    if nz.sum() >= 4:
        q = np.quantile(v[nz], [0.25, 0.5, 0.75])
        out[nz] = 2 + np.searchsorted(q, v[nz], side="right")
    elif nz.sum() > 0:
        out[nz] = 3
    return out


def main():
    vil = villages_gdf()
    vil["geometry"] = vil.geometry.make_valid()
    strata = village_population_strata()
    shp_dir = unzip_dir("flood_potential_taipei_10scenarios_shp.zip")
    lulc_dir = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    lulc = gpd.read_file(glob.glob(str(lulc_dir / "*.shp"))[0], encoding="utf-8").to_crs(3826)
    lulc["c1"] = lulc["LCODE_C1"].astype(str).str.zfill(2)
    lulc = lulc[lulc["c1"].isin(["01", "05"])].reset_index(drop=True)
    lulc["a"] = lulc.geometry.area
    pts = gpd.GeoDataFrame(lulc[["c1", "a"]], geometry=lulc.representative_point(), crs=3826)
    pts = gpd.sjoin(pts, vil[["unit", "geometry"]], how="left", predicate="within").drop(columns="index_right")
    n_out = int(pts["unit"].isna().sum())
    pts = pts[pts["unit"].notna()].copy()
    rows = []
    for sc in SCENARIOS:
        f = pyogrio.read_dataframe(glob.glob(str(shp_dir / f"tp_{sc[:2]}h_r{sc[3:]}_*.shp"))[0]).to_crs(3826)
        zone = make_valid(unary_union([make_valid(x) for x in f.geometry]))
        parts = list(getattr(zone, "geoms", [zone]))
        tree = STRtree(parts)
        li, _ = tree.query(pts.geometry.values, predicate="within")
        inz = np.zeros(len(pts), bool)
        inz[np.unique(li)] = True
        pts["inz"] = inz
        for _, v in vil.iterrows():
            sub = pts[pts.unit == v.unit]
            bld = sub[sub.c1 == "05"]
            agr = sub[sub.c1 == "01"]
            b_all, b_fl = bld["a"].sum() / 1e6, bld.loc[bld.inz, "a"].sum() / 1e6
            a_all, a_fl = agr["a"].sum() / 1e6, agr.loc[agr.inz, "a"].sum() / 1e6
            pct_b = 100 * b_fl / b_all if b_all else 0.0
            pct_a = 100 * a_fl / a_all if a_all else 0.0
            fl_pct = 100 * zone.intersection(v.geometry).area / v.geometry.area
            s = strata.loc[v.unit]
            r = {"unit": v.unit, "district": v.district, "village": v.village, "scenario": sc,
                 "flooded_area_pct": round(fl_pct, 2),
                 "building_area_km2": round(b_all, 4), "flooded_building_area_km2": round(b_fl, 4),
                 "flooded_building_area_pct": round(pct_b, 2),
                 "agri_area_km2": round(a_all, 4), "flooded_agri_area_km2": round(a_fl, 4),
                 "flooded_agri_area_pct": round(pct_a, 2),
                 "pop_total": int(s.pop_total), "pop_65p": int(s.pop_65p), "pop_0_14": int(s.pop_0_14),
                 "pop_alone_elderly": float(s.pop_alone_elderly), "pop_disability": float(s.pop_disability)}
            for k in ["total", "65p", "0_14", "alone_elderly", "disability"]:
                r[f"E_pop_{k}"] = round(r[f"pop_{k}"] * pct_b / 100, 2)
            rows.append(r)
    res = pd.DataFrame(rows)
    res.to_csv(OUT_V2 / "E_stratified_exposure_village_v2.csv", index=False, encoding="utf-8-sig")
    print("LULC 代表點落在 93 里之外（捨棄）:", n_out)
    for sc in SCENARIOS:
        sub = res[res.scenario == sc]
        print(sc, "有建築暴露的里:", int((sub.flooded_building_area_pct > 0).sum()), "/ 93；建築暴露% 前 8:",
              sub.nlargest(8, "flooded_building_area_pct")[["unit", "flooded_building_area_pct"]].values.tolist())
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
        vals = np.asarray(vals, dtype=float)
        for sc in SCENARIOS:
            m = (res.scenario == sc).values
            q = q93_level(vals[m])
            for (i, r), v, qq in zip(res[m].iterrows(), vals[m], q):
                c = cuts[(node, sc)]
                k = level_of(v, c)
                lv.append({"unit": r.unit, "district": r.district, "village": r.village, "scenario": sc, "node": node,
                           "value": round(float(v), 4), "level": k, "level_label": LAB[k],
                           "level_q93": int(qq), "level_q93_label": LAB[int(qq)],
                           "tainan_cuts": "|".join(f"{x:.4g}" for x in c)})
    lv = pd.DataFrame(lv)
    lv.to_csv(OUT_V2 / "E_node_levels_village_v2.csv", index=False, encoding="utf-8-sig")
    print("\n基線分級（臺南絕對切點）各級里數：")
    print(lv.pivot_table(index="node", columns=["scenario", "level_label"], values="unit", aggfunc="count", fill_value=0).to_string())


if __name__ == "__main__":
    main()
