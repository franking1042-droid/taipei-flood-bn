#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_district_base_taipei.py — 臺北移植版 B1：區級原始指標（人口分層、抽水站、收容所、LULC 四指標）

對應臺南 v0.15.1（VS 四節點 raw）、v0.18.5（A4 抽水量 / A5 收容所）、v0.18.6（LULC A1/A2/A3/不透水）。
- LULC 規則沿 v0186：
    A1 NbS        = LCODE_C1=02 ∪ LCODE_C2∈{0402,0403} ∪ LCODE_C3∈{090100,090200,070200}  面積 / 區面積
    A2 GreenInfra = LCODE_C1=02 ∪ LCODE_C3∈{070200,070302}
    A3 RiverCorr  = LCODE_C1=04（水利利用全部）
    Impervious    = LCODE_C1∈{03,05,06}
  資料：國土測繪中心國土利用現況調查 112 年（士林北投裁切；臺南用 centroid-in-polygon，本版用裁切面積）
- 抽水量：水利處「臺北市現有雨水抽水站設施概況」115 上半年（總抽水量 cms，站級加總）
- 收容所：臺北市可供避難收容處所一覽表（教育局／社會局）；每千 65+ 老人之收容所數（v0185 A5 定義）
輸出：bn_engine/results/taipei_v1/district_base_indicators_taipei_v1.csv、lulc_aggregation_taipei_v1.csv
"""
import glob
import io
import sys

import geopandas as gpd
import pandas as pd

from taipei_common import district_population_strata
from taipei_paths import DATA, DISTRICTS, OUT, districts_gdf, read_csv_any, unzip_dir

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def lulc_aggregation(dist):
    d = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    g = gpd.read_file(glob.glob(str(d / "*.shp"))[0], encoding="utf-8")
    g["a"] = g.geometry.area
    c1 = g["LCODE_C1"].astype(str).str.zfill(2)
    c2 = g["LCODE_C2"].astype(str).str.zfill(4)
    c3 = g["LCODE_C3"].astype(str).str.zfill(6)
    g["A1"] = (c1 == "02") | c2.isin(["0402", "0403"]) | c3.isin(["090100", "090200", "070200"])
    g["A2"] = (c1 == "02") | c3.isin(["070200", "070302"])
    g["A3"] = c1 == "04"
    g["IMP"] = c1.isin(["03", "05", "06"])
    g["AGR"] = c1 == "01"
    g["BLD"] = c1 == "05"
    g["OTH"] = c1.isin(["07", "08"])
    area_km2 = dict(zip(dist["district"], dist.geometry.area / 1e6))
    rows = []
    for dn, sub in g.groupby("TNAME"):
        A = area_km2[dn]
        tot = sub["a"].sum() / 1e6

        def km2(col):
            return sub.loc[sub[col], "a"].sum() / 1e6

        r = {"district": dn, "area_km2": round(A, 3), "lulc_total_km2": round(tot, 3)}
        for col, name in [("A1", "A1_NbS"), ("A2", "A2_GreenInfra"), ("A3", "A3_RiverCorridor")]:
            r[f"{name}_km2"] = round(km2(col), 3)
            r[f"{name}_pct"] = round(km2(col) / A * 100, 2)
        r["Impervious_pct"] = round(km2("IMP") / A * 100, 2)
        r["Agricultural_pct"] = round(km2("AGR") / A * 100, 2)
        r["Building_pct"] = round(km2("BLD") / A * 100, 2)
        r["Other_pct"] = round(km2("OTH") / A * 100, 2)
        rows.append(r)
    return pd.DataFrame(rows).set_index("district")


def pumps():
    p = read_csv_any(DATA / "pump_stations_shilin_beitou.csv")
    p = p[p["行政區"].isin(DISTRICTS)]
    return p.groupby("行政區").agg(pump_count=("抽水站名稱", "size"), pump_capacity_cms=("總抽水量_cms", "sum"))


def shelters(strata):
    s = read_csv_any(DATA / "shelters_taipei.csv", dtype=str)
    code = {"111": "士林區", "112": "北投區"}
    s["district"] = s["鄉鎮"].astype(str).str.strip().where(s["鄉鎮"].astype(str).str.strip().isin(DISTRICTS), s["郵遞區號"].astype(str).str.strip().map(code))
    s = s[s["district"].notna()]
    out = {}
    for d in DISTRICTS:
        sub = s[s["district"] == d]
        n_all = len(sub)
        n_flood = int((sub["水災"].astype(str).str.upper() == "Y").sum())
        cap = pd.to_numeric(sub["容納人數"], errors="coerce").fillna(0).sum()
        e = strata.loc[d, "pop_65p"]
        out[d] = {"shelter_count": n_all, "shelter_flood_count": n_flood, "shelter_capacity": int(cap),
                  "shelters_per_1000_elderly": round(n_all / e * 1000, 3),
                  "flood_shelters_per_1000_elderly": round(n_flood / e * 1000, 3)}
    return pd.DataFrame(out).T


def main():
    dist = districts_gdf()
    strata = district_population_strata()
    lulc = lulc_aggregation(dist)
    base = strata.join(pumps()).join(shelters(strata)).join(
        lulc[["Impervious_pct", "A1_NbS_pct", "A2_GreenInfra_pct", "A3_RiverCorridor_pct", "Agricultural_pct", "Building_pct"]])
    base.to_csv(OUT / "district_base_indicators_taipei_v1.csv", encoding="utf-8-sig")
    lulc.to_csv(OUT / "lulc_aggregation_taipei_v1.csv", encoding="utf-8-sig")
    print(base.T.to_string())


if __name__ == "__main__":
    main()
