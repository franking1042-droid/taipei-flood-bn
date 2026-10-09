#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compose_evidence_taipei.py — 臺北移植版 B3：區級 status-quo evidence（對應臺南 v0.18.8 的 16 節點）

把 build_district_base_taipei.py 的原始指標，用**臺南同一套切點／規則**映射成 bn_v0220.pkl 的狀態字串。
狀態字串必須逐字等於 CPD 的 state_names，否則推論時會被 clean_evidence() 靜默丟掉。

規則來源（全部沿臺南，不另訂臺北切點）：
  VS 四節點   ：切點由臺南 v0.15.1 district_vs_evidence_v0151.csv 的實際分級反推（見 VS_CUTS）
  Population_Density / BuildingDensity：compose_evidence_per_district_v0181.py 的 [500, 3000] 人/km²
  LandUseImperviousness / NbS_Coverage_Ratio / LP.green_infrastructure_coverage / LP.river_corridor_designation：
                 update_evidence_real_v0188.py 的百分比切點（LULC v0186 指標）
  DR.StructuralMeasures_Coverage：v0185 抽水量 cms 五分位（level 5 ≥ 44 cms；level≥4→高）
  AccessToShelters：v0185 每千 65+ 老人收容所數五分位（level 5 ≥ 0.216；level≥4→高）
  LP.zoning_type / DR.NonStructural_DRRPolicy / RiverWaterLevel：臺南為知識法則（ZONING / DR_HIGH / RIVER_HIGH 集合），
                 臺北比照以區為單位指定，理由寫在 KNOWLEDGE 內
輸出：bn_engine/results/taipei_v1/evidence_per_district_taipei_v1.json
"""
import io
import json
import pickle
import sys
from datetime import date

import pandas as pd

from taipei_paths import DISTRICTS, OUT, ROOT

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
LAB5 = ["very_low", "low", "medium", "high", "very_high"]

# --- VS 四節點切點（%）：由臺南 v0151 輸出反推（各級的實際 min/max 區間），非文件中的 2/5/10/15 ---
VS_CUTS = {
    "Children_Ratio": [8, 11, 14, 17],            # 0-14 歲 / 總人口 %
    "Elderly_Ratio": [15, 18, 24, 30],            # 65+ / 總人口 %
    "ElderlyAlone_Ratio": [0.1, 0.2, 0.3, 0.5],   # 列冊獨居老人 / 65+ %（v0151 實際採用：0.59% 已是 very_high）
    "DisabilityPopulation_Ratio": [4, 5, 6, 7],   # 身障 / 總人口 %
}

# --- 知識法則（臺南用區集合；臺北逐區指定並附理由）---
KNOWLEDGE = {
    "LP.zoning_type": {d: ("都市計畫區", "臺北市全境為都市計畫區") for d in DISTRICTS},
    "DR.NonStructural_DRRPolicy": {
        "士林區": ("高", "有區級地區災害防救計畫（eoc.gov.taipei）、列入 115 年度水災保全計畫（社子島福安里／富州里）、韌性社區 2 處；臺南 DR_HIGH 同等級"),
        "北投區": ("高", "有區級地區災害防救計畫、列入 115 年度水災保全計畫（洲美關渡八仙里／一德里）、水患自主防災社區（一德里）與韌性社區 5 處；臺南 DR_HIGH 同等級"),
    },
    "RiverWaterLevel": {
        "士林區": ("二級警戒", "臨基隆河／淡水河，社子島為全市唯一防汛熱點與保全區（堤防僅 6.6 m）；比照臺南 RIVER_HIGH 沿河區給二級警戒"),
        "北投區": ("二級警戒", "臨基隆河／淡水河，洲美關渡平原為保全區；比照臺南 RIVER_HIGH。若以 200 年堤防保護標準論可改三級警戒（敏感度項）"),
    },
}


def cut5(v, cuts):
    for i, c in enumerate(cuts):
        if v < c:
            return LAB5[i]
    return LAB5[-1]


def pop3(d):            # v0181 discretise_pop_density / building_density_proxy
    return "低" if d < 500 else ("中" if d < 3000 else "高")


def imperv_state(pct):  # v0188
    return "極低" if pct < 5 else "低" if pct < 15 else "中" if pct < 30 else "高" if pct < 50 else "極高"


def nbs3_state(pct):
    return "低" if pct < 25 else "中" if pct < 50 else "高"


def green_infra_state(pct):
    return "<5%" if pct < 5 else "5-15%" if pct < 15 else "15-30%" if pct < 30 else ">30%"


def river_corridor_state(pct):
    return "僅河道用地" if pct < 6 else "含河岸緩衝帶 (<30m)" if pct < 12 else "完整河川廊道 (≥30m + 生態緩衝)"


def pump_level(cms):    # 臺南 v0185 五分位（37 區 raw：L1=0、L2 5.1–9、L3 10–16、L4 25–35.6、L5 ≥44）
    return 1 if cms <= 0 else 2 if cms < 10 else 3 if cms < 20 else 4 if cms < 44 else 5


def shelter_level(per1000):  # 臺南 v0185 五分位（L2 0.03–0.08、L3 0.10–0.16、L4 ~0.16–0.20、L5 ≥0.216）
    return 1 if per1000 <= 0 else 2 if per1000 < 0.099 else 3 if per1000 < 0.16 else 4 if per1000 < 0.216 else 5


def main():
    base = pd.read_csv(OUT / "district_base_indicators_taipei_v1.csv", encoding="utf-8-sig").set_index("district")
    bn = pickle.load(open(ROOT / "bn_engine" / "bn_v0220.pkl", "rb"))
    sl = {c.variable: list(c.state_names[c.variable]) for c in bn.get_cpds()}
    out = {"_meta": {
        "version": "taipei_v1", "date": date.today().isoformat(),
        "model": "bn_v0220.pkl (193 nodes / 269 edges, NTU-STEMLab/tainan-flood-bn)",
        "nodes": 16, "note": "同臺南 v0188：Rainfall 於推論時依情境覆寫；FloodZone_* 八個 E 節點另由 E_node_levels_taipei_v1.csv 依雨級注入",
        "vs_cuts_pct": VS_CUTS,
        "rules": {
            "Population_Density/BuildingDensity": "[500,3000] 人/km²（v0181，BuildingDensity 以人口密度代理）",
            "LandUseImperviousness": "<5 極低 / <15 低 / <30 中 / <50 高 / ≥50 極高（LULC 03+05+06 面積%）",
            "NbS_Coverage_Ratio": "<25 低 / <50 中 / ≥50 高（LULC A1）",
            "LP.green_infrastructure_coverage": "<5 / 5-15 / 15-30 / >30（LULC A2 %）",
            "LP.river_corridor_designation": "<6 僅河道 / <12 含緩衝帶 / ≥12 完整廊道（LULC 04 水利利用 %）",
            "DR.StructuralMeasures_Coverage": "抽水量 cms 五分位 level≤2 低 / 3 中 / ≥4 高（v0185 A4）",
            "AccessToShelters": "每千 65+ 收容所數五分位 level≥4 高 / 3 中 / ≤2 低（v0185 A5）",
        },
    }}
    for d in DISTRICTS:
        b = base.loc[d]
        ev = {}
        raw = {}
        ev["Children_Ratio"] = cut5(b.children_ratio_pct, VS_CUTS["Children_Ratio"]); raw["children_ratio_pct"] = b.children_ratio_pct
        ev["Elderly_Ratio"] = cut5(b.elderly_ratio_pct, VS_CUTS["Elderly_Ratio"]); raw["elderly_ratio_pct"] = b.elderly_ratio_pct
        ev["ElderlyAlone_Ratio"] = cut5(b.elderly_alone_ratio_pct, VS_CUTS["ElderlyAlone_Ratio"]); raw["elderly_alone_ratio_pct_of_65p"] = b.elderly_alone_ratio_pct
        ev["DisabilityPopulation_Ratio"] = cut5(b.disability_pop_ratio_pct, VS_CUTS["DisabilityPopulation_Ratio"]); raw["disability_pop_ratio_pct"] = b.disability_pop_ratio_pct
        ev["Rainfall"] = "大豪雨"                      # 同 v0181 HAZ_RAINFALL 佔位；推論時覆寫
        for node in ("LP.zoning_type", "DR.NonStructural_DRRPolicy", "RiverWaterLevel"):
            ev[node] = KNOWLEDGE[node][d][0]
        ev["Population_Density"] = pop3(b.pop_density); raw["pop_density_per_km2"] = b.pop_density
        ev["BuildingDensity"] = pop3(b.pop_density)
        ev["LandUseImperviousness"] = imperv_state(b.Impervious_pct); raw["Impervious_pct"] = b.Impervious_pct
        ev["NbS_Coverage_Ratio"] = nbs3_state(b.A1_NbS_pct); raw["A1_NbS_pct"] = b.A1_NbS_pct
        ev["LP.green_infrastructure_coverage"] = green_infra_state(b.A2_GreenInfra_pct); raw["A2_GreenInfra_pct"] = b.A2_GreenInfra_pct
        ev["LP.river_corridor_designation"] = river_corridor_state(b.A3_RiverCorridor_pct); raw["A3_RiverCorridor_pct"] = b.A3_RiverCorridor_pct
        pl = pump_level(b.pump_capacity_cms); raw["pump_capacity_cms"] = b.pump_capacity_cms; raw["pump_level_tainan_quintile"] = pl
        ev["DR.StructuralMeasures_Coverage"] = "低" if pl <= 2 else "中" if pl == 3 else "高"
        shl = shelter_level(b.shelters_per_1000_elderly); raw["shelters_per_1000_elderly"] = b.shelters_per_1000_elderly; raw["shelter_level_tainan_quintile"] = shl
        ev["AccessToShelters"] = "高" if shl >= 4 else "中" if shl == 3 else "低"
        for k, v in ev.items():
            assert k in sl and v in sl[k], (d, k, v, sl.get(k))
        out[d] = ev
        out["_meta"].setdefault("raw_values", {})[d] = {k: (round(float(v), 3) if isinstance(v, float) else v) for k, v in raw.items()}
        out["_meta"].setdefault("knowledge_rule_reasons", {})[d] = {n: KNOWLEDGE[n][d][1] for n in KNOWLEDGE}
    p = OUT / "evidence_per_district_taipei_v1.json"
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved", p.name)
    for d in DISTRICTS:
        print(d, json.dumps(out[d], ensure_ascii=False))


if __name__ == "__main__":
    main()
