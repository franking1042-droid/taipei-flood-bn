#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_webmap_data.py — taipei_v3 C：把模型與街廓輸入匯成互動地圖用的 data/*.js，並產生瀏覽器引擎的自我檢核案例

互動地圖（webmap/bstp_risk_map.html）不是把結果寫死：它載入 CPT，在瀏覽器裡用 webmap/bn_engine.js 做精確推論
（variable elimination＋錨定），輸入參數一改就重算。本檔負責：
  1. bn_v0220.js、bn_v0220_tpe1.js：兩個模型的全部 CPT（排除 OUT_FloodRiskIndex：7 個父節點、390,625 格，網頁不查它；
     靜態 CSV 有）。值為 pgmpy TabularCPD.values 的 C-order 攤平，軸順序＝[子節點]+父節點。
  2. bstp_units.js：街廓 GeoJSON（WGS84）、H2 錨定表、evidence（inherited／planned＋來源）、E 節點等級、
     里界與園區外框（給底圖）、控制面板需要的節點清單／狀態／中文名／是否通到綜合風險。
  3. selftest.js：用 pgmpy anchored_query 算的對照案例（含最終 evidence 字典與期望後驗），網頁「自我檢核」逐格比對。
"""
import csv
import io
import json
import pickle
import sys
from datetime import date

import networkx as nx
import numpy as np

import run_inference_taipei as R
from run_inference_bstp_units import MECH, TARGETS, load_e_levels, unit_evidence
from taipei_paths import CPT, OUT_V2, OUT_V3, ROOT, WEB

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODELS = {"v0220": ROOT / "bn_engine" / "bn_v0220.pkl", "tpe1": ROOT / "bn_engine" / "bn_v0220_tpe1.pkl"}
EXCLUDE = ["OUT_FloodRiskIndex"]
DATA_DIR = WEB / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NODE_LABEL = {
    "Children_Ratio": "兒童比例", "Elderly_Ratio": "高齡比例", "ElderlyAlone_Ratio": "獨居老人比例", "DisabilityPopulation_Ratio": "身障比例",
    "Population_Density": "人口密度", "BuildingDensity": "建築密度", "LandUseImperviousness": "不透水率", "NbS_Coverage_Ratio": "NbS 覆蓋率",
    "LP.green_infrastructure_coverage": "綠基盤覆蓋", "LP.river_corridor_designation": "河川廊道劃設", "LP.zoning_type": "分區類型",
    "DR.NonStructural_DRRPolicy": "非結構減災政策", "DR.StructuralMeasures_Coverage": "結構措施覆蓋（抽水 cms）",
    "AccessToShelters": "收容所可及性", "RiverWaterLevel": "河川水位", "Rainfall": "雨級",
    "FloodZone_Population_Ratio": "潛勢區人口比", "FloodZone_Elderly_Count": "潛勢區高齡人數", "FloodZone_ElderlyAlone_Count": "潛勢區獨居老人數",
    "FloodZone_Disability_Count": "潛勢區身障人數", "FloodZone_Children_Count": "潛勢區兒童數", "FloodZone_Building_Pct": "潛勢區建築占比",
    "FloodZone_Agri_km2": "潛勢區農地面積", "FloodZone_Vulnerable_Ratio": "潛勢區弱勢比",
    "PumpStationOperation": "抽水站運作", "TidalBackwater": "外水頂托", "PowerSupplyReliability": "供電可靠度",
    "PumpMaintenanceFreq": "抽水站維護頻率", "NZ.SeaLevelRise_Scenario": "海平面上升情境", "EnvironmentalDRRIntegration": "環境減災整合",
    "UrbanDrainageStandard": "都市排水標準", "LP.policy_intervention": "政策介入情境", "INFRA_BuildingVulnerability": "建築脆弱度",
    "OriginalFloodPotential": "原始淹水潛勢", "ModifiedFloodPotential": "修正淹水潛勢", "FloodDuration": "淹水延時",
    "R1_EconomicLoss_new": "經濟損失 R1", "R2_Lifeline_new": "生命線中斷 R2", "R3_Vulnerable_new": "弱勢人口 R3", "O_TotalRisk_int": "綜合總風險 O",
}
GROUPS = [
    ("社會人口（里級）", ["Children_Ratio", "Elderly_Ratio", "ElderlyAlone_Ratio", "DisabilityPopulation_Ratio", "Population_Density", "BuildingDensity"]),
    ("土地使用（計畫用途規則會改）", ["LandUseImperviousness", "NbS_Coverage_Ratio", "LP.green_infrastructure_coverage", "LP.river_corridor_designation", "LP.zoning_type"]),
    ("設施與政策", ["DR.StructuralMeasures_Coverage", "DR.NonStructural_DRRPolicy", "AccessToShelters", "RiverWaterLevel"]),
    ("潛勢區暴露 E 節點（依雨級對應 24h350／24h500）", ["FloodZone_Population_Ratio", "FloodZone_Elderly_Count", "FloodZone_Building_Pct",
                                            "FloodZone_ElderlyAlone_Count", "FloodZone_Disability_Count", "FloodZone_Children_Count",
                                            "FloodZone_Agri_km2", "FloodZone_Vulnerable_Ratio"]),
    ("機制與情境（預設不給證據，由模型推估）", ["PumpStationOperation", "TidalBackwater", "PowerSupplyReliability", "PumpMaintenanceFreq",
                                   "NZ.SeaLevelRise_Scenario", "EnvironmentalDRRIntegration", "UrbanDrainageStandard", "LP.policy_intervention",
                                   "INFRA_BuildingVulnerability"]),
]
SCENARIO_NODES = {"PumpStationOperation", "TidalBackwater", "PowerSupplyReliability", "PumpMaintenanceFreq", "NZ.SeaLevelRise_Scenario",
                  "EnvironmentalDRRIntegration", "UrbanDrainageStandard", "LP.policy_intervention", "INFRA_BuildingVulnerability"}


def js_file(path, var, obj):
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"// 由 scripts/export_webmap_data.py 產生（{date.today().isoformat()}），不要手改\nwindow.{var} = {txt};\n", encoding="utf-8")
    print(f"  {path.name}: {path.stat().st_size / 1e6:.2f} MB")


def export_model(name, pkl):
    bn = pickle.load(open(pkl, "rb"))
    nodes = []
    for cpd in bn.get_cpds():
        v = cpd.variable
        if v in EXCLUDE:
            continue
        parents = list(cpd.variables[1:])
        vals = np.asarray(cpd.values, dtype=float)
        assert vals.shape == tuple(len(cpd.state_names[x]) for x in cpd.variables), v
        nodes.append({"name": v, "states": list(cpd.state_names[v]), "parents": parents,
                      "values": [round(float(x), 10) for x in vals.ravel(order="C")]})
    G = nx.DiGraph()
    G.add_nodes_from(bn.nodes())
    G.add_edges_from(bn.edges())
    anc = nx.ancestors(G, R.O_NODE)
    spec = {"name": name, "file": pkl.name, "nodes": nodes, "excluded": EXCLUDE, "n_nodes": bn.number_of_nodes(), "n_edges": bn.number_of_edges(),
            "reaches_O": {n: (n in anc) for n in bn.nodes()}, "date": date.today().isoformat()}
    js_file(DATA_DIR / f"bn_{'v0220' if name == 'v0220' else 'v0220_tpe1'}.js", f"BN_SPEC_{name}", spec)
    return bn


def main():
    print("模型：")
    bns = {name: export_model(name, pkl) for name, pkl in MODELS.items()}
    sl = {c.variable: list(c.state_names[c.variable]) for c in bns["v0220"].get_cpds()}

    # ---- 街廓資料
    units_geo = json.load(open(OUT_V3 / "bstp_units_v3.geojson", encoding="utf-8"))
    ctx = json.load(open(OUT_V2 / "bstp_boundary_and_villages_v2.geojson", encoding="utf-8"))
    ctx["features"] = [f for f in ctx["features"] if f["properties"].get("layer") in ("bstp_boundary", "village")]
    for f in ctx["features"]:
        keep = {k: f["properties"].get(k) for k in ("layer", "name", "village", "area_ha", "pct_of_village_in_bstp", "pct_of_bstp_in_village")}
        f["properties"] = keep
    h2 = json.load(open(CPT / "h2_bstp_unit_conditional_table_v3.json", encoding="utf-8"))
    ev_json = json.load(open(OUT_V3 / "evidence_per_bstp_unit_v3.json", encoding="utf-8"))
    e_rows = list(csv.DictReader(open(OUT_V3 / "E_node_levels_bstp_unit_v3.csv", encoding="utf-8-sig")))
    e_levels = {}
    for r in e_rows:
        e_levels.setdefault(r["unit"], {}).setdefault(r["scenario"], {})[r["node"]] = r["level_label"]
    controls = [{"group": g, "nodes": [{"name": n, "label": NODE_LABEL[n], "states": sl[n], "scenario": n in SCENARIO_NODES} for n in ns]}
                for g, ns in GROUPS]
    meta = {"version": "taipei_v3_bstp_units", "date": date.today().isoformat(), "H1_LIST": R.H1_LIST, "SCEN_BY_H1": R.SCEN_BY_H1,
            "H1_BASE": R.H1_BASE, "targets": TARGETS, "mech": MECH, "node_label": NODE_LABEL, "controls": controls,
            "planned_rules": ev_json["_meta"]["planned_rules"], "rule_basis": ev_json["_meta"]["rule_basis"],
            "unit_index": ev_json["_meta"]["unit_index"], "fd_states": R.FD_STATES, "excluded_nodes": EXCLUDE,
            "states": {n: sl[n] for n in TARGETS + [x for _, ns in GROUPS for x in ns]}}
    js_file(DATA_DIR / "bstp_units.js", "BSTP", {"meta": meta, "units": units_geo, "context": ctx, "h2": h2["table"],
                                                 "evidence": ev_json["units"], "e_levels": e_levels})

    # ---- 自我檢核案例（pgmpy 對照）
    uid_by_kind = {}
    for uid, ix in ev_json["_meta"]["unit_index"].items():
        uid_by_kind.setdefault(ix["kind"], []).append(uid)
    sample = [uid_by_kind["T"][0], uid_by_kind["T"][-1], uid_by_kind["R"][0], uid_by_kind["R"][-1], uid_by_kind["P"][0], uid_by_kind["P"][-1]]
    cases = []
    for mname in MODELS:
        for u in sample:
            for h1 in R.H1_LIST:
                cases.append({"model": mname, "unit": u, "h1": h1, "variant": "planned", "overrides": {}, "anchor": True})
        u = sample[0]
        cases.append({"model": mname, "unit": u, "h1": R.H1_BASE, "variant": "inherited", "overrides": {}, "anchor": True})
        cases.append({"model": mname, "unit": u, "h1": R.H1_BASE, "variant": "planned", "overrides": {}, "anchor": False})
        cases.append({"model": mname, "unit": u, "h1": R.H1_BASE, "variant": "planned", "overrides": {"PumpStationOperation": "失效"}, "anchor": True})
        cases.append({"model": mname, "unit": u, "h1": R.H1_BASE, "variant": "planned", "overrides": {"TidalBackwater": "高", "RiverWaterLevel": "一級警戒"}, "anchor": True})
        cases.append({"model": mname, "unit": sample[2], "h1": "豪雨", "variant": "planned",
                      "overrides": {"DR.StructuralMeasures_Coverage": "低", "LandUseImperviousness": "低", "FloodZone_Population_Ratio": "very_high"}, "anchor": True})
        cases.append({"model": mname, "unit": sample[4], "h1": "極端降雨", "variant": "planned",
                      "overrides": {"NZ.SeaLevelRise_Scenario": "RCP8.5_2050", "PumpMaintenanceFreq": "低", "LP.policy_intervention": "推動藍綠基盤"}, "anchor": True})
    table = h2["table"]
    e_lv = load_e_levels()
    engines = {m: R.load_engine(p) for m, p in MODELS.items()}
    for k, c in enumerate(cases):
        bn, infer, slm = engines[c["model"]]
        ev = unit_evidence(ev_json["units"], e_lv, slm, c["unit"], c["h1"], c["variant"])
        ev.update(c["overrides"])
        res = R.anchored_query(infer, table, c["unit"], c["h1"], ev, TARGETS, anchor=c["anchor"])
        c["id"] = k
        c["evidence"] = ev
        c["pshp"] = table[c["unit"]][c["h1"]]["p_FD1_5"]
        c["expected"] = {t: [round(x, 10) for x in p] for t, p in res.items() if t not in EXCLUDE}   # 網頁引擎不含 OUT_FloodRiskIndex
    js_file(DATA_DIR / "selftest.js", "SELFTEST", {"date": date.today().isoformat(), "tolerance": 1e-6, "cases": cases})
    print(f"自我檢核案例 {len(cases)} 個；目標節點 {len(TARGETS)}")


if __name__ == "__main__":
    main()
