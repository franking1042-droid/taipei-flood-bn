#!/usr/bin/env python3
"""
per_district_conditional_inference_v0212.py — Phase 5 v0.21.2 (Part A2)
BN 端 district 條件化：virtual evidence（two-pass Jeffrey's rule）實作

方法選擇說明
------------
BN 全域 CPT 無法直接放 district 維度（M1 per-district 架構以 evidence 分區）。
兩個候選實作：
  (a) district-specific CPD 熱插拔：37 份 OFP CPD 快取，推論前置換。
      缺點：OFP 有 4 個父節點（Rainfall×LUI×RC×GI = 300 欄），SHP 經驗表只給
      Rainfall 條件維度，其他父維度仍需 fractional-shift 假設重建，且每次置換
      後 pgmpy 需重建 inference engine（37 × 事件數 次），實作面與快取失效風險高。
  (b) virtual evidence（採用）：pgmpy 1.1.2 VariableElimination.query 原生支援
      virtual_evidence。two-pass：先算 P_model(OFP | evidence)，再注入
      likelihood ratio L ∝ P_shp(·|s,d) / P_model(·|evidence)，
      後驗 ∝ P_model × L = P_shp —— **精確**貼合該區經驗條件分布（Jeffrey's rule），
      下游（MFP→FloodDuration→OUT_FRI）自動一致傳遞；不改任何 CPD、
      不動 DAG，對比純度與 v0211 外科置換同級。
      已驗證：forced posterior 與 P_shp 逐位一致（誤差 <1e-12）。
選 (b)：最穩、精確、零副作用。

CLI:  python3 per_district_conditional_inference_v0212.py 安南區 超大豪雨
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

ROOT = Path(__file__).resolve().parent.parent
TABLE_JSON = ROOT / "bn_engine" / "cpt_priors" / "h2_district_conditional_table_v0212.json"
DISTRICT_EV = ROOT / "bn_engine" / "results" / "v0188" / "evidence_per_district_v0188.json"

OFP = "OriginalFloodPotential"
FD_STATES = ["FD1", "FD2", "FD3", "FD4", "FD5"]
DEFAULT_TARGETS = [OFP, "ModifiedFloodPotential", "FloodDuration", "OUT_FloodRiskIndex"]

EVIDENCE_REMAP = {
    "INFRA_LeveeFragility": {"DS3_潰決風險": "DS3_溢堤"},
    "UrbanDrainageStandard": {"不足": "低標準"},
    "Rainfall": {"大雨": "豪雨"},
}


def remap_evidence(node, val):
    return EVIDENCE_REMAP.get(node, {}).get(val, val)


def load_engine(bn_path):
    bn = pickle.load(open(bn_path, "rb"))
    infer = VariableElimination(bn)
    state_lists = {c.variable: list(c.state_names[c.variable]) for c in bn.get_cpds()}
    return bn, infer, state_lists


def clean_evidence(ev_raw, state_lists, exclude=()):
    ev = {}
    for k, v in ev_raw.items():
        if k in exclude or k not in state_lists:
            continue
        vv = remap_evidence(k, v)
        if vv in state_lists[k]:
            ev[k] = vv
    return ev


def conditional_query(infer, table, district, rain_state, evidence, targets=None,
                      district_conditional=True):
    """A2 核心：district 條件化推論。

    evidence 須已含 Rainfall=rain_state。district_conditional=False 時退化為
    global 推論（配置 i/ii 用）。回傳 {node: probs list}。
    """
    targets = targets or DEFAULT_TARGETS
    virtual = None
    if district_conditional:
        p_shp = np.array(table[district][rain_state]["p_FD1_5"], dtype=float)
        p_model = infer.query([OFP], evidence=evidence, show_progress=False).values
        lik = p_shp / np.maximum(p_model, 1e-12)
        lik = lik / lik.sum()
        virtual = [TabularCPD(OFP, 5, lik.reshape(5, 1),
                              state_names={OFP: FD_STATES})]
    out = {}
    for t in targets:
        if t in evidence:
            continue
        kw = {"virtual_evidence": virtual} if virtual else {}
        phi = infer.query([t], evidence=evidence, show_progress=False, **kw)
        out[t] = phi.values.flatten().tolist()
    return out


def main():
    district = sys.argv[1] if len(sys.argv) > 1 else "安南區"
    rain = sys.argv[2] if len(sys.argv) > 2 else "超大豪雨"
    table = json.load(open(TABLE_JSON, encoding="utf-8"))["table"]
    dev = json.load(open(DISTRICT_EV, encoding="utf-8"))

    bn, infer, state_lists = load_engine(ROOT / "bn_engine" / "bn_v0211.pkl")
    ev = clean_evidence(dev.get(district, {}), state_lists, exclude=("Rainfall",))
    ev["Rainfall"] = rain

    print(f"=== {district} | H1={rain} | evidence n={len(ev)} ===")
    for tag, dc in [("global (ii)", False), ("district-conditional (iii)", True)]:
        res = conditional_query(infer, table, district, rain, ev,
                                district_conditional=dc)
        print(f"-- {tag}")
        for t, p in res.items():
            st = state_lists[t]
            ev_idx = float(np.dot(np.arange(len(p)), p))
            print(f"   {t}: " + " ".join(f"{s}={x:.3f}" for s, x in zip(st, p))
                  + f"  EV_idx={ev_idx:.3f}")


if __name__ == "__main__":
    main()
