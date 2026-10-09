# taipei_v1 Close Report — 臺南 BN v0.22.0 直接移植到臺北士林、北投

> 日期：2026-10-10
> 模型：`bn_engine/bn_v0220.pkl`（NTU-STEMLab/tainan-flood-bn，193n/269e）— **原檔未動**
> 對應決策紀錄：`docs/DRT-TPE-20261010-001_transplant_v0220_to_taipei.md`

## 1. 做了什麼

| 步驟 | 臺南對應 | 臺北做法 | 產出 |
|---|---|---|---|
| A1 H2 錨定表 | v0.19.1 SHP 統計 + v0.21.2 條件經驗表 | 水利署臺北淹水潛勢圖 10 情境 ∩ 區界；深度級 GC1–5 對齊臺南 GC2–6 | `cpt_priors/h2_district_conditional_table_taipei_v1.json`、`shp_baseline_taipei_v1.csv` |
| B1 區級指標 | v0.15.1 VS、v0.18.5 A4/A5、v0.18.6 LULC | 主計處資料庫、民政局里級人口、水利處抽水站半年報、收容所一覽、LULC 112 年 | `district_base_indicators_taipei_v1.csv`、`lulc_aggregation_taipei_v1.csv` |
| B2 E 節點 | v0.21.3 暴露存量 + 五分位 | 同法計算存量；以臺南各級邊界中點歸級（2 區無法做分位數） | `E_stratified_exposure_taipei_v1.csv`、`E_node_levels_taipei_v1.csv` |
| B3 evidence | v0.18.8 16 節點 | 同切點／規則映射，狀態字串逐一與 pkl 檢核 | `evidence_per_district_taipei_v1.json` |
| C 推論 | v0.21.2 錨定、v0.22.0 MC 與政策分解 | 2 區 × 4 雨級 × {錨定, 全域}；MC N=1000 Dir(4,4,4) seed 42；do(三軸)+NbS 位移 α=0.51 | `posteriors_all_h1_taipei_v1.csv`、`ototal_*_taipei_v1.csv`、`taipei_v1_summary.json` |

每區 evidence 共 24 個（16 status-quo + 8 E 節點），與臺南 v0.22.0 基線相同。

## 2. 基線結果（H1=超大豪雨 + E 24h500 + 錨定）

| 區 | OFP (FD1..FD5) | MFP EV | FloodDuration EV | OUT_FRI EV | R1 EV | R2 EV | R3 EV | O_total 後驗（極低…極高） | O EV |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 士林區 | .993/.004/.003/.000/.000 | 0.255 | 0.860 | 1.721 | 0.221 | 1.018 | 0.417 | .364/.523/.107/.005/.000 | 0.754 |
| 北投區 | .933/.011/.015/.023/.018 | 0.407 | 0.923 | 1.861 | 0.328 | 1.731 | 0.510 | .181/.539/.235/.042/.003 | 1.148 |

Dirichlet 權重 MC（與臺南同抽樣）：北投 1.148 [0.755, 1.643]、士林 0.756 [0.547, 1.026]。放進臺南 37 區：北投第 14（安南區 1.1485、北投 1.1484、中西區 1.126），士林第 26（新化 0.768 之後；兩區同列時第 27）。

### 四雨級掃描（錨定）

| 區 | 節點 | 豪雨 | 大豪雨 | 超大豪雨 | 極端降雨 |
|---|---|---:|---:|---:|---:|
| 士林區 | OFP EV | 0.001 | 0.004 | 0.011 | 0.122 |
| 士林區 | R2 EV | 1.017 | 1.017 | 1.018 | 1.020 |
| 士林區 | O_total EV | 0.753 | 0.753 | 0.754 | 0.775 |
| 北投區 | OFP EV | 0.000 | 0.007 | 0.182 | 0.544 |
| 北投區 | R2 EV | 0.163 | 0.163 | 1.731 | 1.743 |
| 北投區 | O_total EV | 0.366 | 0.367 | 1.148 | 1.243 |

全域（不錨定）對照：OFP EV 兩區皆為 0.022/0.063/0.121/0.213（pkl 內 CPT 不分區）；錨定把士林的 OFP 壓到更低、北投在超大豪雨以上拉高，與潛勢圖一致。

## 3. 三軸政策分解（status quo vs do(NbS=高, DR.SMC=高, DR.NS=高) + NbS 錨定位移）

| 區 | status quo SMC/DRNS | ΔNbS_eff (%-pt) | O_EV base | O_EV do | RR_total | 貢獻 R1/R2/R3 % | RR（DSE 修，上界） |
|---|---|---:|---:|---:|---:|---|---:|
| 士林區 | 高/高 | 2.85 | 0.754 | 0.759 | −0.005 | 49 / 6 / 45 | +0.032 |
| 北投區 | 高/高 | 3.08 | 1.148 | 1.155 | −0.007 | 56 / 8 / 36 | +0.046 |

讀法與臺南 v0.22.0 相同：兩區 status quo 政策存量皆「高」，RR 微負不是政策有害，是 SMC→DSE、NbS→RC 兩條 CPT 方向反置的洩漏；DSE 修正臂給出修正後效益的上界。R2 貢獻在臺北只有 6–8 %（臺南低存量區 >100 %），因為 DR.SMC 已是「高」、do() 沒有位移空間。

## 4. 行為觀察（誠實版）

1. **北投的階梯**：R2 EV 0.163 → 1.731、O 0.37 → 1.15 發生在「大豪雨→超大豪雨」，驅動者是 E 節點情境切換（24h350 → 24h500：北投潛勢區人口比例 0.0002 → 0.070、建築 0.02 % → 6.98 %），不是 BN 內部對降雨的反應。
2. **降雨幅度傳不到 O_total**：士林四雨級 O 只差 0.022；與臺南行為測試一致。
3. **R2 幾乎只由 E 節點決定**：士林 R2 在四雨級都 ≈1.02，北投在 24h350 情境下 0.163、在 24h500 下 1.73。
4. **無鑑別力節點**：DR.StructuralMeasures_Coverage、LP.river_corridor_designation、ElderlyAlone_Ratio（臺南 31/37 區 very_high）。
5. **與臺南的相對位置合理**：北投（關渡平原潛勢區 10.9 %、R2 高）落在安南區旁邊；士林（潛勢區 0.7 %）落在後段，但因 R2 ≈1.02 不會掉到最尾端。

## 5. 未做／待辦

- 驗證：未做。候選 ground truth 已在 Data_taipei（EMIC 2006–2021 士林北投 6,822 筆、1999 派工定位到里 626 筆、積水事件查詢網 2021–2026、歷史積水 KML 714 筆）；需先決定標籤與基準（climatology、只看雨級）。
- 北士科尺度：本版單位是行政區；北士科（洲美／文林集水區 48–55 ha）要靠 B 版或外疊圖。
- 區級指標分母含山區的稀釋問題；RiverWaterLevel 二級／三級的敏感度未跑。
- AHP 權重替換等權（臺南同待辦）。

## 6. 交付清單

`bn_engine/cpt_priors/h2_district_conditional_table_taipei_v1.json`、`bn_engine/results/taipei_v1/*`（10 檔）、`scripts/*_taipei.py`（5 支＋2 個共用模組）、`docs/evidence_mapping_taipei_v1.md`、`docs/DRT-TPE-20261010-001_transplant_v0220_to_taipei.md`、`data/taipei/*`（12 檔輸入副本）。
