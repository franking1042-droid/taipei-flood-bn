#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_inference_taipei.py — 臺北移植版 C：以 bn_v0220.pkl 對士林、北投做區級推論（臺南 v0.22.0 同法）

完全沿 NTU-STEMLab/tainan-flood-bn 的
  per_district_conditional_inference_v0212.py（district 條件化 = virtual evidence 錨定 OriginalFloodPotential）
  run_ototal_mc_v0220.py（status-quo evidence + E 節點 + Dirichlet 權重 MC + 三軸政策分解）
  policy_aware_anchored_inference_v0214.py（NbS 政策感知錨定位移）
只換三樣輸入：H2 錨定表（臺北淹水潛勢）、區級 evidence（臺北資料）、E 節點等級（臺北暴露，臺南邊界歸級）。
pkl 本體、CPT、節點、狀態完全不動。

stages（CLI：python run_inference_taipei.py [all|baseline|mc|policy]）：
  baseline — 2 區 × 4 雨級 × {錨定, 全域} 的 OFP/MFP/FloodDuration/OUT_FRI/R1/R2/R3/O_total 後驗
  mc       — v0220 基線（H1=超大豪雨 + E 24h500）之 O_total Dirichlet(4,4,4) MC，並與臺南 37 區排序並列
  policy   — do(NbS=高, DR.SMC=高, DR.NS=高) + NbS 錨定位移（α=0.51）之 RR_total 與 R1/R2/R3 分解
輸出：bn_engine/results/taipei_v1/
"""
import csv
import io
import itertools
import json
import pickle
import sys
from datetime import date

import numpy as np
import pandas as pd
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

from taipei_paths import CPT, DISTRICTS, OUT, REF, ROOT

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BN_PKL = ROOT / "bn_engine" / "bn_v0220.pkl"
TABLE_JSON = CPT / "h2_district_conditional_table_taipei_v1.json"
DISTRICT_EV = OUT / "evidence_per_district_taipei_v1.json"
E_LEVELS_CSV = OUT / "E_node_levels_taipei_v1.csv"
LULC_CSV = OUT / "lulc_aggregation_taipei_v1.csv"
TAINAN_MC = REF / "ototal_mc_v0220.csv"
TAINAN_POST = REF / "ototal_baseline_posteriors_v0220.json"

OFP = "OriginalFloodPotential"
FD_STATES = ["FD1", "FD2", "FD3", "FD4", "FD5"]
O_NODE = "O_TotalRisk_int"
R_NODES = ["R1_EconomicLoss_new", "R2_Lifeline_new", "R3_Vulnerable_new"]
FRAME = [OFP, "ModifiedFloodPotential", "FloodDuration", "OUT_FloodRiskIndex"]
POLICY3 = ["NbSImplementation", "DR.StructuralMeasures_Coverage", "DR.NonStructural_DRRPolicy"]
H1_LIST = ["豪雨", "大豪雨", "超大豪雨", "極端降雨"]
SCEN_BY_H1 = {"豪雨": "24h350", "大豪雨": "24h350", "超大豪雨": "24h500", "極端降雨": "24h500"}
H1_BASE = "超大豪雨"
W_EQ = [1.0 / 3, 1.0 / 3, 1.0 / 3]
SIGMA = 0.5
DIRICHLET_ALPHA = [4.0, 4.0, 4.0]
N_MC, SEED = 1000, 42
NBS = {"conversion_rates": {"agri": 0.05, "imperv": 0.08, "other": 0.10}, "depth_scale": 1.0, "alpha_mode": 0.51}
EVIDENCE_REMAP = {"INFRA_LeveeFragility": {"DS3_潰決風險": "DS3_溢堤"}, "UrbanDrainageStandard": {"不足": "低標準"}, "Rainfall": {"大雨": "豪雨"}}
RANKS = np.array(list(itertools.product(range(4), range(4), range(4)))) / 3.0


# ----------------------------------------------------------------- lab functions (verbatim semantics)
def load_engine(path):
    bn = pickle.load(open(path, "rb"))
    infer = VariableElimination(bn)
    sl = {c.variable: list(c.state_names[c.variable]) for c in bn.get_cpds()}
    return bn, infer, sl


def clean_evidence(ev_raw, sl, exclude=()):
    ev = {}
    for k, v in ev_raw.items():
        if k.startswith("_") or k in exclude or k not in sl:
            continue
        vv = EVIDENCE_REMAP.get(k, {}).get(v, v)
        if vv in sl[k]:
            ev[k] = vv
    return ev


def ev_idx(p):
    return float(np.dot(np.arange(len(p)), p))


def nbs_shift(p, s):
    p = np.asarray(p, dtype=float)
    s = float(np.clip(s, 0.0, 1.0))
    out = p.copy()
    for j in range(len(p) - 1, 0, -1):
        m = s * p[j]
        out[j] -= m
        out[j - 1] += m
    return out / out.sum()


def load_delta_nbs_eff():
    c = NBS["conversion_rates"]
    out = {}
    for r in csv.DictReader(open(LULC_CSV, encoding="utf-8-sig")):
        out[r["district"]] = (c["agri"] * float(r["Agricultural_pct"]) + c["imperv"] * float(r["Impervious_pct"])
                              + c["other"] * float(r["Other_pct"]))
    return out


def load_e_levels():
    out = {}
    for r in csv.DictReader(open(E_LEVELS_CSV, encoding="utf-8-sig")):
        out.setdefault((r["district"], r["scenario"]), {})[r["node"]] = r["level_label"]
    return out


def district_evidence(dev, e_levels, sl, d, h1, drop_policy=False):
    ev = clean_evidence(dev.get(d, {}), sl, exclude=("Rainfall",))
    ev["Rainfall"] = h1
    for node, lab in e_levels.get((d, SCEN_BY_H1[h1]), {}).items():
        if node in sl and lab in sl[node]:
            ev[node] = lab
    if drop_policy:
        for p in POLICY3:
            ev.pop(p, None)
    return ev


def anchored_query(infer, table, d, h1, evidence, targets, anchor=True, nbs_high=False, alpha=None, delta=None):
    virtual = None
    if anchor:
        p_shp = np.array(table[d][h1]["p_FD1_5"], dtype=float)
        if nbs_high:
            s = (alpha or NBS["alpha_mode"]) * (delta[d] / 100.0) * NBS["depth_scale"]
            p_shp = nbs_shift(p_shp, s)
        p_model = infer.query([OFP], evidence=evidence, show_progress=False).values
        lik = p_shp / np.maximum(p_model, 1e-12)
        lik = lik / lik.sum()
        virtual = [TabularCPD(OFP, 5, lik.reshape(5, 1), state_names={OFP: FD_STATES})]
    out = {}
    for t in targets:
        if t in evidence:
            continue
        kw = {"virtual_evidence": virtual} if virtual else {}
        out[t] = infer.query([t], evidence=evidence, show_progress=False, **kw).values.flatten().tolist()
    return out


def make_do_engine_multi(bn, node_states):
    m = bn.copy()
    for node, state in node_states.items():
        for p in list(m.predecessors(node)):
            m.remove_edge(p, node)
        old = m.get_cpds(node)
        states = list(old.state_names[node])
        vals = np.zeros((len(states), 1))
        vals[states.index(state)] = 1.0
        m.remove_cpds(old)
        m.add_cpds(TabularCPD(node, len(states), vals, state_names={node: states}))
    assert m.check_model()
    return m, VariableElimination(m)


def approx_ototal_ev(pr1, pr2, pr3, weights, sigma=SIGMA):
    joint = np.einsum("i,j,k->ijk", pr1, pr2, pr3).reshape(-1)
    centers = 4.0 * (RANKS @ np.asarray(weights))
    grid = np.arange(5)[:, None]
    pmf = np.exp(-((grid - centers[None, :]) ** 2) / (2 * sigma ** 2))
    pmf /= pmf.sum(axis=0)
    return float(joint @ (np.arange(5) @ pmf))


# ----------------------------------------------------------------- stages
def stage_baseline(bn, infer, sl, table, dev, e_levels):
    rows, post = [], {}
    for d in DISTRICTS:
        for h1 in H1_LIST:
            ev = district_evidence(dev, e_levels, sl, d, h1)
            for anchor in (True, False):
                res = anchored_query(infer, table, d, h1, ev, FRAME + R_NODES + [O_NODE], anchor=anchor)
                tag = "district_anchored" if anchor else "global"
                for node, p in res.items():
                    for s, x in zip(sl[node], p):
                        rows.append({"district": d, "H1": h1, "E_scenario": SCEN_BY_H1[h1], "config": tag,
                                     "node": node, "state": s, "p": round(x, 6)})
                    rows.append({"district": d, "H1": h1, "E_scenario": SCEN_BY_H1[h1], "config": tag,
                                 "node": node, "state": "EV_idx", "p": round(ev_idx(p), 6)})
                if anchor and h1 == H1_BASE:
                    post[d] = {t: res[t] for t in R_NODES + [O_NODE]}
                    post[d]["_frame"] = {t: res[t] for t in FRAME}
                    post[d]["_evidence"] = ev
            print(f"baseline {d} {h1}: n_ev={len(ev)} OFP(anchored)={[round(x, 3) for x in res_a(infer, table, d, h1, ev)]}", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "posteriors_all_h1_taipei_v1.csv", index=False, encoding="utf-8-sig")
    json.dump(post, open(OUT / "ototal_baseline_posteriors_taipei_v1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return post


def res_a(infer, table, d, h1, ev):
    return anchored_query(infer, table, d, h1, ev, [OFP])[OFP]


def stage_mc(post):
    tn = pd.read_csv(TAINAN_MC, encoding="utf-8-sig")
    rng = np.random.default_rng(SEED)
    W = rng.dirichlet(DIRICHLET_ALPHA, size=N_MC)
    rows = []
    for d in DISTRICTS:
        p1, p2, p3 = (np.array(post[d][t]) for t in R_NODES)
        ev_exact = ev_idx(post[d][O_NODE])
        ev_eq = approx_ototal_ev(p1, p2, p3, W_EQ)
        evs = np.array([approx_ototal_ev(p1, p2, p3, w) for w in W])
        mean = float(evs.mean())
        rank_in_tainan = int((tn["O_EV_mc_mean"] > mean).sum()) + 1
        rows.append({"district": d, "city": "臺北市", "R1_EV": round(ev_idx(p1), 4), "R2_EV": round(ev_idx(p2), 4),
                     "R3_EV": round(ev_idx(p3), 4), "O_EV_exact_eqw": round(ev_exact, 4), "O_EV_approx_eqw": round(ev_eq, 4),
                     "approx_gap": round(ev_eq - ev_exact, 4), "O_EV_mc_mean": round(mean, 4), "O_EV_mc_sd": round(float(evs.std()), 4),
                     "O_EV_ci2.5": round(float(np.percentile(evs, 2.5)), 4), "O_EV_ci97.5": round(float(np.percentile(evs, 97.5)), 4),
                     "rank_if_placed_among_tainan37": rank_in_tainan})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "ototal_mc_taipei_v1.csv", index=False, encoding="utf-8-sig")
    both = pd.concat([out.assign(src="臺北"), tn.assign(src="臺南", city="臺南市")], ignore_index=True)
    both = both.sort_values("O_EV_mc_mean", ascending=False).reset_index(drop=True)
    both["rank_joint39"] = both.index + 1
    both.to_csv(OUT / "ototal_mc_joint_tainan37_taipei2_v1.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    print(both[["rank_joint39", "src", "district", "R1_EV", "R2_EV", "R3_EV", "O_EV_mc_mean", "O_EV_ci2.5", "O_EV_ci97.5"]].head(12).to_string(index=False))
    return out, both


def stage_policy(bn, infer, sl, table, dev, e_levels):
    delta = load_delta_nbs_eff()
    _, infer_do = make_do_engine_multi(bn, {p: "高" for p in POLICY3})
    _, infer_fx = make_do_engine_multi(bn, {**{p: "高" for p in POLICY3}, "DrainageSystemEfficiency": "充足"})
    rows = []
    for d in DISTRICTS:
        ev_sq = district_evidence(dev, e_levels, sl, d, H1_BASE)
        ev_do = district_evidence(dev, e_levels, sl, d, H1_BASE, drop_policy=True)
        ev_fx = {k: v for k, v in ev_do.items() if k != "DrainageSystemEfficiency"}
        base = anchored_query(infer, table, d, H1_BASE, ev_sq, R_NODES + [O_NODE])
        do = anchored_query(infer_do, table, d, H1_BASE, ev_do, R_NODES + [O_NODE], nbs_high=True, delta=delta)
        dofx = anchored_query(infer_fx, table, d, H1_BASE, ev_fx, R_NODES + [O_NODE], nbs_high=True, delta=delta)
        d_r = [ev_idx(base[t]) - ev_idx(do[t]) for t in R_NODES]
        contrib = [w * (4.0 / 3.0) * x for w, x in zip(W_EQ, d_r)]
        tot = sum(contrib)
        rr = ev_idx(base[O_NODE]) - ev_idx(do[O_NODE])
        rr_fx = ev_idx(base[O_NODE]) - ev_idx(dofx[O_NODE])
        rows.append({"district": d, "statusquo_NbS": ev_sq.get("NbSImplementation"), "statusquo_SMC": ev_sq.get("DR.StructuralMeasures_Coverage"),
                     "statusquo_DRNS": ev_sq.get("DR.NonStructural_DRRPolicy"), "delta_NbS_eff_pctpt": round(delta[d], 3),
                     "O_EV_base": round(ev_idx(base[O_NODE]), 4), "O_EV_do3axis": round(ev_idx(do[O_NODE]), 4), "RR_total": round(rr, 4),
                     "dR1_EV": round(d_r[0], 4), "dR2_EV": round(d_r[1], 4), "dR3_EV": round(d_r[2], 4),
                     "share_R1_pct": round(100 * contrib[0] / tot, 1) if abs(tot) > 1e-9 else None,
                     "share_R2_pct": round(100 * contrib[1] / tot, 1) if abs(tot) > 1e-9 else None,
                     "share_R3_pct": round(100 * contrib[2] / tot, 1) if abs(tot) > 1e-9 else None,
                     "linearization_residual": round(rr - tot, 4), "RR_total_dsefix": round(rr_fx, 4)})
        print("policy", rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "ototal_policy_decomposition_taipei_v1.csv", index=False, encoding="utf-8-sig")
    return rows


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    table = json.load(open(TABLE_JSON, encoding="utf-8"))["table"]
    dev = json.load(open(DISTRICT_EV, encoding="utf-8"))
    e_levels = load_e_levels()
    bn, infer, sl = load_engine(BN_PKL)
    print(f"bn_v0220: {len(bn.nodes())} nodes / {len(bn.edges())} edges; districts {DISTRICTS}")
    summary = {"version": "taipei_v1", "date": date.today().isoformat(), "model": "bn_v0220.pkl", "H1_base": H1_BASE}
    post = None
    if stage in ("all", "baseline"):
        post = stage_baseline(bn, infer, sl, table, dev, e_levels)
        summary["baseline"] = {d: {t: [round(x, 4) for x in post[d][t]] for t in R_NODES + [O_NODE]} for d in DISTRICTS}
        summary["baseline_EV"] = {d: {t: round(ev_idx(post[d][t]), 4) for t in R_NODES + [O_NODE]} for d in DISTRICTS}
        summary["n_evidence"] = {d: len(post[d]["_evidence"]) for d in DISTRICTS}
    if stage in ("all", "mc"):
        if post is None:
            post = json.load(open(OUT / "ototal_baseline_posteriors_taipei_v1.json", encoding="utf-8"))
        mc, both = stage_mc(post)
        summary["mc"] = mc.to_dict(orient="records")
    if stage in ("all", "policy"):
        summary["policy"] = stage_policy(bn, infer, sl, table, dev, e_levels)
    json.dump(summary, open(OUT / "taipei_v1_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved summary")


if __name__ == "__main__":
    main()
