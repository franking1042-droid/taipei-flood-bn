#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_inference_bstp_units.py — taipei_v3 B：北士科 67 個街廓 × 4 雨級 × 2 模型（v0220、tpe1）的錨定後驗（靜態交付檔）

推論函式直接用 run_inference_taipei.anchored_query（virtual evidence 錨定，與 v1／v2 同法）；輸入全部用 v3 的街廓級檔：
H2 錨定表（街廓原生）、evidence（預設 planned＝繼承宿主里＋計畫用途規則；另算 inherited 版本供對照）、E 節點（繼承宿主里）。
互動地圖（webmap/）用瀏覽器端引擎即時算同一套東西；本檔是「可直接交給子計畫一」的靜態版本與對照基準。

輸出 bn_engine/results/taipei_v3_bstp_units/：
  results_bstp_units_v3.csv        每街廓 × 模型 × 雨級 × evidence 版本一列：P(OFP≥FD2)、MFP／延時／OUT_FRI／R1–R3／O 期望值、P(O≥高)、抽水運作、外水頂托
  posteriors_all_bstp_units_v3.csv 全部後驗（長表）
  taipei_v3_bstp_units_summary.json
  map_bstp_units_v3_超大豪雨.png     v0220、planned、O 期望值 的街廓地圖
"""
import csv
import io
import json
import sys
from datetime import date

import numpy as np
import pandas as pd

import run_inference_taipei as R
from taipei_paths import CPT, OUT_V2, OUT_V3, ROOT

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODELS = {"v0220": ROOT / "bn_engine" / "bn_v0220.pkl", "tpe1": ROOT / "bn_engine" / "bn_v0220_tpe1.pkl"}
TABLE_JSON = CPT / "h2_bstp_unit_conditional_table_v3.json"
UNIT_EV = OUT_V3 / "evidence_per_bstp_unit_v3.json"
E_LEVELS_CSV = OUT_V3 / "E_node_levels_bstp_unit_v3.csv"
MECH = ["PumpStationOperation", "TidalBackwater"]
TARGETS = R.FRAME + R.R_NODES + [R.O_NODE] + MECH
LAB = {"OriginalFloodPotential": "OFP", "ModifiedFloodPotential": "MFP", "FloodDuration": "FD", "OUT_FloodRiskIndex": "OUTFRI",
       "R1_EconomicLoss_new": "R1", "R2_Lifeline_new": "R2", "R3_Vulnerable_new": "R3", R.O_NODE: "O",
       "PumpStationOperation": "PSO", "TidalBackwater": "TB"}
H1_MAP = "超大豪雨"


def load_e_levels():
    out = {}
    for r in csv.DictReader(open(E_LEVELS_CSV, encoding="utf-8-sig")):
        out.setdefault((r["unit"], r["scenario"]), {})[r["node"]] = r["level_label"]
    return out


def unit_evidence(units, e_levels, sl, u, h1, variant="planned"):
    """與 run_inference_village.unit_evidence 同一套規則；evidence 來源換成街廓檔的 inherited／planned 版本。"""
    ev = R.clean_evidence(units[u]["evidence_" + variant], sl, exclude=("Rainfall",))
    ev["Rainfall"] = h1
    for node, lab in e_levels.get((u, R.SCEN_BY_H1[h1]), {}).items():
        if node in sl and lab in sl[node]:
            ev[node] = lab
    return ev


def summarize(res, sl, table, u, h1):
    row = {"flooded_area_pct": table[u][h1]["flooded_area_pct"]}
    p = res["OriginalFloodPotential"]
    row["P_OFP_ge_FD2"] = round(1.0 - p[0], 6)
    for node in TARGETS:
        if node in res:
            row[f"{LAB[node]}_EV"] = round(R.ev_idx(res[node]), 6)
    po = res[R.O_NODE]
    row["P_O_high"] = round(po[3] + po[4], 6)                        # 高＋極高
    row["P_PSO_normal"] = round(res["PumpStationOperation"][0], 6)
    row["P_TB_high"] = round(res["TidalBackwater"][2], 6)
    return row


def draw_map(df, index):
    import geopandas as gpd
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, Normalize
    matplotlib.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    ramp = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]   # dataviz 藍色序列 100→700
    cmap = LinearSegmentedColormap.from_list("seq_blue", ramp)
    g = gpd.read_file(OUT_V3 / "bstp_units_v3.geojson").to_crs(3826)
    sub = df[(df.model == "v0220") & (df.H1 == H1_MAP) & (df.variant == "planned")].set_index("unit_id")
    g["O_EV"] = g.unit_id.map(sub["O_EV"])
    ctx = gpd.read_file(OUT_V2 / "bstp_boundary_and_villages_v2.geojson").to_crs(3826)
    norm = Normalize(vmin=float(g.O_EV.min()), vmax=float(g.O_EV.max()))
    fig, ax = plt.subplots(figsize=(13, 10))
    ctx[ctx.layer == "village"].plot(ax=ax, facecolor="none", edgecolor="#8c8c8c", linewidth=1.0, linestyle="--", zorder=2)
    g.plot(ax=ax, column="O_EV", cmap=cmap, norm=norm, edgecolor="#ffffff", linewidth=0.8, zorder=3)
    ctx[ctx.layer == "bstp_boundary"].boundary.plot(ax=ax, color="#c00000", linewidth=2.0, zorder=4)
    for _, r in g.iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x, c.y, r.unit_id if r.kind != "P" else "", fontsize=6.5, ha="center", va="center",
                color="#ffffff" if norm(r.O_EV) > 0.55 else "#0b0b0b", zorder=5)
    for _, r in ctx[ctx.layer == "village"].iterrows():
        c = r.geometry.representative_point()
        ax.text(c.x, c.y, r["village"], fontsize=10, ha="center", va="center", color="#444444", zorder=5,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7))
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label("綜合總風險 O 期望值（0 極低 … 4 極高）")
    minx, miny, maxx, maxy = g.total_bounds
    ax.set_xlim(minx - 250, maxx + 250)
    ax.set_ylim(miny - 250, maxy + 250)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(f"北士科 67 街廓 綜合總風險 O 期望值（bn_v0220、H1＝{H1_MAP}、計畫用途 evidence、街廓錨定）", fontsize=13)
    fig.text(0.5, 0.02, "街廓：地政局區段徵收區 ZEPN_1；分區：細部計畫使用分區；evidence 繼承宿主里＋計畫用途規則；E 節點繼承宿主里；"
             "潛勢錨定為街廓原生。白字＝深色格。", ha="center", fontsize=8.5, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = OUT_V3 / f"map_bstp_units_v3_{H1_MAP}.png"
    fig.savefig(out, dpi=160)
    print("saved", out.name)


def main():
    table = json.load(open(TABLE_JSON, encoding="utf-8"))["table"]
    ev_json = json.load(open(UNIT_EV, encoding="utf-8"))
    units, index = ev_json["units"], ev_json["_meta"]["unit_index"]
    e_levels = load_e_levels()
    uids = list(units)
    rows, longrows = [], []
    for mname, pkl in MODELS.items():
        bn, infer, sl = R.load_engine(pkl)
        print(f"{mname}: {bn.number_of_nodes()} 節點 {bn.number_of_edges()} 邊", flush=True)
        for i, u in enumerate(uids):
            for h1 in R.H1_LIST:
                variants = ("planned", "inherited") if h1 == R.H1_BASE else ("planned",)
                for variant in variants:
                    ev = unit_evidence(units, e_levels, sl, u, h1, variant)
                    res = R.anchored_query(infer, table, u, h1, ev, TARGETS)
                    base = {"unit_id": u, "code": index[u]["code"], "kind": index[u]["kind"], "zoning_name": index[u]["zoning_name"],
                            "area_ha": index[u]["area_ha"], "host_village": index[u]["host_village"],
                            "model": mname, "H1": h1, "E_scenario": R.SCEN_BY_H1[h1], "variant": variant}
                    rows.append({**base, **summarize(res, sl, table, u, h1)})
                    for node, p in res.items():
                        for s, x in zip(sl[node], p):
                            longrows.append({**base, "node": node, "state": s, "p": round(x, 6)})
            if i % 10 == 0 or i == len(uids) - 1:
                r = rows[-1]
                print(f"  {i + 1}/{len(uids)} {u} {r['H1']}: O {r['O_EV']:.3f}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT_V3 / "results_bstp_units_v3.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(longrows).to_csv(OUT_V3 / "posteriors_all_bstp_units_v3.csv", index=False, encoding="utf-8-sig")
    base = df[(df.model == "v0220") & (df.H1 == R.H1_BASE) & (df.variant == "planned")].set_index("unit_id")
    inh = df[(df.model == "v0220") & (df.H1 == R.H1_BASE) & (df.variant == "inherited")].set_index("unit_id")
    tpe = df[(df.model == "tpe1") & (df.H1 == R.H1_BASE) & (df.variant == "planned")].set_index("unit_id")
    summ = {"date": date.today().isoformat(), "n_units": len(uids), "H1_base": R.H1_BASE, "models": list(MODELS),
            "O_EV_v0220_planned": {"mean": round(base.O_EV.mean(), 4), "min": round(base.O_EV.min(), 4), "max": round(base.O_EV.max(), 4),
                                   "by_kind": base.groupby("kind").O_EV.mean().round(4).to_dict()},
            "O_EV_top10": base.sort_values("O_EV", ascending=False).head(10)[["kind", "zoning_name", "flooded_area_pct", "O_EV"]].round(4).to_dict("index"),
            "planned_minus_inherited_O_EV": {"mean": round((base.O_EV - inh.O_EV).mean(), 4), "min": round((base.O_EV - inh.O_EV).min(), 4),
                                             "max": round((base.O_EV - inh.O_EV).max(), 4)},
            "tpe1_minus_v0220_O_EV": {"mean": round((tpe.O_EV - base.O_EV).mean(), 4), "min": round((tpe.O_EV - base.O_EV).min(), 4),
                                      "max": round((tpe.O_EV - base.O_EV).max(), 4)},
            "O_EV_by_H1_mean_v0220_planned": df[(df.model == "v0220") & (df.variant == "planned")].groupby("H1").O_EV.mean().round(4).to_dict()}
    json.dump(summ, open(OUT_V3 / "taipei_v3_bstp_units_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summ.items() if k != "O_EV_top10"}, ensure_ascii=False, indent=1))
    draw_map(df, index)


if __name__ == "__main__":
    main()
