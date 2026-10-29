#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_bstp_units.py — taipei_v3 A：北投士林科技園區 67 個街廓（土地使用單元）的單元表、H2 錨定表、evidence、E 節點

空間單元＝地政局「臺北市區段徵收區」ZEPN_1.shp 的北士科 67 個街廓多邊形：46 個 T／R 編碼街廓（44.72 ha）＋
21 個未編碼的公園、綠地、學校、機關、交通、抽水站、堤防用地（28.72 ha）；街廓合計 73.44 ha，園區外框 104.99 ha，
其餘是道路與河川。每個街廓的分區＝都市計畫細部計畫使用分區（細計-面）與街廓交集面積最大者
（排除「規劃範圍」「細部計畫範圍」兩個外框多邊形）。

三份輸入到街廓的方法：
  1. H2 錨定表：潛勢圖 10 情境多邊形 overlay 街廓（build_shp_baseline_village 同法，空間單元換成街廓）。街廓原生。
  2. evidence（16 節點）：先整份繼承「宿主里」（與街廓交集面積最大的里）的 v2 里級 evidence，再依「計畫用途規則」
     覆寫土地使用相關節點（不透水率、建築密度、人口密度、NbS 覆蓋、綠基盤）。理由：街廓現況（國土利用 112 年）
     是空置地／營建中（T／R 街廓內空置地 25.5 ha、其他建築用地 13.4 ha），用現況算會把未來的科技產業／住宅街廓
     判成「不透水低」，所以用計畫分區定狀態。兩種版本都存（evidence_inherited／evidence_planned），地圖可切換。
  3. E 節點（8 個 FloodZone_*）：繼承宿主里的等級（里級絕對暴露量）。街廓級的「計畫暴露量」是下一步。
輸出：
  bn_engine/results/taipei_v3_bstp_units/bstp_units_v3.csv、bstp_units_v3.geojson（WGS84）、shp_baseline_bstp_units_v3.csv、
      evidence_per_bstp_unit_v3.json、E_node_levels_bstp_unit_v3.csv
  bn_engine/cpt_priors/h2_bstp_unit_conditional_table_v3.json
  data/taipei/bstp_detail_plan_zoning.geojson（細部計畫分區裁到園區外框 100 m 內；首次執行時由 Data_taipei 的全市 SHP 裁出）
"""
import csv
import glob
import io
import json
import os
import pickle
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from shapely import make_valid
from shapely.geometry import box

from build_shp_baseline_taipei import FD_STATES, MID, RAINFALL_SCENARIO_MAP, TOP, scen_name
from build_shp_baseline_village import profile
from make_bstp_map import load_bstp
from taipei_paths import CPT, DATA, OUT_V2, OUT_V3, ROOT, unzip_dir, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ZONING_CITY_ZIP = Path(r"C:\Users\R1462\OneDrive\中鋼計畫\團隊內部討論紀錄\中綱BN建構\Data\Data_taipei\policy\臺北市都市計畫使用分區SHP.zip")
ZONING_GEOJSON = DATA / "bstp_detail_plan_zoning.geojson"
ZONING_KIND = {"D16": "T", "R3A": "R", "R32A": "R", "RH": "R", "RR4": "R"}
KIND_LABEL = {"T": "科技產業街廓", "R": "住宅街廓", "P": "公共設施／公園綠地"}
PKL = ROOT / "bn_engine" / "bn_v0220.pkl"

# 計畫用途規則：分區代碼 → 覆寫的節點狀態（狀態字串必須是 pkl 裡的狀態；main() 會檢核）
RULE_BUILT = {"LandUseImperviousness": "極高", "BuildingDensity": "高", "NbS_Coverage_Ratio": "低"}
PLANNED_RULES = {
    "D16": dict(RULE_BUILT),                                                   # 科技產業專用區
    "R3A": dict(RULE_BUILT, Population_Density="高"),                           # 第三種住宅區(特)
    "R32A": dict(RULE_BUILT, Population_Density="高"),                          # 第三之二種住宅區(特)
    "RH": dict(RULE_BUILT, Population_Density="高"),                            # 市民住宅區
    "RR4": dict(RULE_BUILT, Population_Density="高"),                           # 住商混合區
    "PEA": {"LandUseImperviousness": "低", "BuildingDensity": "低", "Population_Density": "低",
            "NbS_Coverage_Ratio": "高", "LP.green_infrastructure_coverage": ">30%"},   # 公園用地
    "PEB": {"LandUseImperviousness": "低", "BuildingDensity": "低", "Population_Density": "低",
            "NbS_Coverage_Ratio": "高", "LP.green_infrastructure_coverage": ">30%"},   # 綠地用地
    "PS": {"LandUseImperviousness": "高", "BuildingDensity": "中"},             # 學校用地
    "PSB": {"LandUseImperviousness": "高", "BuildingDensity": "中"},            # 國小用地
    "PSD": {"LandUseImperviousness": "高", "BuildingDensity": "中"},            # 高中用地
    "PG": {"LandUseImperviousness": "高", "BuildingDensity": "中"},             # 機關用地
    "PTA": {"LandUseImperviousness": "高"},                                    # 交通用地
    "PFD1": {"LandUseImperviousness": "高"},                                   # 抽水站用地
    "PFE": {"LandUseImperviousness": "高"},                                    # 堤防用地
}
RULE_BASIS = {
    "LandUseImperviousness": "v0186 規則＝03+05+06 面積%：<5 極低／<15 低／<30 中／<50 高／≥50 極高。建成街廓（建蔽率 50–70% 加鋪面）≥50% → 極高；公園綠地 → 低；學校機關交通設施 → 高",
    "BuildingDensity": "v0181 以人口密度代理 [500,3000] 人/km²；住宅與科技產業街廓（容積率 ≥300%）→ 高；公園綠地 → 低；學校機關 → 中",
    "Population_Density": "住宅街廓常住人口密度 → 高；科技產業街廓是日間工作人口、非常住，沿用宿主里；公園綠地 → 低",
    "NbS_Coverage_Ratio": "A1 規則＝LULC 自然覆蓋 <25 低／<50 中／≥50 高；建成街廓 → 低；公園綠地 → 高",
    "LP.green_infrastructure_coverage": "A2 規則＝綠基盤 % <5／5-15／15-30／>30；公園綠地 → >30%；其餘沿用宿主里",
}
EVIDENCE_NODES = ["Children_Ratio", "Elderly_Ratio", "ElderlyAlone_Ratio", "DisabilityPopulation_Ratio", "Rainfall",
                  "LP.zoning_type", "DR.NonStructural_DRRPolicy", "RiverWaterLevel", "Population_Density", "BuildingDensity",
                  "LandUseImperviousness", "NbS_Coverage_Ratio", "LP.green_infrastructure_coverage",
                  "LP.river_corridor_designation", "DR.StructuralMeasures_Coverage", "AccessToShelters"]


def load_zoning(bstp):
    """細部計畫使用分區（細計-面），裁到園區外框 100 m 內，EPSG:3826。首次執行時從 Data_taipei 全市 SHP 裁出並存成 GeoJSON。"""
    if not ZONING_GEOJSON.exists():
        assert ZONING_CITY_ZIP.exists(), f"找不到全市分區 SHP：{ZONING_CITY_ZIP}"
        d = tempfile.mkdtemp()
        with zipfile.ZipFile(ZONING_CITY_ZIP) as z:
            for i in z.infolist():
                n = i.filename
                if not (i.flag_bits & 0x800):
                    for enc in ("big5", "cp950"):
                        try:
                            n = n.encode("cp437").decode(enc)
                            break
                        except Exception:
                            pass
                if not i.is_dir():
                    open(os.path.join(d, os.path.basename(n)), "wb").write(z.read(i))
        g = gpd.read_file(glob.glob(os.path.join(d, "細計-面.shp"))[0], encoding="big5")
        g = g.set_crs(3826, allow_override=True)          # 原檔無 .prj；座標範圍即 TWD97 TM2
        g = g[~g["分區代碼"].isin(["規劃範圍", "細部計畫範圍"])]
        g = g[g.intersects(bstp.buffer(100))][["編號", "街廓編號", "分區代碼", "分區簡稱", "使用分區", "geometry"]].copy()
        g["使用分區"] = g["使用分區"].astype(str).str.strip()
        g["geometry"] = g.geometry.apply(make_valid)
        g.to_crs(4326).to_file(ZONING_GEOJSON, driver="GeoJSON")
        print(f"細部計畫分區：由全市 SHP 裁出 {len(g)} 個多邊形 → {ZONING_GEOJSON.name}")
    g = gpd.read_file(ZONING_GEOJSON).to_crs(3826)
    g["geometry"] = g.geometry.apply(make_valid)
    return g


def unit_table(blocks, zon, vil, lulc):
    """每個街廓：編號、分區、宿主里與各里占比、現況 LULC。"""
    rows, p_seq, name_seq = [], 0, {}
    for i, b in blocks.iterrows():
        geom = b.geometry
        area = geom.area
        inter = zon[zon.intersects(geom)].copy()
        inter["a"] = inter.geometry.intersection(geom).area
        top = inter.groupby(["分區代碼", "使用分區"])["a"].sum().sort_values(ascending=False)
        if len(top):
            zcode, zname = top.index[0]
            zshare = 100.0 * top.iloc[0] / area
        else:
            zcode, zname, zshare = "NA", "未對到分區", 0.0
        code = None if pd.isna(b["街廓碼"]) else str(b["街廓碼"])
        if code is None:
            p_seq += 1
            uid = f"P{p_seq:02d}"
            kind = ZONING_KIND.get(zcode, "P")
            name_seq[zname] = name_seq.get(zname, 0) + 1
            name = f"{zname}-{name_seq[zname]}"
        else:
            uid, kind, name = code, code[0], f"{code} {zname}"
            assert ZONING_KIND.get(zcode) == kind, (uid, zcode)
        iv = vil[vil.intersects(geom)].copy()
        iv["a"] = iv.geometry.intersection(geom).area
        shares = {r.unit: 100.0 * r.a / area for _, r in iv.iterrows() if r.a / area > 0.001}
        host = max(shares, key=shares.get)
        il = lulc[lulc.intersects(geom)].copy()
        il["a"] = il.geometry.intersection(geom).area
        lu = il.groupby("LCODEC_C2")["a"].sum().sort_values(ascending=False)
        lulc_now = "、".join(f"{k} {100.0 * v / area:.0f}%" for k, v in lu.head(3).items())
        c = geom.centroid
        rows.append({"unit_id": uid, "code": code or "", "name": name, "kind": kind, "kind_label": KIND_LABEL[kind],
                     "zoning_code": zcode, "zoning_name": zname, "zoning_share_pct": round(zshare, 1),
                     "area_ha": round(area / 1e4, 3), "host_village": host, "host_share_pct": round(shares[host], 1),
                     "village_shares": json.dumps({k: round(v, 1) for k, v in shares.items()}, ensure_ascii=False),
                     "lulc_now_2023": lulc_now, "x_twd97": round(c.x, 1), "y_twd97": round(c.y, 1), "_geom": geom})
    return rows


def h2_table(units_gdf):
    """潛勢圖 10 情境 overlay 街廓 → 每街廓 × 情境的淹水統計與 P_shp(FD1..5 | 雨級)。"""
    shp_dir = unzip_dir("flood_potential_taipei_10scenarios_shp.zip")
    rows = []
    for shp in sorted(glob.glob(str(shp_dir / "tp_*_polygon_class_1.shp"))):
        scen = scen_name(shp)
        src_crs = pyogrio.read_info(shp)["crs"]                       # 潛勢圖原檔座標系與街廓（3826）不同，bbox 要先轉
        bb = tuple(gpd.GeoSeries([box(*units_gdf.total_bounds)], crs=3826).buffer(50).to_crs(src_crs).total_bounds)
        g = pyogrio.read_dataframe(shp, bbox=bb).to_crs(3826)
        g["geometry"] = g.geometry.apply(make_valid)
        g = g[["GRIDCODE", "geometry"]].explode(index_parts=False)
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
        ov = gpd.overlay(g, units_gdf[["unit_id", "geometry"]], how="intersection", keep_geom_type=True)
        ov["a"] = ov.geometry.area
        piv = ov.groupby(["unit_id", "GRIDCODE"])["a"].sum().unstack(fill_value=0.0).reindex(columns=[1, 2, 3, 4, 5], fill_value=0.0)
        npoly = ov.groupby("unit_id").size()
        for _, u in units_gdf.iterrows():
            town = u.geometry.area
            a = {k: float(piv.loc[u.unit_id, k]) if u.unit_id in piv.index else 0.0 for k in range(1, 6)}
            flooded = sum(a.values())
            mean_flooded = sum(MID[k] * a[k] for k in a) / flooded if flooded > 0 else 0.0
            cum, p90 = 0.0, 0.0
            for k in range(1, 6):
                cum += a[k]
                if flooded > 0 and cum >= 0.9 * flooded:
                    p90 = MID[k]
                    break
            maxd = max([TOP[k] for k in a if a[k] > 0], default=0.0)
            rows.append({"unit_id": u.unit_id, "kind": u.kind, "zoning_name": u.zoning_name, "scenario": scen,
                         "flooded_area_pct": 100.0 * flooded / town, "mean_depth_m": mean_flooded * flooded / town,
                         "mean_depth_flooded_only_m": mean_flooded, "max_depth_m": maxd, "p90_depth_m": p90,
                         "n_polygons_flooded": int(npoly.get(u.unit_id, 0)), "flooded_area_m2": flooded, "town_area_m2": town,
                         "area_d2_m2": a[1], "area_d3_m2": a[2], "area_d4_m2": a[3], "area_d5_m2": a[4], "area_d6_m2": a[5]})
        sub = [r for r in rows if r["scenario"] == scen]
        print(f"  {scen}: 有淹水的街廓 {sum(1 for r in sub if r['flooded_area_m2'] > 0)}/{len(units_gdf)}；"
              f"最高 {max(sub, key=lambda r: r['flooded_area_pct'])['unit_id']} {max(r['flooded_area_pct'] for r in sub):.1f}%", flush=True)
    by = {}
    for r in rows:
        by.setdefault((r["unit_id"], r["scenario"]), []).append(r)
    table = {}
    for uid in units_gdf["unit_id"]:
        table[uid] = {}
        for s, scens in RAINFALL_SCENARIO_MAP.items():
            p, pct = profile([x for sc in scens for x in by.get((uid, sc), [])])
            table[uid][s] = {"p_FD1_5": [round(x, 6) for x in p], "flooded_area_pct": round(pct, 3), "scenarios": scens}
    return rows, table


def main():
    bstp, _, blocks = load_bstp()
    blocks = blocks.reset_index(drop=True)
    blocks["geometry"] = blocks.geometry.apply(make_valid)
    zon = load_zoning(bstp)
    vil = villages_gdf()
    vil["geometry"] = vil.geometry.make_valid()
    lulc_dir = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    lulc = gpd.read_file(glob.glob(str(lulc_dir / "*.shp"))[0], encoding="utf-8", bbox=tuple(blocks.total_bounds)).to_crs(3826)
    lulc["geometry"] = lulc.geometry.apply(make_valid)

    rows = unit_table(blocks, zon, vil, lulc)
    units = gpd.GeoDataFrame([{k: v for k, v in r.items() if k != "_geom"} for r in rows],
                             geometry=[r["_geom"] for r in rows], crs=3826)
    print(f"北士科街廓 {len(units)}：T {int((units.kind == 'T').sum())}、R {int((units.kind == 'R').sum())}、"
          f"P {int((units.kind == 'P').sum())}；合計 {units.area_ha.sum():.2f} ha；宿主里 {units.host_village.value_counts().to_dict()}")
    print(units.groupby(["kind", "zoning_name"]).agg(n=("unit_id", "size"), ha=("area_ha", "sum")).round(2).to_string())

    # ---- H2 錨定表
    print("潛勢圖 overlay 街廓：")
    shp_rows, table = h2_table(units)
    with open(OUT_V3 / "shp_baseline_bstp_units_v3.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(shp_rows[0].keys()))
        w.writeheader()
        w.writerows(shp_rows)
    h2 = {"version": "taipei_v3_bstp_units", "release_date": date.today().isoformat(),
          "title": "P_shp(H2 | H1, unit) — 北投士林科技園區 67 個街廓 × 4 雨級 × 5 淹水級 條件經驗表（臺南 v0.21.2 同法，空間單元＝街廓）",
          "source": "水利署臺北市淹水潛勢圖（10 情境，GRIDCODE 1-5）× 地政局臺北市區段徵收區 ZEPN_1.shp 北士科街廓",
          "spatial_unit": "街廓（unit_id = 街廓碼；未編碼公設用地 = P01..）",
          "depth_class_mapping": "FD1=街廓面積−淹水面積(≥0.3 m)；FD2=GC1(0.3-0.5 m)；FD3=GC2(0.5-1 m)；FD4=GC3(1-2 m)；FD5=GC4+GC5(>2 m)；epsilon floor 1e-6",
          "h1_states": list(RAINFALL_SCENARIO_MAP), "h2_states": FD_STATES, "rainfall_scenario_mapping": RAINFALL_SCENARIO_MAP,
          "n_units": len(table), "table": table}
    json.dump(h2, open(CPT / "h2_bstp_unit_conditional_table_v3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- evidence：繼承宿主里 + 計畫用途規則
    bn = pickle.load(open(PKL, "rb"))
    sl = {c.variable: list(c.state_names[c.variable]) for c in bn.get_cpds()}
    for zc, rule in PLANNED_RULES.items():
        for node, st in rule.items():
            assert st in sl[node], (zc, node, st)
    dev = json.load(open(OUT_V2 / "evidence_per_village_taipei_v2.json", encoding="utf-8"))
    ev_units, n_rule = {}, 0
    for _, u in units.iterrows():
        inherited = {k: v for k, v in dev[u.host_village].items() if not k.startswith("_")}
        planned = dict(inherited)
        prov = {k: f"里級繼承（{u.host_village}）" for k in inherited}
        for node, st in PLANNED_RULES.get(u.zoning_code, {}).items():
            if planned.get(node) != st:
                n_rule += 1
            planned[node] = st
            prov[node] = f"計畫用途規則（{u.zoning_name}）"
        ev_units[u.unit_id] = {"evidence_inherited": inherited, "evidence_planned": planned, "provenance": prov}
    unit_index = {u.unit_id: {"code": u.code, "name": u.name, "kind": u.kind, "kind_label": u.kind_label, "zoning_code": u.zoning_code,
                              "zoning_name": u.zoning_name, "area_ha": u.area_ha, "host_village": u.host_village,
                              "host_share_pct": u.host_share_pct, "village_shares": json.loads(u.village_shares),
                              "lulc_now_2023": u.lulc_now_2023} for _, u in units.iterrows()}
    out = {"_meta": {"version": "taipei_v3_bstp_units", "date": date.today().isoformat(),
                     "model": "bn_v0220.pkl（狀態字串檢核）；推論可用 v0220 或 bn_v0220_tpe1",
                     "spatial_unit": "北士科街廓（67）", "nodes": EVIDENCE_NODES, "n_units": len(units),
                     "method": {"evidence_inherited": "整份繼承宿主里（與街廓交集面積最大的里）的 v2 里級 evidence",
                                "evidence_planned": "繼承後依計畫用途規則覆寫土地使用相關節點；推論與地圖的預設版本",
                                "E_nodes": "繼承宿主里 E_node_levels_village_v2（里級絕對暴露量）"},
                     "planned_rules": PLANNED_RULES, "rule_basis": RULE_BASIS, "n_rule_overrides": n_rule,
                     "unit_index": unit_index},
           "units": ev_units}
    json.dump(out, open(OUT_V3 / "evidence_per_bstp_unit_v3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- E 節點：繼承宿主里
    e2 = pd.read_csv(OUT_V2 / "E_node_levels_village_v2.csv", encoding="utf-8-sig")
    e_rows = []
    for _, u in units.iterrows():
        sub = e2[e2.unit == u.host_village]
        for _, r in sub.iterrows():
            e_rows.append({"unit": u.unit_id, "kind": u.kind, "scenario": r.scenario, "node": r.node, "value": r.value,
                           "level": r.level, "level_label": r.level_label, "source_village": u.host_village, "method": "里級繼承"})
    pd.DataFrame(e_rows).to_csv(OUT_V3 / "E_node_levels_bstp_unit_v3.csv", index=False, encoding="utf-8-sig")

    # ---- 單元表與 GeoJSON
    units.drop(columns="geometry").to_csv(OUT_V3 / "bstp_units_v3.csv", index=False, encoding="utf-8-sig")
    fl = {s: {uid: table[uid][s]["flooded_area_pct"] for uid in table} for s in RAINFALL_SCENARIO_MAP}
    g4 = units.copy()
    for s in RAINFALL_SCENARIO_MAP:
        g4[f"flooded_pct_{s}"] = g4.unit_id.map(fl[s])
    g4.to_crs(4326).to_file(OUT_V3 / "bstp_units_v3.geojson", driver="GeoJSON")
    top = sorted(((uid, table[uid]["超大豪雨"]["flooded_area_pct"]) for uid in table), key=lambda x: -x[1])[:10]
    print("超大豪雨 淹水面積% 前 10 街廓:", [(u, round(p, 1)) for u, p in top])
    print(f"計畫用途規則實際改掉的節點狀態數：{n_rule}；輸出 → {OUT_V3.name}/、cpt_priors/h2_bstp_unit_conditional_table_v3.json")


if __name__ == "__main__":
    main()
