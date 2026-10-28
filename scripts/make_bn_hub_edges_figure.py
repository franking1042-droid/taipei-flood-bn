# -*- coding: utf-8 -*-
"""bn_v0220 樞紐（ModifiedFloodPotential）周邊結構圖，標出建議新增的兩條邊。

- 節點與實線邊全部直接讀自 bn_engine/bn_v0220.pkl；每一條實線都 assert 存在、兩條建議邊都 assert 不存在。
- 建議新增：DR.StructuralMeasures_Coverage → PumpStationOperation、RiverWaterLevel → TidalBackwater。
  理由與 24 項證據的路徑查核見 docs/DRT-TPE-20261026-002_village_level_inputs.md 第 10 節。
- 輸出：docs/figures/bn_hub_two_edges.png、.svg。不改 pkl。
"""
import math
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch

from taipei_paths import ROOT

PKL = ROOT / "bn_engine" / "bn_v0220.pkl"
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

with open(PKL, "rb") as f:
    m = pickle.load(f)
G = nx.DiGraph()
G.add_nodes_from(m.nodes())
G.add_edges_from(m.edges())

X = {0: 0.0, 1: 3.9, 2: 7.6, 3: 11.0, 4: 14.4}
R = {r: 0.6 + 1.6 * r for r in range(7)}
# key, 中文, 英文, 類型, 欄, y
N = [
    ("Rainfall", "降雨", "Rainfall", "fed", 0, R[6]),
    ("LP.river_corridor_designation", "河廊劃設", "LP.river_corridor_designation", "fed", 0, R[5]),
    ("NZ.SeaLevelRise_Scenario", "海平面上升情境", "NZ.SeaLevelRise_Scenario", "root", 0, R[4]),
    ("DR.StructuralMeasures_Coverage", "工程措施覆蓋（抽水 cms）", "DR.StructuralMeasures_Coverage", "fed", 0, R[3]),
    ("PumpMaintenanceFreq", "抽水站維護頻率", "PumpMaintenanceFreq", "root", 0, R[2]),
    ("PowerSupplyReliability", "供電可靠度", "PowerSupplyReliability", "inter", 0, R[1]),
    ("ENV_ROOTS", "政策類根節點 ×4", "CCA_PolicyIntegration +3", "root", 0, R[0]),
    ("OriginalFloodPotential", "原始淹水潛勢（錨定潛勢圖）", "OriginalFloodPotential", "anch", 1, R[6]),
    ("RiverWaterLevel", "河川水位（出邊 0）", "RiverWaterLevel", "fed", 1, R[5]),
    ("TidalBackwater", "外水頂托", "TidalBackwater", "inter", 1, R[4]),
    ("PumpStationOperation", "抽水運作", "PumpStationOperation", "inter", 1, R[3]),
    ("DrainageSystemEfficiency", "排水系統效率", "DrainageSystemEfficiency", "inter", 1, R[2]),
    ("A_b_LifelineAdaptation", "維生線調適", "A_b_LifelineAdaptation", "inter", 1, R[1]),
    ("EnvironmentalDRRIntegration", "環境減災整合", "EnvironmentalDRRIntegration", "inter", 1, R[0]),
    ("ModifiedFloodPotential", "修正淹水潛勢（樞紐）", "ModifiedFloodPotential", "hub", 2, 6.4),
    ("R1_EconomicLoss_new", "經濟損失風險 R1", "R1_EconomicLoss_new", "risk", 3, 9.0),
    ("FloodDuration", "淹水延時", "FloodDuration", "inter", 3, 5.8),
    ("R2_Lifeline_new", "維生線風險 R2", "R2_Lifeline_new", "risk", 3, 2.4),
    ("O_TotalRisk_int", "綜合風險", "O_TotalRisk_int", "risk", 4, 5.8),
]
pos = {k: (X[c], y) for k, _, _, _, c, y in N}

SOLID = [
    ("Rainfall", "OriginalFloodPotential"), ("Rainfall", "RiverWaterLevel"),
    ("LP.river_corridor_designation", "RiverWaterLevel"), ("NZ.SeaLevelRise_Scenario", "TidalBackwater"),
    ("DR.StructuralMeasures_Coverage", "DrainageSystemEfficiency"), ("DR.StructuralMeasures_Coverage", "A_b_LifelineAdaptation"),
    ("PumpMaintenanceFreq", "PumpStationOperation"), ("PumpMaintenanceFreq", "A_b_LifelineAdaptation"),
    ("PowerSupplyReliability", "PumpStationOperation"), ("PumpStationOperation", "ModifiedFloodPotential"),
    ("PumpStationOperation", "DrainageSystemEfficiency"), ("TidalBackwater", "ModifiedFloodPotential"),
    ("OriginalFloodPotential", "ModifiedFloodPotential"), ("EnvironmentalDRRIntegration", "ModifiedFloodPotential"),
    ("ModifiedFloodPotential", "FloodDuration"), ("ModifiedFloodPotential", "R1_EconomicLoss_new"),
    ("DrainageSystemEfficiency", "FloodDuration"), ("A_b_LifelineAdaptation", "R2_Lifeline_new"),
    ("R1_EconomicLoss_new", "O_TotalRisk_int"), ("R2_Lifeline_new", "O_TotalRisk_int"),
]
PROPOSED = [("DR.StructuralMeasures_Coverage", "PumpStationOperation"), ("RiverWaterLevel", "TidalBackwater")]
ENV_ROOTS = ["CCA_PolicyIntegration", "CoastalForestMgmt", "NBS_ConservationRatio", "WaterResourceMgmtPolicy"]

# ---- 結構核對：圖上畫的每一條邊都要對得上 pkl
for a, b in SOLID:
    assert G.has_edge(a, b), ("pkl 無此邊", a, b)
for a, b in PROPOSED:
    assert not G.has_edge(a, b), ("pkl 已有此邊", a, b)
assert set(G.predecessors("EnvironmentalDRRIntegration")) == set(ENV_ROOTS)
assert all(G.in_degree(r) == 0 for r in ENV_ROOTS)
assert nx.shortest_path_length(G, "FloodDuration", "R2_Lifeline_new") == 3
assert G.out_degree("RiverWaterLevel") == 0
n_children = G.out_degree("ModifiedFloodPotential")
print(f"結構核對通過：{len(SOLID)} 條實線邊存在、{len(PROPOSED)} 條建議邊不存在；MFP 子節點 {n_children}")

# ---- 繪圖
HW, HH, HH_HUB = 1.42, 0.46, 0.84
STYLE = {
    "fed": dict(fc="#CDE9E4", ec="#0F766E", lw=1.6, tc="#0B3B36"),
    "anch": dict(fc="#CDE9E4", ec="#0F766E", lw=1.6, tc="#0B3B36"),
    "inter": dict(fc="#FFFFFF", ec="#6B7280", lw=1.2, tc="#374151"),
    "root": dict(fc="#E5E7EB", ec="#6B7280", lw=1.2, tc="#374151"),
    "hub": dict(fc="#1E3A5F", ec="#1E3A5F", lw=1.6, tc="#FFFFFF"),
    "risk": dict(fc="#DBEAFE", ec="#1D4ED8", lw=1.4, tc="#1E3A8A"),
}


def hh_of(k):
    return HH_HUB if k == "ModifiedFloodPotential" else HH


def border(k_from, k_to):
    a, b = pos[k_from], pos[k_to]
    dx, dy = b[0] - a[0], b[1] - a[1]
    tx = HW / abs(dx) if dx else math.inf
    ty = hh_of(k_from) / abs(dy) if dy else math.inf
    t = min(tx, ty) * 1.04
    return (a[0] + dx * t, a[1] + dy * t)


def arrow(ax, a, b, color="#4B5563", lw=1.3, ls="-", ms=13, z=2):
    s, e = border(a, b), border(b, a)
    ax.annotate("", xy=e, xytext=s, zorder=z,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, linestyle=ls, shrinkA=0, shrinkB=0, mutation_scale=ms))


fig, ax = plt.subplots(figsize=(17.5, 11.2), dpi=150)
ax.set_xlim(-1.6, 16.0)
ax.set_ylim(-0.7, 11.5)
ax.axis("off")
for a, b in SOLID:
    arrow(ax, a, b)
arrow(ax, "ENV_ROOTS", "EnvironmentalDRRIntegration")
arrow(ax, "FloodDuration", "R2_Lifeline_new", color="#9CA3AF", lw=1.2, ls=":")
ax.text(X[3] - 0.15, 4.1, "間接：停電／停水／交通中斷\n→ 維生線中斷 → R2、R3", fontsize=8, color="#6B7280", ha="right", va="center")
for i, (a, b) in enumerate(PROPOSED):
    arrow(ax, a, b, color="#C0392B", lw=3.2, ls="--", ms=22, z=6)
    mx, my = (pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2
    lx, ly = (mx, my + 0.42) if i == 0 else (mx + 0.95, my)
    ax.text(lx, ly, "新增 " + "①②"[i], fontsize=12, fontweight="bold", color="#C0392B", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#C0392B", lw=1.2), zorder=7)
hub_note = "另有 %d 個子節點\n基礎設施脆弱度、OUT 指數" % (n_children - 2)
for k, zh, en, kd, c, y in N:
    st = STYLE[kd]
    x = X[c]
    hh = hh_of(k)
    ax.add_patch(FancyBboxPatch((x - HW, y - hh), 2 * HW, 2 * hh, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=st["fc"], ec=st["ec"], lw=st["lw"], zorder=3))
    if k == "ModifiedFloodPotential":
        ax.text(x, y + 0.50, zh, ha="center", va="center", fontsize=12, fontweight="bold", color=st["tc"], zorder=4)
        ax.text(x, y + 0.16, en, ha="center", va="center", fontsize=8, color=st["tc"], zorder=4, family="DejaVu Sans")
        ax.text(x, y - 0.38, hub_note, ha="center", va="center", fontsize=7.8, color="#CBD5E1", zorder=4, linespacing=1.4)
    else:
        ax.text(x, y + 0.13, zh, ha="center", va="center", fontsize=11, fontweight="bold", color=st["tc"], zorder=4)
        ax.text(x, y - 0.22, en, ha="center", va="center", fontsize=7.5, color=st["tc"], zorder=4, family="DejaVu Sans")
for c, t in [(0, "輸入"), (1, "中介"), (2, "樞紐"), (3, "風險構面"), (4, "整合")]:
    ax.text(X[c], 11.15, t, ha="center", va="center", fontsize=10, color="#6B7280")
notes = ("現況（pkl 既有結構，邊已逐條核對）\n"
         "①  工程措施覆蓋（抽水 cms）只通到排水系統效率與維生線調適；直接接樞紐的「抽水運作」沒有任何證據，父節點全是均勻先驗。\n"
         "②  河川水位出邊為 0，河廊劃設與降雨到此為止；「外水頂托」只聽海平面上升情境。\n"
         "新增兩條邊之後：抽水容量驅動抽水運作、河川水位驅動外水頂托，兩者直接進修正淹水潛勢。各需擴一張 CPT，走 DRT 由臺南端處理。")
ax.text(X[2] - HW - 0.3, 1.75, notes, fontsize=8.8, color="#374151", ha="left", va="top", linespacing=1.55,
        bbox=dict(boxstyle="round,pad=0.5", fc="#F9FAFB", ec="#D1D5DB", lw=1.0))
fig.suptitle("bn_v0220：修正淹水潛勢周邊結構，與建議新增的兩條邊", x=0.5, y=0.975, fontsize=16, fontweight="bold", color="#111827")
ax.text(-1.55, -0.45, "實線＝pkl 既有邊；紅色虛線＝建議新增；點線＝經 3 條邊的間接路徑。R3 與其餘下游節點略。",
        fontsize=9, color="#6B7280", ha="left", va="center")
leg = [Patch(fc="#CDE9E4", ec="#0F766E", label="基線證據有餵（24 項之一）"),
       Patch(fc="#FFFFFF", ec="#6B7280", label="中介節點，無證據"),
       Patch(fc="#E5E7EB", ec="#6B7280", label="根節點未餵（均勻先驗）"),
       Patch(fc="#1E3A5F", ec="#1E3A5F", label="樞紐"),
       Patch(fc="#DBEAFE", ec="#1D4ED8", label="風險節點"),
       Line2D([0], [0], color="#C0392B", lw=3, ls="--", label="建議新增的邊")]
ax.legend(handles=leg, loc="upper right", fontsize=9, frameon=True, ncol=2, bbox_to_anchor=(1.0, 0.935))
for ext in ("png", "svg"):
    fig.savefig(OUT / f"bn_hub_two_edges.{ext}", bbox_inches="tight", facecolor="white")
print("輸出：", OUT / "bn_hub_two_edges.png", "與 .svg")
