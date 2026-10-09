#!/usr/bin/env python3
"""
build_bn_v0220.py — Phase 5 v0.22.0（CPE）
O_total 總和風險綜合節點：R1/R2/R3 → O_TotalRisk_int（加權序數 CPT）

設計論述（回應 Mike「三個 R 的單位不同要如何整合」）
--------------------------------------------------
R1/R2/R3 皆為**序數風險等級**（4 級），非物理單位：
  - R1_EconomicLoss_new（輕微/中度/嚴重/重大）：物理對應 Hazus DDF % loss
    （FD1-5 城市平均 4.3/8.1/17.6/26.8/38.9%；級切點 15/35%），可經
    nhess_ci_costs.json（重置成本 EUR→NTD 35）換算 NTD 區間——單位「錢」。
  - R2_Lifeline_new（低/中/高/極高）：服務中斷「戶·日」概念（事件弱標籤閾值：
    無紀錄/<2 萬戶/2–8 萬戶/≥8 萬戶或併大規模停水）——單位「戶·日」。
  - R3_Vulnerable_new = R3_total（低/中/高/極高）：潛勢區弱勢受害「人數」區間；
    R3_rate 同配方但 E 用弱勢比例——單位「人」/「比例」。
三者物理單位不可共量（錢 / 戶·日 / 人），任何線性加總皆隱含任意匯率假設。
因此 O_total 綜合在**序數等級層**做（rank-based aggregation）：
  score = Σ w_i · rank_i，rank_i = state_idx/3 ∈ [0,1]（各 R 正規化序位）
  center = score × 4（5 級 child 尺度 0..4），truncated normal σ=0.5 離散化。
權重初版**等權 (1/3,1/3,1/3)**（Source C 假設；AHP 四團隊 elicitation 後替換——
權重不確定性由 run_ototal_mc_v0220.py 之 Dirichlet MC 顯式承載）。

設計選擇：不建 O_TotalRisk_rate 變體——O_total 走 total 系（資源配置導向，
與 R3_total 同語意軸）；公平/rate 視角由 R3_rate 單獨並列呈現，避免混軸。

輸出：bn_engine/bn_v0220.pkl（193n/269e 預期）+ bn_v0220_build_summary.json
      bn_engine/results/v0220/ototal_dag_v0220.png（O_total 子圖）
"""
import itertools
import json
import pickle
from pathlib import Path

import numpy as np
from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination

ROOT = Path(__file__).resolve().parent.parent
BN_IN = ROOT / "bn_engine" / "bn_v0214b.pkl"
BN_OUT = ROOT / "bn_engine" / "bn_v0220.pkl"
SUMMARY_OUT = ROOT / "bn_engine" / "bn_v0220_build_summary.json"
OUT_DIR = ROOT / "bn_engine" / "results" / "v0220"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NODE = "O_TotalRisk_int"
O_STATES = ["極低", "低", "中", "高", "極高"]
PARENTS = ["R1_EconomicLoss_new", "R2_Lifeline_new", "R3_Vulnerable_new"]  # 恰 3 父（Marcot）
W_EQ = [1.0 / 3, 1.0 / 3, 1.0 / 3]   # Source C：等權初版，AHP 後替換
SIGMA = 0.5


def trunc_normal_pmf(n, peak, sigma):
    w = np.exp(-((np.arange(n) - peak) ** 2) / (2 * sigma ** 2))
    return w / w.sum()


def ototal_cpt_vals(weights, cards, n_child=5, sigma=SIGMA):
    """加權序數 CPT：score=Σw·rank → TN(center=score×(n_child−1), σ)."""
    vals = np.zeros((n_child, int(np.prod(cards))))
    for ci, idxs in enumerate(itertools.product(*[range(c) for c in cards])):
        score = sum(w * (i / (c - 1)) for w, i, c in zip(weights, idxs, cards))
        vals[:, ci] = trunc_normal_pmf(n_child, score * (n_child - 1), sigma)
    return vals


def main():
    model = pickle.load(open(BN_IN, "rb"))
    n0, e0 = len(model.nodes()), len(model.edges())
    print(f"loaded bn_v0214b: {n0} nodes / {e0} edges")

    names = {NODE: O_STATES}
    for p in PARENTS:
        names[p] = list(model.get_cpds(p).state_names[p])
    cards = [len(names[p]) for p in PARENTS]
    assert cards == [4, 4, 4], cards

    model.add_node(NODE)
    for p in PARENTS:
        model.add_edge(p, NODE)
    vals = ototal_cpt_vals(W_EQ, cards)
    model.add_cpds(TabularCPD(NODE, 5, vals, evidence=PARENTS,
                              evidence_card=cards, state_names=names))
    print(f"{NODE} added: parents={PARENTS}, 64 cols, TN sigma={SIGMA}")

    # 檢核
    assert model.check_model(), "check_model FAILED"
    import networkx as nx
    assert nx.is_directed_acyclic_graph(nx.DiGraph(model.edges())), "DAG cycle"
    n1, e1 = len(model.nodes()), len(model.edges())
    print(f"bn_v0220: {n1} nodes / {e1} edges (+{n1-n0}n, +{e1-e0}e)")

    # CPT 單調性 sanity：全最低→極低峰、全最高→極高峰、混合→中間
    infer = VariableElimination(model)
    corner = {
        "all_min": [round(float(x), 4) for x in vals[:, 0]],
        "all_max": [round(float(x), 4) for x in vals[:, -1]],
        "mid(2,2,2)": [round(float(x), 4) for x in
                       vals[:, 2 * 16 + 2 * 4 + 2]],
    }
    assert np.argmax(vals[:, 0]) == 0 and np.argmax(vals[:, -1]) == 4
    print("corner check:", corner)

    # 無 evidence 先驗後驗（連通性 smoke）
    p0 = infer.query([NODE], show_progress=False).values.flatten()
    print("prior posterior:", [round(float(x), 4) for x in p0])

    # DAG 子圖
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        for f in font_manager.fontManager.ttflist:
            if "CJK" in f.name or "Noto Sans TC" in f.name:
                plt.rcParams["font.family"] = f.name
                break
        fig, ax = plt.subplots(figsize=(9, 5))
        pos = {}
        gp = {p: sorted(model.get_parents(p)) for p in PARENTS}
        y2, y1, y0 = 1.0, 0.55, 0.0
        allgp = []
        for p in PARENTS:
            allgp += gp[p]
        allgp = list(dict.fromkeys(allgp))
        for i, g in enumerate(allgp):
            pos[g] = ((i + 0.5) / len(allgp), y2)
        for i, p in enumerate(PARENTS):
            pos[p] = ((i + 0.5) / 3, y1)
        pos[NODE] = (0.5, y0)
        for p in PARENTS:
            for g in gp[p]:
                ax.annotate("", xy=pos[p], xytext=pos[g],
                            arrowprops=dict(arrowstyle="->", color="grey", lw=1))
            ax.annotate("", xy=pos[NODE], xytext=pos[p],
                        arrowprops=dict(arrowstyle="->", color="C3", lw=2))
        for n, (x, y) in pos.items():
            fc = "#f6c344" if n == NODE else ("#9ecae1" if n in PARENTS else "#eeeeee")
            ax.text(x, y, n.replace("_new", "").replace("FloodZone_", "FZ_"),
                    ha="center", va="center", fontsize=8,
                    bbox=dict(boxstyle="round,pad=0.35", fc=fc, ec="k", lw=0.6))
        ax.set_title("O_TotalRisk_int weighted-ordinal aggregation (v0.22.0)")
        ax.axis("off")
        fig.savefig(OUT_DIR / "ototal_dag_v0220.png", dpi=150, bbox_inches="tight")
        print("DAG subgraph saved")
    except Exception as ex:      # 圖非關鍵路徑
        print("DAG figure skipped:", ex)

    pickle.dump(model, open(BN_OUT, "wb"))
    summary = {
        "version": "v0.22.0", "date": "2026-08-19",
        "base": f"bn_v0214b.pkl ({n0}n/{e0}e)",
        "result": {"nodes": n1, "edges": e1, "nodes_added": [NODE],
                   "edges_added": [[p, NODE] for p in PARENTS]},
        "cpt_recipe": {
            "type": "weighted ordinal (rank-based aggregation)",
            "formula": "score=Σ w_i·(state_idx_i/3)；center=score×4；TN σ=0.5 → 5 級",
            "weights": {"value": W_EQ, "source": "C（等權假設）",
                        "pending": "AHP 四團隊 elicitation 後替換；權重不確定性由 "
                                   "Dirichlet(4,4,4) MC 承載（run_ototal_mc_v0220.py）"},
            "rationale": "R1(錢)/R2(戶·日)/R3(人) 單位不可共量——綜合必須在序數等級層做；"
                         "線性物理加總隱含任意匯率假設，序數層 rank aggregation 迴避之",
        },
        "design_choice_no_rate_variant":
            "O_total 走 total 系（資源配置導向）；公平/rate 視角由 R3_rate 單獨呈現，"
            "不建 O_TotalRisk_rate（避免 total/rate 混軸）",
        "unit_semantics": {
            "R1_EconomicLoss_new": "序數 4 級 輕微/中度/嚴重/重大；物理對應 Hazus % loss"
                                   "（FD1-5 城市平均 4.3/8.1/17.6/26.8/38.9%，切點 15/35%）"
                                   "→ nhess_ci_costs.json 可換算 NTD 區間",
            "R2_Lifeline_new": "序數 4 級 低/中/高/極高；服務中斷戶·日概念"
                               "（弱標籤閾值 無/<2萬/2–8萬/≥8萬戶或併大規模停水）",
            "R3_Vulnerable_new(R3_total)": "序數 4 級；潛勢區弱勢受害人數區間（絕對量）",
            "R3_rate": "序數 4 級；弱勢受害比例區間（公平導向，獨立呈現不入 O_total）",
        },
        "corner_check": corner,
        "prior_posterior": [round(float(x), 4) for x in p0],
        "check_model": "PASS", "dag_acyclic": True,
    }
    json.dump(summary, open(SUMMARY_OUT, "w"), ensure_ascii=False, indent=1)
    print("saved", BN_OUT.name, "+", SUMMARY_OUT.name)


if __name__ == "__main__":
    main()
