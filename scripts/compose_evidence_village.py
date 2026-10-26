#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compose_evidence_village.py — taipei_v2 B3：里級 status-quo evidence（16 節點，集合與臺南 v0188／v1 相同）

切點與規則全部沿 v1 compose_evidence_taipei.py（即臺南同一套），只把單位換成里。
每個節點另記錄「資料解析度」（里級原生／面資料裁切到里／點位→集水分區→里／服務里別→里／區級複製／市級常數／情境），
寫在 evidence JSON 的 _meta.resolution，與 docs/data_input_scale_taipei_v2.md 對應。
輸出：bn_engine/results/taipei_v2_village/evidence_per_village_taipei_v2.json
"""
import io
import json
import pickle
import sys
from datetime import date

import pandas as pd

from compose_evidence_taipei import (KNOWLEDGE, VS_CUTS, cut5, green_infra_state, imperv_state, nbs3_state, pop3,
                                     pump_level, river_corridor_state, shelter_level)
from taipei_paths import OUT_V2, ROOT

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESOLUTION = {
    "Children_Ratio": ("里級原生", "民政局各里人口數按年齡分（115/9）：0–14 歲／總人口"),
    "Elderly_Ratio": ("里級原生", "同上：65+／總人口"),
    "ElderlyAlone_Ratio": ("區級複製", "主計處區級列冊獨居老人（114 年底）／區 65+；同區各里同值"),
    "DisabilityPopulation_Ratio": ("區級複製", "主計處區級身心障礙人數（114 年底）／區總人口；同區各里同值"),
    "Population_Density": ("里級原生", "里人口／里界面積"),
    "BuildingDensity": ("里級原生（代理）", "以里人口密度代理（v0181 規則）"),
    "LP.zoning_type": ("市級常數", "臺北市全境為都市計畫區"),
    "DR.NonStructural_DRRPolicy": ("區級複製", "區級地區災害防救計畫、水災保全計畫、韌性社區（知識法則）；同區各里同值"),
    "RiverWaterLevel": ("區級複製", "沿河區知識法則；同區各里同值"),
    "LandUseImperviousness": ("面資料裁切到里", "國土利用現況調查 112 年多邊形 overlay 里界：03+05+06 面積／里面積"),
    "NbS_Coverage_Ratio": ("面資料裁切到里", "同上，A1 規則"),
    "LP.green_infrastructure_coverage": ("面資料裁切到里", "同上，A2 規則"),
    "LP.river_corridor_designation": ("面資料裁切到里", "同上，04 水利利用占比"),
    "DR.StructuralMeasures_Coverage": ("點位→集水分區→里", "抽水站 cms 落入雨水下水道集水分區，里的有效 cms＝Σ 分區 cms × 面積占比"),
    "AccessToShelters": ("服務里別→里", "收容所一覽表「服務里別」計數／里 65+ × 1000"),
    "Rainfall": ("情境", "推論時依 H1 覆寫"),
}


def main():
    base = pd.read_csv(OUT_V2 / "village_base_indicators_v2.csv", encoding="utf-8-sig").set_index("unit")
    bn = pickle.load(open(ROOT / "bn_engine" / "bn_v0220.pkl", "rb"))
    sl = {c.variable: list(c.state_names[c.variable]) for c in bn.get_cpds()}
    v1meta = json.load(open(ROOT / "bn_engine" / "results" / "taipei_v1" / "evidence_per_district_taipei_v1.json", encoding="utf-8"))["_meta"]
    out = {"_meta": {
        "version": "taipei_v2_village", "date": date.today().isoformat(),
        "model": "bn_v0220.pkl (193 nodes / 269 edges, NTU-STEMLab/tainan-flood-bn)",
        "spatial_unit": "里（unit = 區名＋里名；士林 51 里＋北投 42 里）",
        "nodes": 16, "n_units": int(len(base)),
        "note": "節點集合、切點、規則與 v1／臺南 v0188 相同；Rainfall 於推論時依情境覆寫；FloodZone_* 八個 E 節點另由 E_node_levels_village_v2.csv 依雨級注入",
        "vs_cuts_pct": VS_CUTS, "rules": v1meta["rules"],
        "resolution": {k: {"resolution": v[0], "method": v[1]} for k, v in RESOLUTION.items()},
        "unit_index": {}, "raw_values": {}, "knowledge_rule_reasons": {},
    }}
    counts = {}
    for u, b in base.iterrows():
        d = b["district"]
        ev, raw = {}, {}
        ev["Children_Ratio"] = cut5(b.children_ratio_pct, VS_CUTS["Children_Ratio"]); raw["children_ratio_pct"] = b.children_ratio_pct
        ev["Elderly_Ratio"] = cut5(b.elderly_ratio_pct, VS_CUTS["Elderly_Ratio"]); raw["elderly_ratio_pct"] = b.elderly_ratio_pct
        ev["ElderlyAlone_Ratio"] = cut5(b.elderly_alone_ratio_pct, VS_CUTS["ElderlyAlone_Ratio"]); raw["elderly_alone_ratio_pct_of_65p"] = b.elderly_alone_ratio_pct
        ev["DisabilityPopulation_Ratio"] = cut5(b.disability_pop_ratio_pct, VS_CUTS["DisabilityPopulation_Ratio"]); raw["disability_pop_ratio_pct"] = b.disability_pop_ratio_pct
        ev["Rainfall"] = "大豪雨"
        for node in ("LP.zoning_type", "DR.NonStructural_DRRPolicy", "RiverWaterLevel"):
            ev[node] = KNOWLEDGE[node][d][0]
        ev["Population_Density"] = pop3(b.pop_density); raw["pop_density_per_km2"] = b.pop_density
        ev["BuildingDensity"] = pop3(b.pop_density)
        ev["LandUseImperviousness"] = imperv_state(b.Impervious_pct); raw["Impervious_pct"] = b.Impervious_pct
        ev["NbS_Coverage_Ratio"] = nbs3_state(b.A1_NbS_pct); raw["A1_NbS_pct"] = b.A1_NbS_pct
        ev["LP.green_infrastructure_coverage"] = green_infra_state(b.A2_GreenInfra_pct); raw["A2_GreenInfra_pct"] = b.A2_GreenInfra_pct
        ev["LP.river_corridor_designation"] = river_corridor_state(b.A3_RiverCorridor_pct); raw["A3_RiverCorridor_pct"] = b.A3_RiverCorridor_pct
        pl = pump_level(b.pump_capacity_cms_eff); raw["pump_capacity_cms_eff"] = b.pump_capacity_cms_eff; raw["pump_level_tainan_quintile"] = pl
        ev["DR.StructuralMeasures_Coverage"] = "低" if pl <= 2 else "中" if pl == 3 else "高"
        shl = shelter_level(b.shelters_per_1000_elderly); raw["shelters_per_1000_elderly"] = b.shelters_per_1000_elderly; raw["shelter_level_tainan_quintile"] = shl
        ev["AccessToShelters"] = "高" if shl >= 4 else "中" if shl == 3 else "低"
        for k, v in ev.items():
            assert k in sl and v in sl[k], (u, k, v, sl.get(k))
            counts.setdefault(k, {}).setdefault(v, 0)
            counts[k][v] += 1
        out[u] = ev
        out["_meta"]["unit_index"][u] = {"district": d, "village": b["village"]}
        out["_meta"]["raw_values"][u] = {k: (round(float(v), 3) if isinstance(v, float) else v) for k, v in raw.items()}
        out["_meta"]["knowledge_rule_reasons"][u] = {n: KNOWLEDGE[n][d][1] for n in KNOWLEDGE}
    out["_meta"]["state_counts"] = counts
    p = OUT_V2 / "evidence_per_village_taipei_v2.json"
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", p.name, "| units", len(base))
    for k, v in counts.items():
        print(f"  {k:36s}", v)


if __name__ == "__main__":
    main()
