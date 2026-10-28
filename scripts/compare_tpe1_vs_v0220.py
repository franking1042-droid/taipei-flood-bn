# -*- coding: utf-8 -*-
"""compare_tpe1_vs_v0220.py — 同一套 v2 里級輸入，比較 bn_v0220.pkl 與提案版 bn_v0220_tpe1.pkl 的後驗。

推論函式直接用 run_inference_taipei.anchored_query（virtual evidence 錨定，與 v2 同法）；輸入檔全部用 v2 的里級檔。
  A. 93 里 × H1=超大豪雨（E 24h500）、錨定：ModifiedFloodPotential、O_TotalRisk_int 期望值，新舊與差值。
  B. 焦點里（北士科建民、洲美，及福華、吉慶、一德）× 4 雨級：抽水運作、外水頂托、修正潛勢、延時、R1–R3、O 的期望值。
輸出：bn_engine/results/taipei_tpe1/compare_tpe1_vs_v0220_93villages.csv、compare_tpe1_vs_v0220_focus.csv、summary.json
"""
import csv
import io
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

import run_inference_taipei as R
from taipei_paths import CPT, OUT_V2, ROOT

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PKL0 = ROOT / "bn_engine" / "bn_v0220.pkl"
PKL1 = ROOT / "bn_engine" / "bn_v0220_tpe1.pkl"
TABLE_JSON = CPT / "h2_village_conditional_table_taipei_v2.json"
UNIT_EV = OUT_V2 / "evidence_per_village_taipei_v2.json"
E_LEVELS_CSV = OUT_V2 / "E_node_levels_village_v2.csv"
OUT = ROOT / "bn_engine" / "results" / "taipei_tpe1"
OUT.mkdir(parents=True, exist_ok=True)
FOCUS_VILLAGES = ["建民里", "洲美里", "福華里", "吉慶里", "一德里"]   # 以里名對應 unit，不猜區
MECH = ["PumpStationOperation", "TidalBackwater"]
T_ALL = ["ModifiedFloodPotential", "FloodDuration"] + R.R_NODES + [R.O_NODE]


def load_e_levels():
    out = {}
    for r in csv.DictReader(open(E_LEVELS_CSV, encoding="utf-8-sig")):
        out.setdefault((r["unit"], r["scenario"]), {})[r["node"]] = r["level_label"]
    return out


def unit_evidence(dev, e_levels, sl, u, h1):
    ev = R.clean_evidence(dev.get(u, {}), sl, exclude=("Rainfall",))
    ev["Rainfall"] = h1
    for node, lab in e_levels.get((u, R.SCEN_BY_H1[h1]), {}).items():
        if node in sl and lab in sl[node]:
            ev[node] = lab
    return ev


def main(stage="all"):
    bn0, inf0, sl = R.load_engine(PKL0)
    bn1, inf1, _ = R.load_engine(PKL1)
    print(f"v0220: {bn0.number_of_nodes()} 節點 {bn0.number_of_edges()} 邊；tpe1: {bn1.number_of_nodes()} 節點 {bn1.number_of_edges()} 邊")
    table = json.load(open(TABLE_JSON, encoding="utf-8"))["table"]
    dev = json.load(open(UNIT_EV, encoding="utf-8"))
    index = dev["_meta"]["unit_index"]
    units = [k for k in dev if not k.startswith("_")]
    e_levels = load_e_levels()
    FOCUS = [u for u in units if index[u]["village"] in FOCUS_VILLAGES]
    assert len(FOCUS) == len(FOCUS_VILLAGES), FOCUS

    # A. 93 里 × 超大豪雨（stage=B 時直接讀上次的輸出）
    rows = []
    for i, u in enumerate(units if stage in ("all", "A") else []):
        ev = unit_evidence(dev, e_levels, sl, u, R.H1_BASE)
        r0 = R.anchored_query(inf0, table, u, R.H1_BASE, ev, ["ModifiedFloodPotential", R.O_NODE])
        r1 = R.anchored_query(inf1, table, u, R.H1_BASE, ev, ["ModifiedFloodPotential", R.O_NODE])
        row = {"unit": u, "district": index[u]["district"], "village": index[u]["village"],
               "DR.SMC": ev.get("DR.StructuralMeasures_Coverage"), "RiverWaterLevel": ev.get("RiverWaterLevel"),
               "MFP_EV_v0220": R.ev_idx(r0["ModifiedFloodPotential"]), "MFP_EV_tpe1": R.ev_idx(r1["ModifiedFloodPotential"]),
               "O_EV_v0220": R.ev_idx(r0[R.O_NODE]), "O_EV_tpe1": R.ev_idx(r1[R.O_NODE])}
        row["dMFP"] = row["MFP_EV_tpe1"] - row["MFP_EV_v0220"]
        row["dO"] = row["O_EV_tpe1"] - row["O_EV_v0220"]
        rows.append(row)
        if i % 10 == 0 or i == len(units) - 1:
            print(f"A {i + 1}/{len(units)} {u}: O {row['O_EV_v0220']:.4f} -> {row['O_EV_tpe1']:.4f}", flush=True)
    if rows:
        A = pd.DataFrame(rows)
        A.round(4).to_csv(OUT / "compare_tpe1_vs_v0220_93villages.csv", index=False, encoding="utf-8-sig")
    else:
        A = pd.read_csv(OUT / "compare_tpe1_vs_v0220_93villages.csv", encoding="utf-8-sig")

    # B. 焦點里 × 4 雨級
    rows = []
    for u in FOCUS:
        for h1 in R.H1_LIST:
            ev = unit_evidence(dev, e_levels, sl, u, h1)
            r0 = R.anchored_query(inf0, table, u, h1, ev, MECH + T_ALL)
            r1 = R.anchored_query(inf1, table, u, h1, ev, MECH + T_ALL)
            row = {"unit": u, "H1": h1, "DR.SMC": ev.get("DR.StructuralMeasures_Coverage"), "RiverWaterLevel": ev.get("RiverWaterLevel")}
            for t in MECH:
                lab = "PSO" if t == "PumpStationOperation" else "TB"
                for s, a, b in zip(sl[t], r0[t], r1[t]):
                    row[f"P({lab}={s})_v0220"] = round(a, 4)
                    row[f"P({lab}={s})_tpe1"] = round(b, 4)
            for t in T_ALL:
                lab = {"ModifiedFloodPotential": "MFP", "FloodDuration": "FloodDuration", "R1_EconomicLoss_new": "R1",
                       "R2_Lifeline_new": "R2", "R3_Vulnerable_new": "R3", R.O_NODE: "O"}[t]
                row[f"{lab}_EV_v0220"] = round(R.ev_idx(r0[t]), 4)
                row[f"{lab}_EV_tpe1"] = round(R.ev_idx(r1[t]), 4)
            rows.append(row)
            print(f"B {u} {h1}: MFP {row['MFP_EV_v0220']:.4f} -> {row['MFP_EV_tpe1']:.4f}, O {row['O_EV_v0220']:.4f} -> {row['O_EV_tpe1']:.4f}", flush=True)
    B = pd.DataFrame(rows)
    B.to_csv(OUT / "compare_tpe1_vs_v0220_focus.csv", index=False, encoding="utf-8-sig")

    summ = {"date": date.today().isoformat(), "H1": R.H1_BASE, "n_villages": len(A),
            "mean_O_v0220": round(A.O_EV_v0220.mean(), 4), "mean_O_tpe1": round(A.O_EV_tpe1.mean(), 4),
            "mean_dO": round(A.dO.mean(), 4), "min_dO": round(A.dO.min(), 4), "max_dO": round(A.dO.max(), 4),
            "mean_dMFP": round(A.dMFP.mean(), 4), "min_dMFP": round(A.dMFP.min(), 4), "max_dMFP": round(A.dMFP.max(), 4),
            "dO_by_DR.SMC": A.groupby("DR.SMC").dO.mean().round(4).to_dict(),
            "dMFP_by_DR.SMC": A.groupby("DR.SMC").dMFP.mean().round(4).to_dict(),
            "RiverWaterLevel_values": sorted(A.RiverWaterLevel.dropna().unique().tolist()),
            "top10_by_dO": A.sort_values("dO").head(10)[["unit", "DR.SMC", "dMFP", "dO"]].round(4).to_dict("records"),
            "focus": B[["unit", "H1", "MFP_EV_v0220", "MFP_EV_tpe1", "O_EV_v0220", "O_EV_tpe1"]].to_dict("records")}
    json.dump(summ, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k not in ("top10_by_dO", "focus")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
