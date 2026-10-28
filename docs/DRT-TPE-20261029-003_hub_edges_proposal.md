---
id: DRT-TPE-20261029-003
title: bn_v0220_tpe1 — 臺北提案模型：加兩條邊（抽水 cms → 抽水運作、河川水位 → 外水頂托）
status: proposed（臺北端已建提案模型與前後比較）；採納與 CPT 校準待臺南端
date: 2026-10-29
depends_on: DRT-TPE-20261026-002（§10 路徑查核）
model: bn_v0220.pkl（不動）→ bn_v0220_tpe1.pkl（新檔，193 節點／271 邊）
---

## 1. 背景：為什麼是這兩條邊

10/29 用 networkx 直接查 `bn_v0220.pkl`（DRT-002 §10）：樞紐 ModifiedFloodPotential 的四個父節點（原始潛勢、抽水運作、外水頂托、環境減災整合）只有第一個有證據；93 里之間的差異全部來自潛勢圖錨定。北士科最關心的兩個機制，模型裡都接錯或沒接：

1. **抽水。** 里級建好的抽水容量證據 DR.StructuralMeasures_Coverage（集水分區面積加權 cms，里級分布 低 32／中 17／高 44）在 v0220 只通到 DrainageSystemEfficiency（→ 延時）與 A_b_LifelineAdaptation（→ R2），碰不到修正淹水潛勢。直接接樞紐的 PumpStationOperation 沒有任何證據：父節點 PumpMaintenanceFreq 是均勻先驗的根、PowerSupplyReliability 無證據，所以每一個里的「抽水運作」都是同一個平均值。10/22 單節點掃描裡 PumpStationOperation 是對綜合風險影響最大的節點（0.180）。北士科（洲美、建民）在關渡平原低地、堤內靠抽水站排內水，抽水能力是該區淹水的第一機制。
2. **外水。** RiverWaterLevel 是證據節點（臺北依臺南規則給值），但出邊為 0，證據進了模型什麼都不影響。LP.river_corridor_designation 唯一的子節點就是它，所以河廊劃設（里級有鑑別力：僅河道 67／緩衝帶 9／完整 17）也形同虛設。TidalBackwater 直接接樞紐，卻只有 NZ.SeaLevelRise_Scenario 一個父節點（其父 NZ.adaptation_mitigation_synergy 是均勻先驗的根），在臺北等於常數。北士科外側是基隆河、雙溪、磺港溪，外水位高時閘門關閉、內水只能靠抽水，「外水頂托」正是該區的物理機制。

兩條邊接上之後，抽水容量與河川水位都直接進修正淹水潛勢，整條下游（R1、延時、各基礎設施脆弱度、OUT 指數）才會對這兩項證據有反應。使用者 10/29 決定：先在臺北 repo 建提案模型推上 GitHub，供會議討論與臺南端審查。

## 2. 具體請求（對臺南端）

1. 採納 `DR.StructuralMeasures_Coverage → PumpStationOperation`、`RiverWaterLevel → TidalBackwater` 進共用基線（下一版 v022x）。
2. 兩張 CPT 的正式數值；本版是勝算權重佔位（§3）。
3. 是否同時把 PumpMaintenanceFreq、NZ.SeaLevelRise_Scenario 納入基線證據或給城市常數（它們仍是抽水運作、外水頂托的另一個父節點）。

## 3. 做法

- 不動 `bn_v0220.pkl`。`scripts/build_bn_tpe1_hub_edges.py` 讀 v0220 → `copy()` → 加邊 → 換兩張 CPT → `check_model()` → 另存 `bn_engine/bn_v0220_tpe1.pkl`（193 節點／271 邊）＋ `bn_v0220_tpe1_meta.json`（含兩檔 sha256、規則、日期）。
- CPT 擴充規則（佔位、未校準）：
  `新 CPT(child | 舊父節點, 新父節點) ∝ 舊 CPT(child | 舊父節點) × K^(方向 × ℓ × c)`
  ℓ＝新父節點狀態依序線性映射到 [−1, +1]；c＝子節點狀態的置中序位（三態為 −1, 0, +1）。ℓ＝0 時 w ≡ 1，與 v0220 完全相同（腳本 assert：DR.SMC＝中 時 PumpStationOperation 的 CPT 與 v0220 逐格相等）。K＝2 表示極端等級把兩端狀態的勝算比改變 K²＝4 倍。
  邊①方向 −1：抽水覆蓋越高，抽水運作越往「正常」。邊②方向 +1：河川水位越高（一級警戒），外水頂托越往「高」。
- 擴充後的 CPT 片段：

| PumpStationOperation｜供電正常、維護中 | 正常 | 低於正常 | 失效 |
|---|---|---|---|
| DR.SMC＝低 | 0.482 | 0.487 | 0.032 |
| DR.SMC＝中（＝v0220） | 0.657 | 0.332 | 0.011 |
| DR.SMC＝高 | 0.796 | 0.201 | 0.003 |

| TidalBackwater｜海平面 current | 低 | 中 | 高 |
|---|---|---|---|
| 河川水位＝正常 | 0.807 | 0.185 | 0.009 |
| 三級警戒 | 0.719 | 0.261 | 0.020 |
| 二級警戒 | 0.607 | 0.350 | 0.042 |
| 一級警戒 | 0.478 | 0.438 | 0.084 |

- 前後比較 `scripts/compare_tpe1_vs_v0220.py`：同一套 v2 里級輸入（H2 里級錨定表、evidence、E 節點）與同一個錨定函式 `run_inference_taipei.anchored_query`；A）93 里 × H1＝超大豪雨（E 24h500）的 MFP 與 O 期望值；B）焦點里（建民、洲美、福華、吉慶、一德）× 4 雨級的抽水運作、外水頂托、MFP、延時、R1–R3、O。輸出 `bn_engine/results/taipei_tpe1/`。

## 4. 決定（臺北端）

| # | 決定 | 理由 |
|---|---|---|
| D1 | 另存新檔，不覆寫 v0220 | AGENTS 不可碰清單；共用基線由臺南端管，臺北只提案 |
| D2 | 檔名 `bn_v0220_tpe1`，不佔臺南版號 | 臺南 v022x 由臺南端發；tpe1＝臺北提案 1 |
| D3 | CPT 用勝算權重擴充，ℓ＝0 時不變 | 沒有校準資料；「中」狀態回到 v0220，前後差異可全部歸因於新父節點 |
| D4 | K＝2 | 佔位；敏感度只要改常數重跑 |
| D5 | RiverWaterLevel 四態對映 −1, −1/3, +1/3, +1（正常 → 一級警戒），以三級與二級之間為中性 | 把 v0220 的 TidalBackwater CPT 當作「平均河況」 |
| D6 | v2 結果檔不動，比較輸出另放 `results/taipei_tpe1/` | v2 永遠對應 v0220，方便回溯 |

## 5. 結果（H1＝超大豪雨＋E 24h500，錨定，同一套 v2 里級輸入）

**機制有接上，但 K＝2 佔位下幅度小、排序不變。**

- 機制檢核（焦點里）：P(抽水運作＝正常) 在 v0220 全里同為 0.289（父節點均勻先驗的平均）；tpe1 依抽水覆蓋分成 高 0.388／中 0.289（＝v0220）／低 0.203。P(外水頂托＝高) 全里一致 +0.04（臺北 RiverWaterLevel 93 里全部＝二級警戒，ℓ＝+1/3）。
- 93 里 MFP 期望值變化：抽水覆蓋 高（44 里）平均 −0.040、中（17 里）+0.017、低（32 里）+0.076；高低兩組差 0.116。「中」組的 +0.017 就是純河川水位效應。
- 93 里 O_total 期望值：均值 0.5085 → 0.5088；只有 29 個有潛勢區暴露的里變動，64 個停在底值 0.2921 的里完全不動（MFP 變了 O 也不動：O 對 MFP 的敏感度在暴露節點為 very_low 時趨近 0，是 v0220 既有性質）。ΔO 範圍 −0.020（吉慶）到 +0.021（一德）；新舊排序 Spearman 0.9999。
- 北士科兩里（抽水覆蓋皆為 高）：

| 里 | 雨級 | MFP v0220 → tpe1 | O v0220 → tpe1 |
|---|---|---|---|
| 建民 | 超大豪雨 | 0.485 → 0.445 | 0.783 → 0.775 |
| 建民 | 極端降雨 | 1.684 → 1.635 | 1.017 → 1.008 |
| 洲美 | 超大豪雨 | 0.726 → 0.682 | 0.978 → 0.967 |
| 洲美 | 極端降雨 | 2.080 → 2.034 | 1.311 → 1.300 |

- 對照：一德（抽水 低）超大豪雨 MFP 0.660 → 0.739、O 1.290 → 1.310；吉慶（高）1.590 → 1.529、1.623 → 1.603；福華（中，士林）只受河川效應 0.348 → 0.366、1.150 → 1.154。

讀法：兩條邊讓抽水容量第一次進到淹水本身，里級的抽水差異（三級）開始有作用；外水頂托因臺北河川水位是區級複製，目前只是整體位移。幅度由 K 決定，K＝2 是佔位，綜合風險變化 ≤ 0.02；正式幅度要等臺南端給 CPT 或校準。檔案：`bn_engine/results/taipei_tpe1/compare_tpe1_vs_v0220_93villages.csv`、`compare_tpe1_vs_v0220_focus.csv`、`summary.json`。

## 6. 需要臺南端回覆

§2 三項，另加：K 的量級是否合理（或給出 CPT）；RiverWaterLevel 的中性點放哪一級。

## 7. Known limitations

- 兩張 CPT 是佔位規則，不是專家或資料校準；數字只能看方向與相對大小。
- 臺北的 RiverWaterLevel 是區級複製（里間同值），邊②在里級地圖上是整體位移，不改變里間排序；要有里級河川水位（測站對應堤防與閘門）才有鑑別力。
- 抽水運作的另外兩個父節點（維護頻率、供電可靠度）仍無證據；外水頂托的海平面情境亦同。
- v0220 其餘既有問題（CPT 方向反置、豪雨／大豪雨同值、E 節點切點）原樣存在。

## 8. 交付

`bn_engine/bn_v0220_tpe1.pkl`、`bn_engine/bn_v0220_tpe1_meta.json`、`scripts/build_bn_tpe1_hub_edges.py`、`scripts/compare_tpe1_vs_v0220.py`、`bn_engine/results/taipei_tpe1/compare_tpe1_vs_v0220_93villages.csv`、`compare_tpe1_vs_v0220_focus.csv`、`summary.json`、結構圖 `docs/figures/bn_hub_two_edges.png`。

## 9. 不動清單

`bn_engine/bn_v0220.pkl`、`bn_engine/reference_tainan/`、`bn_engine/results/taipei_v1/`、`bn_engine/results/taipei_v2_village/`（本次未改）、v1／v2 腳本既有函式。
