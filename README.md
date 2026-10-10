# 臺北市士林、北投淹水風險貝氏網路 — 臺南 BN v0.22.0 直接移植版（taipei_v1）

## 定位

本 repo 是 [NTU-STEMLab/tainan-flood-bn](https://github.com/NTU-STEMLab/tainan-flood-bn)（NSC 2025 中綱計畫，臺南市 37 行政區淹水風險 BN，v0.22.0，193 節點／269 邊）的**「A. 直接移植」版**：

- **模型本體完全不動**：`bn_engine/bn_v0220.pkl`、所有 CPT、節點與狀態都原封不動（含臺南端已知的 CPT 方向反置等問題）。
- **只換三份輸入**：H2 錨定表（臺北淹水潛勢圖）、區級 status-quo evidence（臺北資料）、潛勢區暴露 E 節點（臺北暴露，以臺南五分位邊界歸級）。
- **推論方法照抄**：district 條件化（virtual evidence 錨定 OriginalFloodPotential）、O_total Dirichlet 權重 MC、三軸政策分解，全沿 `per_district_conditional_inference_v0212.py` / `run_ototal_mc_v0220.py` / `policy_aware_anchored_inference_v0214.py`。

研究區：臺北市士林區、北投區（北投士林科技園區所在），作為子二 BN 落地北士科的第一步；之後的「B. 北士科專用小模型」另立版本。

## 內容導覽

| 內容 | 位置 |
|---|---|
| BN 模型（臺南 v0.22.0 原檔，pgmpy 1.1.2） | `bn_engine/bn_v0220.pkl` |
| **臺北 H2 錨定表**（2 區 × 4 雨級 × FD1–5） | `bn_engine/cpt_priors/h2_district_conditional_table_taipei_v1.json` |
| **臺北區級 evidence**（16 節點＋原始值＋規則理由） | `bn_engine/results/taipei_v1/evidence_per_district_taipei_v1.json` |
| 潛勢區暴露存量與 E 節點等級 | `bn_engine/results/taipei_v1/E_stratified_exposure_taipei_v1.csv`、`E_node_levels_taipei_v1.csv` |
| 區級原始指標、LULC 四指標、潛勢圖區級統計 | `bn_engine/results/taipei_v1/district_base_indicators_taipei_v1.csv`、`lulc_aggregation_taipei_v1.csv`、`shp_baseline_taipei_v1.csv` |
| **推論結果**（2 區 × 4 雨級 × 錨定／全域後驗、O_total MC、與臺南 37 區並列、政策分解） | `bn_engine/results/taipei_v1/posteriors_all_h1_taipei_v1.csv`、`ototal_mc_taipei_v1.csv`、`ototal_mc_joint_tainan37_taipei2_v1.csv`、`ototal_policy_decomposition_taipei_v1.csv` |
| 結案報告 | `bn_engine/results/taipei_v1/taipei_v1_close_report.md` |
| **Evidence 對照表**（每個節點：臺北原始值 → 狀態 → 沿用的臺南切點 → 資料來源 → 可比性） | `docs/evidence_mapping_taipei_v1.md` |
| 移植決策紀錄（比照臺南 DRT 格式） | `docs/DRT-TPE-20261010-001_transplant_v0220_to_taipei.md` |
| **給 Codex 的審查任務簡報**（先讀臺南、再審臺北、逐條提修改方案） | `docs/CODEX_BRIEF.md` |
| **已驗證優化候選清單**（16 確認／20 駁回／6 未驗證，含審查投票與修正版做法） | `docs/optimization_candidates_v1.md` |
| AI 代理（Codex 等）的工作守則：腳本順序、不可碰清單、編碼注意、提交規範 | `AGENTS.md` |
| 臺南參考表（切點來源，從 tainan-flood-bn 複製） | `bn_engine/reference_tainan/` |
| 臺北輸入資料副本（CSV、潛勢圖 SHP、LULC、里界） | `data/taipei/` |
| 腳本（依執行順序） | `scripts/` |

## 快速開始

```bash
pip install -r requirements.txt
cd scripts
python build_shp_baseline_taipei.py      # 潛勢圖 → 區級經驗表 → H2 錨定表
python build_district_base_taipei.py     # 人口分層、抽水量、收容所、LULC
python compute_E_exposure_taipei.py      # 潛勢區暴露 → E 節點等級
python compose_evidence_taipei.py        # 16 節點 status-quo evidence
python run_inference_taipei.py all       # baseline / mc / policy
```

所有輸入都在 `data/taipei/`，不需要外部路徑；`data/_unzipped/` 會在第一次執行時自動產生。

## 結果摘要（H1 = 超大豪雨 + E 24h500 + district 錨定，等權 w，與臺南 v0.22.0 同設定）

| 區 | R1_EV | R2_EV | R3_EV | O_total EV（MC 均值） | 95 % CI | 放進臺南 37 區的排名 |
|---|---:|---:|---:|---:|---|---:|
| 北投區 | 0.328 | 1.731 | 0.510 | **1.148** | [0.755, 1.643] | 14（緊鄰安南區 1.1485） |
| 士林區 | 0.221 | 1.018 | 0.418 | **0.756** | [0.547, 1.026] | 26（兩區同列時 27） |

四雨級的 O_total EV（錨定）：士林 0.753 / 0.753 / 0.754 / 0.775；北投 0.366 / 0.367 / 1.148 / 1.243（豪雨→極端降雨）。

三軸政策 do(NbS=高, DR.SMC=高, DR.NS=高)：RR_total 士林 −0.005、北投 −0.007（與臺南已高政策存量區一樣微負，是上游 CPT 方向反置的洩漏）；DSE 修正敏感度臂 +0.032 / +0.046。

## 讀結果前必看的限制

1. **這是移植版，不是臺北模型**：所有切點、CPT、權重都是臺南的；臺北只有兩區，E 節點的 very_low…very_high 是「放進臺南 37 區分布中屬第幾級」。
2. **北投的 R2／O_total 在「大豪雨→超大豪雨」之間跳一級**（0.37 → 1.15），不是降雨本身的效果，而是 E 節點情境從 24h350 切到 24h500 時，北投的潛勢區暴露從 very_low 跳到 high／very_high（關渡平原）。臺南端已知的「FloodZone_* 情境內五分位」行為在這裡以階梯形式出現。
3. **降雨幅度幾乎傳不到 O_total**（士林四雨級只差 0.02），與臺南 v0.22.0 行為測試結論相同。
4. **兩個節點在臺北沒有鑑別力**：DR.StructuralMeasures_Coverage（臺北任一區抽水量都超過臺南最高值，一律「高」）、LP.river_corridor_designation（規則只看水利用地占比，臺北河濱系統看不見，一律「僅河道用地」）。
5. 區級指標分母含山區（兩區一半以上是陽明山），不透水率、NbS、綠基盤占比都被稀釋。
6. 臺南端未裁定的問題原樣存在：VS 切點文件版與實作版不一致、SMC→DSE 與 NbS→RC 的 CPT 方向反置、Brier 數字不能直接引用。
7. 沒有做任何驗證：士林北投 2016 年洲美抽水站啟用後幾乎沒有 ≥15 cm 積水紀錄，正樣本不足；EMIC／1999／積水事件資料已備妥（見資料來源），驗證設計另案。

## 資料來源

臺北輸入檔均為政府開放資料或官方文件，整理於 `中鋼計畫\團隊內部討論紀錄\中綱BN建構\Data\Data_taipei\`（README 有每檔出處）；本 repo `data/taipei/` 為副本。主要來源：水利署臺北市淹水潛勢圖（2016 二次更新）、水利處「臺北市現有雨水抽水站設施概況」115 上半年、臺北市統計資料庫（人口密度、獨居老人、身心障礙 114 年底）、民政局各里人口數按年齡分（112/1）與里界圖、教育局可供避難收容處所一覽表、國土測繪中心土地利用現況調查 112 年。

## 協作約定（沿臺南）

1. 模型本體若要改（CPT、節點、切點），回到 tainan-flood-bn 開 DRT；本 repo 只改輸入與臺北專屬文件。
2. 版本命名 `taipei_v<n>`；每版附 close report 與 evidence 對照表更新。
3. 執行環境：Python 3.14、pgmpy 1.1.2、geopandas 1.x（Windows 實測）。
