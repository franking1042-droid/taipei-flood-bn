# -*- coding: utf-8 -*-
"""build_bn_tpe1_hub_edges.py — 臺北提案版模型 bn_v0220_tpe1.pkl：v0220 加兩條邊，CPT 以勝算權重擴充。

不動 bn_v0220.pkl（AGENTS 不可碰清單）；另存新檔。這是臺北端的「提案模型」，不是共用基線，
正式採納與 CPT 校準由臺南端（DRT）裁定。決策紀錄：docs/DRT-TPE-20261029-003_hub_edges_proposal.md。

新增的邊（理由見 DRT-TPE-20261026-002 §10）：
  ① DR.StructuralMeasures_Coverage（抽水 cms，里級證據）→ PumpStationOperation（直接接樞紐 ModifiedFloodPotential）
  ② RiverWaterLevel（河川水位，證據；原本出邊為 0）→ TidalBackwater（直接接樞紐；原本只聽海平面情境）

CPT 擴充規則（佔位、未校準）：
  新 CPT(child | 舊父節點, 新父節點) ∝ 舊 CPT(child | 舊父節點) × w(child 狀態, 新父節點等級)
  新父節點狀態依序線性映射到等級 ℓ ∈ [-1, +1]；w = K^(方向 × ℓ × c)，c 為子節點狀態的置中序位（三態為 -1, 0, +1）。
  ℓ = 0（新父節點居中，如 DR.SMC=中）時 w ≡ 1，與 v0220 完全相同。K = 2 表示極端等級把兩端狀態的勝算比改變 K² = 4 倍。
  ① 方向 = -1：抽水覆蓋越高，PumpStationOperation 越往「正常」。
  ② 方向 = +1：河川水位越高（一級警戒），TidalBackwater 越往「高」。

輸出：bn_engine/bn_v0220_tpe1.pkl、bn_engine/bn_v0220_tpe1_meta.json
"""
import hashlib
import io
import itertools
import json
import pickle
import sys
from datetime import date

import numpy as np
from pgmpy.factors.discrete import TabularCPD

from taipei_paths import ROOT

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = ROOT / "bn_engine" / "bn_v0220.pkl"
DST = ROOT / "bn_engine" / "bn_v0220_tpe1.pkl"
META = ROOT / "bn_engine" / "bn_v0220_tpe1_meta.json"
K_PUMP = 2.0
K_RIVER = 2.0
EDGES = [
    # (新父節點, 子節點, K, 方向)
    ("DR.StructuralMeasures_Coverage", "PumpStationOperation", K_PUMP, -1),
    ("RiverWaterLevel", "TidalBackwater", K_RIVER, +1),
]


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def level(states, s):
    """父節點狀態依序線性映射到 [-1, +1]（三態：-1, 0, +1；四態：-1, -1/3, +1/3, +1）。"""
    n = len(states)
    return -1.0 + 2.0 * states.index(s) / (n - 1)


def extend_cpd(model, new_parent, child, k, direction):
    old = model.get_cpds(child)
    child_states = list(old.state_names[child])
    old_parents = list(old.variables[1:])
    sn = {v: list(old.state_names[v]) for v in old.variables}
    np_states = list(model.get_cpds(new_parent).state_names[new_parent])
    parents = old_parents + [new_parent]
    cards = [len(sn[p]) for p in old_parents] + [len(np_states)]
    nc = len(child_states)
    centre = np.arange(nc) - (nc - 1) / 2.0
    vals = np.zeros([nc] + cards)
    for idx in itertools.product(*[range(c) for c in cards]):
        p = np.asarray(old.values[(slice(None),) + idx[:-1]], dtype=float)
        w = k ** (direction * level(np_states, np_states[idx[-1]]) * centre)
        q = p * w
        vals[(slice(None),) + idx] = q / q.sum()
    new = TabularCPD(child, nc, vals.reshape(nc, -1), evidence=parents, evidence_card=cards,
                     state_names={child: child_states, **{p: sn[p] for p in old_parents}, new_parent: np_states})
    model.add_edge(new_parent, child)
    model.remove_cpds(old)
    model.add_cpds(new)
    return old, new


def show(cpd, fixed, new_parent):
    """印出固定舊父節點狀態、只變新父節點時的子節點分布。"""
    child = cpd.variable
    sn = cpd.state_names
    print(f"  {child} | {fixed}")
    for s in sn[new_parent]:
        q = {**fixed, new_parent: s}
        idx = tuple(sn[v].index(q[v]) for v in cpd.variables[1:])
        p = cpd.values[(slice(None),) + idx]
        print(f"    {new_parent}={s:<12} " + "  ".join(f"{a}={b:.3f}" for a, b in zip(sn[child], p)))


def main():
    with open(SRC, "rb") as f:
        base = pickle.load(f)
    n0, e0 = base.number_of_nodes(), base.number_of_edges()
    m = base.copy()
    report = []
    for new_parent, child, k, direction in EDGES:
        assert not m.has_edge(new_parent, child), (new_parent, child)
        old, new = extend_cpd(m, new_parent, child, k, direction)
        report.append({"edge": f"{new_parent} -> {child}", "K": k, "direction": direction,
                       "old_parents": old.variables[1:], "new_parents": new.variables[1:],
                       "child_states": list(new.state_names[child]), "new_parent_states": list(new.state_names[new_parent])})
        print(f"加邊 {new_parent} -> {child}：父節點 {old.variables[1:]} -> {new.variables[1:]}，K={k}，方向={direction:+d}")
    assert m.check_model()
    assert m.number_of_nodes() == n0 and m.number_of_edges() == e0 + len(EDGES)
    # 中性檢核：新父節點居中時，CPT 與 v0220 相同
    pso_old, pso_new = base.get_cpds("PumpStationOperation"), m.get_cpds("PumpStationOperation")
    mid = pso_new.state_names["DR.StructuralMeasures_Coverage"].index("中")
    assert np.allclose(pso_old.values, pso_new.values[..., mid])
    print(f"檢核通過：節點 {n0}，邊 {e0} -> {m.number_of_edges()}；DR.SMC=中 時 PumpStationOperation CPT 與 v0220 相同")
    print("\n擴充後的 CPT 片段：")
    show(pso_new, {"PowerSupplyReliability": "正常", "PumpMaintenanceFreq": "中"}, "DR.StructuralMeasures_Coverage")
    show(m.get_cpds("TidalBackwater"), {"NZ.SeaLevelRise_Scenario": "current"}, "RiverWaterLevel")
    with open(DST, "wb") as f:
        pickle.dump(m, f)
    meta = {"name": DST.name, "date": date.today().isoformat(), "base": SRC.name, "base_sha256": sha256(SRC),
            "sha256": sha256(DST), "nodes": m.number_of_nodes(), "edges": m.number_of_edges(),
            "status": "臺北端提案模型；未經臺南端裁定，不是共用基線",
            "rule": "新 CPT ∝ 舊 CPT × K^(方向 × ℓ × c)；ℓ=新父節點等級 ∈ [-1,1]，c=子節點置中序位；ℓ=0 時與 v0220 相同",
            "edges_added": report, "drt": "docs/DRT-TPE-20261029-003_hub_edges_proposal.md"}
    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n輸出 {DST.name}（{DST.stat().st_size / 1e6:.2f} MB）與 {META.name}")


if __name__ == "__main__":
    main()
