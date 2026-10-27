# AGENTS.md — taipei-flood-bn

## 這個 repo 是什麼

這是臺北市士林區、北投區（北士科所在）淹水風險貝氏網路的 **「A. 直接移植」版**，版本代號 `taipei_v1`。模型來源是 NTU-STEMLab `tainan-flood-bn` v0.22.0：臺南市 37 區、`bn_v0220.pkl`、193 節點／269 邊、pgmpy。

- **模型本體不動**：pkl、所有 CPT、節點、狀態原封不動，包括臺南端已知的問題，例如 SMC→DSE 與 NbS→RC 兩條 CPT 方向反置。
- **只換三份輸入**：
  1. H2 錨定表：臺北淹水潛勢圖；
  2. 區級 16 節點 status-quo evidence；
  3. 潛勢區暴露 E 節點：依臺南五分位邊界歸級。
- **推論方法照抄臺南**：v0212 virtual evidence 錨定、v0220 O_total Dirichlet MC 與三軸政策分解、v0214 NbS 政策感知位移。

## 目錄導覽

| 路徑 | 內容 |
|---|---|
| `bn_engine/bn_v0220.pkl` | 臺南 v0.22.0 原檔。**不可修改** |
| `bn_engine/cpt_priors/h2_district_conditional_table_taipei_v1.json` | 臺北 H2 錨定表：2 區 × 4 雨級 × FD1–5 |
| `bn_engine/reference_tainan/` | 臺南參考表副本，是切點與對照來源，含 `ototal_mc_v0220.csv`、`ototal_baseline_posteriors_v0220.json`、`E_node_levels_v0213.csv` 等。**既有檔不可修改**，可新增，但要註明來源與 md5 |
| `bn_engine/results/taipei_v1/` | v1 全部輸出與 `taipei_v1_close_report.md`、`taipei_v1_summary.json`。保留原樣，作為比對基準 |
| `data/taipei/` | 臺北輸入副本，共 12 檔：潛勢圖 zip、LULC zip、里界 zip、抽水站、收容所、人口、獨居、身障、低收、集水分區 KML |
| `data/_unzipped/` | 執行時自動解壓的目錄，已列入 .gitignore |
| `docs/DRT-TPE-*.md` | 臺北端決策紀錄，格式比照臺南 DRT |
| `docs/evidence_mapping_taipei_v1.md` | 每個 evidence 節點的對照：臺北原始值 → 狀態 → 沿用的臺南切點 → 可比性 |
| `scripts/` | 腳本，見下一節 |

## 腳本執行順序（在 `scripts/` 目錄下執行，模組彼此以同目錄 import）

| 順序 | 腳本 | 主要輸入 | 輸出（`bn_engine/...`） |
|---|---|---|---|
| 1 | `build_shp_baseline_taipei.py` | `data/taipei/flood_potential_taipei_10scenarios_shp.zip`、里界（經 `taipei_paths.districts_gdf()` dissolve 成區界） | `results/taipei_v1/shp_baseline_taipei_v1.csv`、`cpt_priors/h2_district_conditional_table_taipei_v1.json` |
| 2 | `build_district_base_taipei.py` | 人口（經 `taipei_common.py`）、`pump_stations_shilin_beitou.csv`、`shelters_taipei.csv`、LULC zip | `results/taipei_v1/district_base_indicators_taipei_v1.csv`、`lulc_aggregation_taipei_v1.csv` |
| 3 | `compute_E_exposure_taipei.py` | 潛勢圖 zip、LULC zip、人口分層、`reference_tainan/E_node_levels_v0213.csv`、`FloodZone_Vulnerable_Ratio_levels_v0214a.csv` | `results/taipei_v1/E_stratified_exposure_taipei_v1.csv`、`E_node_levels_taipei_v1.csv` |
| 4 | `compose_evidence_taipei.py` | `district_base_indicators_taipei_v1.csv`；pkl 只用來檢核狀態字串 | `results/taipei_v1/evidence_per_district_taipei_v1.json` |
| 5 | `run_inference_taipei.py [all\|baseline\|mc\|policy]` | pkl、H2 JSON、evidence JSON、E 等級、`lulc_aggregation`、`reference_tainan/ototal_mc_v0220.csv` | `posteriors_all_h1_taipei_v1.csv`、`ototal_baseline_posteriors_taipei_v1.json`、`ototal_mc_taipei_v1.csv`、`ototal_mc_joint_tainan37_taipei2_v1.csv`、`ototal_policy_decomposition_taipei_v1.csv`、`taipei_v1_summary.json` |

共用模組：
- `taipei_paths.py`：定義 ROOT、DATA、REF、OUT、CPT、TMP、DISTRICTS，以及 `unzip_dir`、`districts_gdf`、`read_csv_any`。
- `taipei_common.py`：`district_population_strata()`。

上游任何一步有改動，下游都要依序重跑。規劃中但尚未存在的檔案：`check_consistency_taipei.py`（C30），以及 `run_inference_taipei.py` 的 `regress`、`validate` stage（C30、C04）。

## taipei_v2_village（里級版）腳本順序

| 順序 | 腳本 | 輸出（`bn_engine/...`） |
|---|---|---|
| 1 | `build_shp_baseline_village.py` | `results/taipei_v2_village/shp_baseline_village_v2.csv`、`cpt_priors/h2_village_conditional_table_taipei_v2.json` |
| 2 | `build_village_base.py` | `results/taipei_v2_village/village_base_indicators_v2.csv`、`lulc_aggregation_village_v2.csv`、`pump_catchment_mapping_v2.csv`、`shelter_service_mapping_v2.csv` |
| 3 | `compute_E_exposure_village.py` | `E_stratified_exposure_village_v2.csv`、`E_node_levels_village_v2.csv` |
| 4 | `compose_evidence_village.py` | `evidence_per_village_taipei_v2.json` |
| 5 | `run_inference_village.py [all\|baseline\|mc\|policy]` | `results_village_v2.csv`、`posteriors_all_h1_village_v2.csv`、`ototal_*_village_v2.*`、`taipei_v2_village_summary.json` |
| 6 | `make_village_maps.py` | `map_village_v2_超大豪雨.png`、`results_village_v2.geojson`、`bstp_neighbourhood_villages_v2.csv` |
| 7 | `make_bstp_map.py`（用 `data/taipei/taipei_zone_expropriation_ZEPN.zip` 地政局區段徵收區 SHP） | `map_bstp_villages_v2.png`、`bstp_villages_v2.csv`、`bstp_boundary_and_villages_v2.geojson` |

注意：
- 里的鍵是 `unit`＝區名＋里名（`士林區福安里`），由 `taipei_paths.villages_gdf()` 產生；所有 v2 表、evidence JSON、H2 錨定表都用這個鍵。
- v2 腳本 import v1 的規則函式（`compose_evidence_taipei`、`compute_E_exposure_taipei`、`run_inference_taipei`），所以要在 `scripts/` 目錄下執行，**不能用 `python -I`**（會拿掉同目錄 import）。
- v1 模組 import 時已把 stdout 包成 UTF-8；v2 腳本用 `if getattr(sys.stdout, "encoding", "")...` 守衛避免重複包裝（重複包裝會造成 `I/O operation on closed file`）。
- 里級人口檔 `data/taipei/pop_by_age_village_shilin_beitou_112-115.csv` 是 data.taipei「臺北市各里人口數按年齡分」的里列子集（112/1–115/9）；v1 用的 `pop_by_age_village_2023-01.csv` 其實是區列，別拿來當里級。
- `bn_engine/results/taipei_v2_village/` 是 v2 基準輸出；下一版輸出到 `taipei_v2a/` 等新目錄。

## 不可碰的東西

1. `bn_engine/bn_v0220.pkl`，以及任何 CPT、節點、狀態、邊。模型問題一律回臺南 repo 開 DRT，本 repo 只能記錄成「需要臺南端回覆」。
2. `bn_engine/reference_tainan/` 的既有檔。
3. `bn_engine/results/taipei_v1/`。新版輸出到 `taipei_v1a/` 等新目錄。
4. 臺南 repo `C:\Users\R1462\OneDrive\中鋼計畫\tainan-flood-bn-20260903` 與資料倉 `C:\Users\R1462\OneDrive\中鋼計畫\團隊內部討論紀錄\中綱BN建構\Data\Data_taipei`，兩者唯讀。
5. 基線 evidence 集合（16 個 status-quo 節點加 8 個 E 節點）要與臺南 v0188 相同。只有臺北才有的新節點或新口徑，只能做成敏感度臂。

## 環境

- Windows 10、Python 3.14、pgmpy 1.1.2、geopandas 1.x、pyogrio、shapely 2、pyproj（README 寫明為實測環境）。目前 `requirements.txt` 寫 `pgmpy>=1.1.2`，應鎖成 `==1.1.2`（見 C31）。virtual evidence 用的是 pgmpy 1.1.x 的 API。
- 執行指令：

```bash
pip install -r requirements.txt
cd scripts
python build_shp_baseline_taipei.py
python build_district_base_taipei.py
python compute_E_exposure_taipei.py
python compose_evidence_taipei.py
python run_inference_taipei.py all
```

## 編碼與路徑注意事項

- 路徑含中文（`中鋼計畫`）而且在 OneDrive 底下。shell 一律用加引號的絕對路徑；Git Bash 寫成 `/c/Users/R1462/OneDrive/中鋼計畫/...`。
- 各腳本開頭已把 stdout 包成 UTF-8，新腳本照做。輸出 CSV 用 `utf-8-sig`，JSON 用 `utf-8` 加 `ensure_ascii=False`。
- 讀臺北開放資料時，有些 CSV 是 Big5／cp950（例如 Data_taipei 的全市里級人口檔、醫院清冊），有些是 UTF-8-BOM。一律透過 `taipei_paths.read_csv_any()` 自動判斷。zip 內檔名可能是 cp437 誤標，`unzip_dir()` 已處理 big5／cp950 轉換。
- **狀態字串必須與 pkl 的 `state_names` 逐字相同**，包括全形、半形、空白與括號，例如 `含河岸緩衝帶 (<30m)`；否則 `clean_evidence()` 會靜默丟棄。新增 evidence 後要檢查 `n_evidence`，並列出被丟棄的鍵。
- 常見的對照陷阱：
  - 保全計畫寫「富州里」，里界與門牌檔寫「富洲里」；
  - 抽水站有三站在兩個來源中所屬行政區不同（大龍、洲美、社子）；
  - 臺北潛勢圖 GRIDCODE 1 對應臺南 GC2（≥0.3 m）。

## 與臺南 repo 的關係

- 臺北是**下游移植**，不是臺南的分支。臺南若升版 pkl（例如 v0.22.x 修正方向反置邊、AHP 權重取代等權），臺北必須重跑並升版。
- 臺南的規範沿用到臺北：
  - 模型或輸入修改要留 DRT；
  - 每一版都要有 close report，內容包括回答問題、方法、驗證、交付清單、Known limitations、不動清單；
  - 回退要誠實記錄。
- 引用臺南 DRT 時寫「截至 2026-09-03 快照、編號至 DRT-082」。
- 不得把臺南的 Brier 數字當成臺北成績；所有輸出都只能是**事件條件機率**，不得寫成年度風險。
- 臺北 E 節點等級的意思是「放進臺南 37 區分布中屬第幾級」，解讀時要記得這一點。

## 提交規範

1. 從 `main` 開分支，命名為 `taipei_v1a/<主題>`，例如 `taipei_v1a/c01-age-structure`。
2. 一個候選（或一組緊密相關的候選）對應一個 commit。commit 訊息用繁體中文，格式為 `taipei_v1a: [C01] 年齡結構改取 114/12 單期`，內文列出變更檔與驗證結果。
3. 每個 commit 都要同步更新：對應的 `docs/DRT-TPE-*.md` 段落（背景、方法、結果、resolution、known limitations、交付、不動清單），以及受影響的 `docs/evidence_mapping_*.md`、README 與 close report。
4. 不得提交 `data/_unzipped/`；不得把整個 Data_taipei 大檔放進 repo，只放必要的子集，並在 README 寫明來源。
5. 提交前必須跑 regress 與 check_consistency（C30 完成後），而且全部 PASS。
6. 未經使用者同意，不 push、不改 remote、不改寫歷史。
