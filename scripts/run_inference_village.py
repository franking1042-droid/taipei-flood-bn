#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_inference_village.py — taipei_v2 C：以 bn_v0220.pkl 對士林、北投 93 里做里級推論（臺南 v0.22.0 同法）

推論函式全部直接沿用 run_inference_taipei.py（virtual evidence 錨定、Dirichlet MC、三軸政策分解），
只把空間單元換成里：H2 錨定表、evidence、E 節點等級、LULC 表都用 v2 的里級檔。pkl 不動。

stages（CLI：python run_inference_village.py [all|baseline|mc|policy]）：
  baseline — 93 里 × 4 雨級 錨定後驗（全域後驗只算 H1 基線情境，供對照）
  mc       — H1=超大豪雨 + E 24h500 之 O_total Dirichlet(4,4,4) MC，並給「放進臺南 37 區」的名次
  policy   — do(NbS=高, DR.SMC=高, DR.NS=高) + NbS 錨定位移 之 RR_total 與 R1/R2/R3 分解
另輸出 results_village_v2.csv：每里一列的摘要（各雨級 P(OFP≥FD2)、FloodDuration／OUT_FRI／R1–R3／O 期望值），供地圖與文件。
輸出：bn_engine/results/taipei_v2_village/
"""
import csv
import io
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

import run_inference_taipei as R
from taipei_paths import CPT, OUT_V2

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TABLE_JSON = CPT / "h2_village_conditional_table_taipei_v2.json"
UNIT_EV = OUT_V2 / "evidence_per_village_taipei_v2.json"
E_LEVELS_CSV = OUT_V2 / "E_node_levels_village_v2.csv"
LULC_CSV = OUT_V2 / "lulc_aggregation_village_v2.csv"
VERSION = "taipei_v2_village"


def load_e_levels():
    out = {}
    for r in csv.DictReader(open(E_LEVELS_CSV, encoding="utf-8-sig")):
        out.setdefault((r["unit"], r["scenario"]), {})[r["node"]] = r["level_label"]
    return out


def load_delta_nbs_eff():
    c = R.NBS["conversion_rates"]
    out = {}
    for r in csv.DictReader(open(LULC_CSV, encoding="utf-8-sig")):
        out[r["unit"]] = (c["agri"] * float(r["Agricultural_pct"]) + c["imperv"] * float(r["Impervious_pct"])
                          + c["other"] * float(r["Other_pct"]))
    return out


def unit_evidence(dev, e_levels, sl, u, h1, drop_policy=False):
    ev = R.clean_evidence(dev.get(u, {}), sl, exclude=("Rainfall",))
    ev["Rainfall"] = h1
    for node, lab in e_levels.get((u, R.SCEN_BY_H1[h1]), {}).items():
        if node in sl and lab in sl[node]:
            ev[node] = lab
    if drop_policy:
        for p in R.POLICY3:
            ev.pop(p, None)
    return ev


def stage_baseline(bn, infer, sl, table, dev, e_levels, units, index):
    rows, post, summ = [], {}, []
    for i, u in enumerate(units):
        srow = {"unit": u, "district": index[u]["district"], "village": index[u]["village"]}
        for h1 in R.H1_LIST:
            ev = unit_evidence(dev, e_levels, sl, u, h1)
            configs = (True, False) if h1 == R.H1_BASE else (True,)
            for anchor in configs:
                res = R.anchored_query(infer, table, u, h1, ev, R.FRAME + R.R_NODES + [R.O_NODE], anchor=anchor)
                tag = "village_anchored" if anchor else "global"
                for node, p in res.items():
                    for s, x in zip(sl[node], p):
                        rows.append({"unit": u, "district": srow["district"], "village": srow["village"], "H1": h1,
                                     "E_scenario": R.SCEN_BY_H1[h1], "config": tag, "node": node, "state": s, "p": round(x, 6)})
                    rows.append({"unit": u, "district": srow["district"], "village": srow["village"], "H1": h1,
                                 "E_scenario": R.SCEN_BY_H1[h1], "config": tag, "node": node, "state": "EV_idx", "p": round(R.ev_idx(p), 6)})
                if anchor:
                    srow[f"P_OFP_ge_FD2|{h1}"] = round(1.0 - res[R.OFP][0], 4)
                    srow[f"MFP_EV|{h1}"] = round(R.ev_idx(res["ModifiedFloodPotential"]), 4)
                    srow[f"FloodDuration_EV|{h1}"] = round(R.ev_idx(res["FloodDuration"]), 4)
                    srow[f"OUT_FRI_EV|{h1}"] = round(R.ev_idx(res["OUT_FloodRiskIndex"]), 4)
                    for t, lab in zip(R.R_NODES, ["R1", "R2", "R3"]):
                        srow[f"{lab}_EV|{h1}"] = round(R.ev_idx(res[t]), 4)
                    srow[f"O_EV|{h1}"] = round(R.ev_idx(res[R.O_NODE]), 4)
                    if h1 == R.H1_BASE:
                        post[u] = {t: res[t] for t in R.R_NODES + [R.O_NODE]}
                        post[u]["_frame"] = {t: res[t] for t in R.FRAME}
                        post[u]["_evidence"] = ev
        srow["n_evidence"] = len(post[u]["_evidence"])
        summ.append(srow)
        if i % 10 == 0 or i == len(units) - 1:
            print(f"baseline {i + 1}/{len(units)} {u}: O_EV(超大豪雨)={srow['O_EV|超大豪雨']}", flush=True)
    pd.DataFrame(rows).to_csv(OUT_V2 / "posteriors_all_h1_village_v2.csv", index=False, encoding="utf-8-sig")
    json.dump(post, open(OUT_V2 / "ototal_baseline_posteriors_village_v2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pd.DataFrame(summ).to_csv(OUT_V2 / "results_village_v2.csv", index=False, encoding="utf-8-sig")
    return post


def stage_mc(post, units, index):
    tn = pd.read_csv(R.TAINAN_MC, encoding="utf-8-sig")
    rng = np.random.default_rng(R.SEED)
    W = rng.dirichlet(R.DIRICHLET_ALPHA, size=R.N_MC)
    rows = []
    for u in units:
        p1, p2, p3 = (np.array(post[u][t]) for t in R.R_NODES)
        ev_exact = R.ev_idx(post[u][R.O_NODE])
        ev_eq = R.approx_ototal_ev(p1, p2, p3, R.W_EQ)
        evs = np.array([R.approx_ototal_ev(p1, p2, p3, w) for w in W])
        mean = float(evs.mean())
        rank_in_tainan = int((tn["O_EV_mc_mean"] > mean).sum()) + 1
        rows.append({"unit": u, "district": index[u]["district"], "village": index[u]["village"], "city": "臺北市",
                     "R1_EV": round(R.ev_idx(p1), 4), "R2_EV": round(R.ev_idx(p2), 4), "R3_EV": round(R.ev_idx(p3), 4),
                     "O_EV_exact_eqw": round(ev_exact, 4), "O_EV_approx_eqw": round(ev_eq, 4), "approx_gap": round(ev_eq - ev_exact, 4),
                     "O_EV_mc_mean": round(mean, 4), "O_EV_mc_sd": round(float(evs.std()), 4),
                     "O_EV_ci2.5": round(float(np.percentile(evs, 2.5)), 4), "O_EV_ci97.5": round(float(np.percentile(evs, 97.5)), 4),
                     "rank_if_placed_among_tainan37": rank_in_tainan})
    out = pd.DataFrame(rows).sort_values("O_EV_mc_mean", ascending=False)
    out["rank_among_93_villages"] = np.arange(1, len(out) + 1)
    out.to_csv(OUT_V2 / "ototal_mc_village_v2.csv", index=False, encoding="utf-8-sig")
    print(out.head(15)[["rank_among_93_villages", "unit", "R1_EV", "R2_EV", "R3_EV", "O_EV_mc_mean", "O_EV_ci2.5", "O_EV_ci97.5", "rank_if_placed_among_tainan37"]].to_string(index=False))
    return out


def stage_policy(bn, infer, sl, table, dev, e_levels, units, index):
    delta = load_delta_nbs_eff()
    _, infer_do = R.make_do_engine_multi(bn, {p: "高" for p in R.POLICY3})
    _, infer_fx = R.make_do_engine_multi(bn, {**{p: "高" for p in R.POLICY3}, "DrainageSystemEfficiency": "充足"})
    rows = []
    for i, u in enumerate(units):
        ev_sq = unit_evidence(dev, e_levels, sl, u, R.H1_BASE)
        ev_do = unit_evidence(dev, e_levels, sl, u, R.H1_BASE, drop_policy=True)
        ev_fx = {k: v for k, v in ev_do.items() if k != "DrainageSystemEfficiency"}
        base = R.anchored_query(infer, table, u, R.H1_BASE, ev_sq, R.R_NODES + [R.O_NODE])
        do = R.anchored_query(infer_do, table, u, R.H1_BASE, ev_do, R.R_NODES + [R.O_NODE], nbs_high=True, delta=delta)
        dofx = R.anchored_query(infer_fx, table, u, R.H1_BASE, ev_fx, R.R_NODES + [R.O_NODE], nbs_high=True, delta=delta)
        d_r = [R.ev_idx(base[t]) - R.ev_idx(do[t]) for t in R.R_NODES]
        contrib = [w * (4.0 / 3.0) * x for w, x in zip(R.W_EQ, d_r)]
        tot = sum(contrib)
        rr = R.ev_idx(base[R.O_NODE]) - R.ev_idx(do[R.O_NODE])
        rr_fx = R.ev_idx(base[R.O_NODE]) - R.ev_idx(dofx[R.O_NODE])
        rows.append({"unit": u, "district": index[u]["district"], "village": index[u]["village"],
                     "statusquo_NbS": ev_sq.get("NbSImplementation"), "statusquo_SMC": ev_sq.get("DR.StructuralMeasures_Coverage"),
                     "statusquo_DRNS": ev_sq.get("DR.NonStructural_DRRPolicy"), "delta_NbS_eff_pctpt": round(delta[u], 3),
                     "O_EV_base": round(R.ev_idx(base[R.O_NODE]), 4), "O_EV_do3axis": round(R.ev_idx(do[R.O_NODE]), 4), "RR_total": round(rr, 4),
                     "dR1_EV": round(d_r[0], 4), "dR2_EV": round(d_r[1], 4), "dR3_EV": round(d_r[2], 4),
                     "share_R1_pct": round(100 * contrib[0] / tot, 1) if abs(tot) > 1e-9 else None,
                     "share_R2_pct": round(100 * contrib[1] / tot, 1) if abs(tot) > 1e-9 else None,
                     "share_R3_pct": round(100 * contrib[2] / tot, 1) if abs(tot) > 1e-9 else None,
                     "linearization_residual": round(rr - tot, 4), "RR_total_dsefix": round(rr_fx, 4)})
        if i % 20 == 0 or i == len(units) - 1:
            print(f"policy {i + 1}/{len(units)} {u}: RR_total={rows[-1]['RR_total']}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_V2 / "ototal_policy_decomposition_village_v2.csv", index=False, encoding="utf-8-sig")
    print(df[["RR_total", "RR_total_dsefix", "dR1_EV", "dR2_EV", "dR3_EV"]].describe().round(4).to_string())
    return rows


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    table = json.load(open(TABLE_JSON, encoding="utf-8"))["table"]
    dev = json.load(open(UNIT_EV, encoding="utf-8"))
    index = dev["_meta"]["unit_index"]
    units = [k for k in dev if not k.startswith("_")]
    e_levels = load_e_levels()
    bn, infer, sl = R.load_engine(R.BN_PKL)
    print(f"bn_v0220: {len(bn.nodes())} nodes / {len(bn.edges())} edges; units {len(units)} 里")
    summary = {"version": VERSION, "date": date.today().isoformat(), "model": "bn_v0220.pkl", "H1_base": R.H1_BASE, "n_units": len(units)}
    post = None
    if stage in ("all", "baseline"):
        post = stage_baseline(bn, infer, sl, table, dev, e_levels, units, index)
        summary["baseline_EV"] = {u: {t: round(R.ev_idx(post[u][t]), 4) for t in R.R_NODES + [R.O_NODE]} for u in units}
        summary["n_evidence"] = {u: len(post[u]["_evidence"]) for u in units}
    if stage in ("all", "mc"):
        if post is None:
            post = json.load(open(OUT_V2 / "ototal_baseline_posteriors_village_v2.json", encoding="utf-8"))
        mc = stage_mc(post, units, index)
        summary["mc_top15"] = mc.head(15).to_dict(orient="records")
    if stage in ("all", "policy"):
        pol = stage_policy(bn, infer, sl, table, dev, e_levels, units, index)
        summary["policy_RR_total_stats"] = pd.DataFrame(pol)["RR_total"].describe().round(4).to_dict()
    json.dump(summary, open(OUT_V2 / f"{VERSION}_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved summary")


if __name__ == "__main__":
    main()
