#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_village_base.py — taipei_v2 B1：里級原始指標（人口分層、LULC 四指標、抽水量、收容所）

對應 v1 的 build_district_base_taipei.py，空間單元改為 93 里。每項指標的「到里的方法」：
- 人口分層：里級原生（民政局各里人口數按年齡分，115/9）；獨居、身障比例為區級複製（見 taipei_common.village_population_strata）。
- LULC 四指標（不透水、A1 NbS、A2 綠基盤、A3 河川廊道）＋農地／建築／其他占比：國土利用現況調查 112 年多邊形
  以 overlay 裁到里界後加總面積（規則同 v0186／v1）。
- 抽水量：抽水站是點位，不屬於任何一個里。做法＝抽水站點位落入水利處「雨水下水道集水分區」多邊形
  （落不進者取 500 m 內最近分區），集水分區抽水量＝分區內各站總抽水量 cms 之和；
  里的有效抽水量＝Σ(分區 cms × 里與分區交集面積／里面積)。無抽水站的重力排水分區與山區 → 0 cms。
- 收容所：臺北市可供避難收容處所一覽表的「服務里別」欄（「全區」＝該區所有里），
  每里被服務的收容所數／里 65+ 人口 × 1000（v0185 A5 定義）。另附「設在該里內」的收容所數供參考。
輸出：bn_engine/results/taipei_v2_village/
  village_base_indicators_v2.csv、lulc_aggregation_village_v2.csv、pump_catchment_mapping_v2.csv、shelter_service_mapping_v2.csv
"""
import glob
import io
import re
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from taipei_common import village_population_strata
from taipei_paths import DATA, DISTRICTS, OUT_V2, read_csv_any, unzip_dir, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
VILLAGE_ALIAS = {"富州里": "富洲里", "福佳港": "福佳里"}   # 保全計畫／收容所表寫法 vs 里界圖寫法；福佳港＝一覽表的筆誤


def norm_village(n):
    """服務里別常省略「里」字、夾註解；統一成里界圖寫法。"""
    n = re.sub(r"[（(].*?[）)]", "", str(n)).strip()
    if not n:
        return ""
    n = VILLAGE_ALIAS.get(n, n)
    if not n.endswith("里"):
        n = VILLAGE_ALIAS.get(n + "里", n + "里")
    return n


def lulc_aggregation(vil):
    d = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    g = gpd.read_file(glob.glob(str(d / "*.shp"))[0], encoding="utf-8").to_crs(3826)
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
    g["geometry"] = g.geometry.make_valid()
    flags = ["A1", "A2", "A3", "IMP", "AGR", "BLD", "OTH"]
    ov = gpd.overlay(g[flags + ["geometry"]], vil[["unit", "geometry"]], how="intersection", keep_geom_type=True)
    ov["a"] = ov.geometry.area
    tot = ov.groupby("unit")["a"].sum()
    rows = []
    for _, v in vil.iterrows():
        sub = ov[ov.unit == v.unit]
        A = v.area_km2
        r = {"unit": v.unit, "district": v.district, "village": v.village, "area_km2": round(A, 4),
             "lulc_total_km2": round(float(tot.get(v.unit, 0.0)) / 1e6, 4)}

        def km2(col):
            return float(sub.loc[sub[col], "a"].sum()) / 1e6

        for col, name in [("A1", "A1_NbS"), ("A2", "A2_GreenInfra"), ("A3", "A3_RiverCorridor")]:
            r[f"{name}_km2"] = round(km2(col), 4)
            r[f"{name}_pct"] = round(km2(col) / A * 100, 2)
        r["Impervious_pct"] = round(km2("IMP") / A * 100, 2)
        r["Agricultural_pct"] = round(km2("AGR") / A * 100, 2)
        r["Building_pct"] = round(km2("BLD") / A * 100, 2)
        r["Other_pct"] = round(km2("OTH") / A * 100, 2)
        rows.append(r)
    return pd.DataFrame(rows).set_index("unit")


def pumps_by_catchment(vil):
    p = read_csv_any(DATA / "pump_stations_shilin_beitou.csv")
    p = p[p["行政區"].isin(DISTRICTS)].copy()            # 與 v1 相同的站集合（士林 24、北投 10）
    pts = gpd.GeoDataFrame(p, geometry=gpd.points_from_xy(p["X_TWD97"].astype(float), p["Y_TWD97"].astype(float)), crs=3826)
    k = gpd.read_file(DATA / "taipei_pump_catchments.kml", driver="KML").to_crs(3826)
    k = k[["Name", "PS1_NAME", "geometry"]].rename(columns={"Name": "catchment", "PS1_NAME": "catchment_ps"}).reset_index(drop=True)
    k["geometry"] = k.geometry.make_valid()
    k["cid"] = k.index
    union = vil.geometry.union_all()
    k = k[k.intersects(union)].copy()
    j = gpd.sjoin(pts, k[["cid", "catchment", "geometry"]], how="left", predicate="within").drop(columns="index_right")
    miss = j["cid"].isna()
    if miss.any():
        near = gpd.sjoin_nearest(pts[miss].drop(columns=[c for c in ["cid", "catchment"] if c in pts.columns]),
                                 k[["cid", "catchment", "geometry"]], how="left", max_distance=500, distance_col="dist_m")
        for idx, r in near.iterrows():
            j.loc[idx, "cid"] = r["cid"]
            j.loc[idx, "catchment"] = r["catchment"]
            j.loc[idx, "match"] = f"nearest {r['dist_m']:.0f} m" if pd.notna(r["cid"]) else "unmatched"
    j.loc[~miss, "match"] = "within"
    j["cms"] = pd.to_numeric(j["總抽水量_cms"], errors="coerce").fillna(0.0)
    cms_by_c = j.groupby("cid")["cms"].sum()
    k["cms"] = k["cid"].map(cms_by_c).fillna(0.0)
    k["stations"] = k["cid"].map(j.groupby("cid")["抽水站名稱"].apply(lambda s: "、".join(s)))
    mapping = j[["抽水站名稱", "行政區", "cms", "catchment", "match"]].sort_values(["catchment", "抽水站名稱"])
    rows = []
    for _, v in vil.iterrows():
        inter = k.geometry.intersection(v.geometry).area
        share = inter / v.geometry.area
        eff = float((k["cms"] * share).sum())
        cov = float(share.sum() * 100)
        names = [f"{c}({s:.0%})" for c, s in zip(k["catchment"], share) if s > 0.01]
        n_in = int(pts.within(v.geometry).sum())
        rows.append({"unit": v.unit, "pump_capacity_cms_eff": round(eff, 3), "pump_catchment_coverage_pct": round(cov, 1),
                     "pump_catchments": "、".join(names), "pump_stations_in_village": n_in})
    cat_table = k.drop(columns="geometry")[["cid", "catchment", "catchment_ps", "cms", "stations"]]
    return pd.DataFrame(rows).set_index("unit"), mapping, cat_table


def shelters_by_service(vil, strata):
    s = read_csv_any(DATA / "shelters_taipei.csv", dtype=str)
    s["district"] = s["鄉鎮"].astype(str).str.strip()
    s = s[s["district"].isin(DISTRICTS)].copy()        # 只用「鄉鎮」欄（v1 以郵遞區號回退會把大同區 111 誤算進士林，C02）
    vset = {(d, n) for d, n in zip(vil.district, vil.village)}
    n_all = {u: 0 for u in vil.unit}
    n_flood = {u: 0 for u in vil.unit}
    cap = {u: 0.0 for u in vil.unit}
    unknown, mapping = [], []
    for _, r in s.iterrows():
        txt = str(r["服務里別"]) if pd.notna(r["服務里別"]) else ""
        is_flood = str(r["水災"]).strip().upper() == "Y"
        c = pd.to_numeric(r["容納人數"], errors="coerce")
        c = 0.0 if pd.isna(c) else float(c)
        if "全區" in txt:
            targets = [u for u, d in zip(vil.unit, vil.district) if d == r["district"]]
            note = "全區"
        else:
            names = [norm_village(n) for n in re.split(r"[、，,;；/／\s]+", txt) if norm_village(n)]
            targets, bad = [], []
            for n in names:
                if (r["district"], n) in vset:
                    targets.append(r["district"] + n)
                else:
                    bad.append(n)
            if bad:
                unknown.append({"收容所": r["名稱"], "district": r["district"], "unmatched": "、".join(bad)})
            note = f"{len(targets)} 里"
        for u in targets:
            n_all[u] += 1
            cap[u] += c
            if is_flood:
                n_flood[u] += 1
        mapping.append({"收容所編號": r["收容所編號"], "名稱": r["名稱"], "district": r["district"], "所在里": r["村里"],
                        "水災": r["水災"], "容納人數": c, "服務里別": txt, "對到": note})
    loc = s.groupby(["district", "村里"]).size()
    rows = []
    for _, v in vil.iterrows():
        e = strata.loc[v.unit, "pop_65p"]
        rows.append({"unit": v.unit, "shelter_count": n_all[v.unit], "shelter_flood_count": n_flood[v.unit],
                     "shelter_capacity": int(cap[v.unit]),
                     "shelters_per_1000_elderly": round(n_all[v.unit] / e * 1000, 3) if e else 0.0,
                     "flood_shelters_per_1000_elderly": round(n_flood[v.unit] / e * 1000, 3) if e else 0.0,
                     "shelters_located_in_village": int(loc.get((v.district, v.village), 0))})
    return pd.DataFrame(rows).set_index("unit"), pd.DataFrame(mapping), pd.DataFrame(unknown)


def main():
    vil = villages_gdf()
    vil["geometry"] = vil.geometry.make_valid()
    strata = village_population_strata()
    lulc = lulc_aggregation(vil)
    pumps, pump_map, cat_table = pumps_by_catchment(vil)
    shel, shel_map, shel_unknown = shelters_by_service(vil, strata)
    base = strata.join(pumps).join(shel).join(
        lulc[["Impervious_pct", "A1_NbS_pct", "A2_GreenInfra_pct", "A3_RiverCorridor_pct", "Agricultural_pct", "Building_pct"]])
    base.to_csv(OUT_V2 / "village_base_indicators_v2.csv", encoding="utf-8-sig")
    lulc.to_csv(OUT_V2 / "lulc_aggregation_village_v2.csv", encoding="utf-8-sig")
    with open(OUT_V2 / "pump_catchment_mapping_v2.csv", "w", encoding="utf-8-sig", newline="") as f:
        f.write("# 抽水站 → 集水分區（within 或 500 m 內最近）\n")
        pump_map.to_csv(f, index=False)
        f.write("\n# 集水分區 → 分區抽水量（cms）\n")
        cat_table.to_csv(f, index=False)
    shel_map.to_csv(OUT_V2 / "shelter_service_mapping_v2.csv", index=False, encoding="utf-8-sig")
    if len(shel_unknown):
        shel_unknown.to_csv(OUT_V2 / "shelter_service_unmatched_v2.csv", index=False, encoding="utf-8-sig")
    print("village_base_indicators_v2:", base.shape)
    print(base[["pop_density", "children_ratio_pct", "elderly_ratio_pct", "Impervious_pct", "A1_NbS_pct", "A2_GreenInfra_pct",
                "A3_RiverCorridor_pct", "pump_capacity_cms_eff", "shelters_per_1000_elderly"]].describe().round(2).to_string())
    print("\n抽水站對應：", pump_map["match"].value_counts().to_dict())
    print("收容所：士林北投", len(shel_map), "處；服務里別無法對上的名稱", len(shel_unknown), "筆")
    if len(shel_unknown):
        print(shel_unknown.to_string())
    print("\nLULC 里級總面積 vs 里面積（km²）：", round(lulc["lulc_total_km2"].sum(), 2), "/", round(lulc["area_km2"].sum(), 2))


if __name__ == "__main__":
    main()
