---
id: DRT-TPE-20261026-002
title: taipei_v2_village — 空間單元由 2 區改為 93 里（輸入層里級化）
status: resolved（臺北端）；臺南端待回覆項見第 6 節
date: 2026-10-26
depends_on: DRT-TPE-20261010-001
model: bn_v0220.pkl（不動）
---

## 1. 背景

10/22 會議（余老師）定調：北士科的空間呈現要用里；有里級資料就用里級，只有區級的同區各里同值。
v1（taipei_v1）只有士林、北投 2 區，區級指標被山區稀釋（不透水率兩區都「中」）、E 節點只能用臺南邊界歸級、北士科在區級下看不見。

## 2. 具體請求

1. 以里級或更細的資料為優先，有就取來更新 BN 輸入。
2. 列出每一項輸入的資料尺度，放到 GitHub。

## 3. 做法

- 空間單元：民政局里界圖 456 里中取士林 51 里＋北投 42 里；鍵 `unit`＝區名＋里名（如 `士林區福安里`）。
- H2 錨定表：潛勢圖 10 情境 overlay 里界（`build_shp_baseline_village.py`）。檢核：93 里加總回推 2 區，與 v1 區級表最大差 0.000000。
- 人口分層：data.taipei「臺北市各里人口數按年齡分」最新一期（115/9）里列；獨居、身障為區級比例複製（`taipei_common.village_population_strata`）。
  附帶修正：v1 用的 `pop_by_age_village_2023-01.csv` 其實是區列（檔名誤導），而且把 112/1–115/7 多期加總當比例（C01）；v2 改單一期、里列。
- LULC 四指標：國土利用現況調查 112 年 overlay 里界（`build_village_base.py`），規則同 v0186。
- 抽水量：抽水站點位 → 雨水下水道集水分區（within，否則 500 m 內最近）→ 分區 cms → 里的面積加權有效 cms。
- 收容所：一覽表「服務里別」逐里計數（「全區」＝該區全部里），只用「鄉鎮」欄判區（修 C02 的郵遞區號誤算）；里名正規化（省略「里」字、「福佳港」筆誤、「富州里」＝「富洲里」）。
- E 節點：LULC 代表點 → 里 → 潛勢區內外（`compute_E_exposure_village.py`）；離散化沿 v1 臺南絕對切點，另附 `level_q93`。
- 推論：`run_inference_village.py` 直接 import v1 的推論函式，只換三份輸入；93 里 × 4 雨級錨定後驗、H1 基線全域後驗、O_total Dirichlet MC、三軸政策分解。
- 地圖：`make_village_maps.py`；北士科示意中心（121.507°E、25.105°N）1.5 km 內 25 里清單。

## 4. 決定（臺北端）

| # | 決定 | 理由 |
|---|---|---|
| D1 | E 節點基線離散化用臺南絕對切點，不用 93 里分位數 | CPT 是在「等級＝臺南 37 區分布位置」的語意下建的；里級分位數會把「無暴露」與「低暴露」的差別抹掉。相對分級保留為 `level_q93` 供敏感度 |
| D2 | 抽水量用集水分區面積加權 | 抽水站是點，不屬於里；集水分區是水利處官方的服務範圍。重力排水區與山區給 0 cms 是「無抽水設施」的真實狀態 |
| D3 | 收容所用「服務里別」而非「設在里內」 | AccessToShelters 的語意是可及性；同時保留 `shelters_located_in_village` |
| D4 | 區級複製的節點照臺南規則不升級（獨居、身障、DR.NonStructural、RiverWaterLevel） | 基線集合與口徑要與臺南 v0188 相同；里級升級方案列在 `docs/data_input_scale_taipei_v2.md` 表 A 末欄 |
| D5 | 人口期別取 115/9 單期 | 最新；同時修 C01 |
| D6 | v1 輸出目錄不動，v2 另立 `bn_engine/results/taipei_v2_village/` | AGENTS 不可碰清單 |

## 5. 結果摘要

- H1＝超大豪雨＋E 24h500、錨定、等權：64 里無潛勢區暴露（O_total 0.292 底值）；前十里吉慶 1.62、立賢 1.56、八仙 1.54、立農 1.47、一德 1.29、尊賢 1.24、大同 1.19、福華 1.15、豐年 1.08、福安 1.07。
- 里級 evidence 的鑑別力：不透水率 極低 1／低 7／中 12／高 16／極高 57；抽水 低 32／中 17／高 44；NbS 低 64／中 12／高 17；河廊 僅河道 67／緩衝帶 9／完整 17。無鑑別力：獨居（全 very_high）、身障（全 medium）、收容所（全 高）、三個知識法則節點。
- 政策分解：RR_total 均值 0.010、最大 0.115（一德里）；無暴露里為 0；少數微負（上游 CPT 反置洩漏，同 v1）。

## 6. 需要臺南端（Mike）回覆

1. E 節點在里尺度的離散化：絕對切點（本版）或單位內分位數？計數型節點（*_Count、Agri_km2）是否該改成密度／比例定義？
2. DR.StructuralMeasures_Coverage 的里級定義（集水分區面積加權 cms）是否接受；臺南是否也有集水分區圖可同法。
3. AccessToShelters 在臺北全為「高」，是否改用「設在里內」或改切點。
4. BuildingDensity 是否改用 LULC 建築用地占比（里級已備）。
5. （2026-10-29 新增）加邊 `DR.StructuralMeasures_Coverage → PumpStationOperation`，擴 PumpStationOperation 的 CPT：抽水容量證據現在只通到 DrainageSystemEfficiency 與 A_b_LifelineAdaptation，碰不到 ModifiedFloodPotential；直接接樞紐的 PumpStationOperation 無任何證據。見第 10 節與 `docs/figures/bn_hub_two_edges.png`。
6. （2026-10-29 新增）加邊 `RiverWaterLevel → TidalBackwater`，擴 TidalBackwater 的 CPT：RiverWaterLevel 出邊為 0，LP.river_corridor_designation 與 Rainfall 到此為止；TidalBackwater 只有 NZ.SeaLevelRise_Scenario 一個父節點。北士科在堤內靠抽水排內水，外水頂托是其主要淹水機制。見第 10 節。

## 7. Known limitations

- 關渡、知行兩個集水分區在 115 上半年站表無同名站（可能為水利署或其他單位管理），暫以 0 cms 計。
- 北士科正式範圍已於 10/27 取得（地政局區段徵收區 SHP，104.99 ha）：只與建民里（50%）、洲美里（49%）有交集，福興里 0.4% 為邊界切割；1.5 km 圓僅作周邊參考。
- 區級複製的四個節點在里級地圖上沒有變化，R3 弱勢鏈的里間差異只來自里級年齡結構與潛勢區暴露。
- 驗證未做；里級災情資料（1999 派工定位到里、EMIC、積水事件）已備妥。
- 模型本身的已知問題（CPT 方向反置、降雨幅度傳不到 O_total、FloodZone 情境切換階梯）原樣存在。
- 24 項基線證據只有 15 項通到 `O_TotalRisk_int`；樞紐 ModifiedFloodPotential 四個父節點有三個無證據（第 10 節）。

## 8. 交付

見 `docs/data_input_scale_taipei_v2.md` 第 7 節檔案索引；結案報告 `bn_engine/results/taipei_v2_village/taipei_v2_village_close_report.md`。

## 9. 不動清單

`bn_engine/bn_v0220.pkl`、`bn_engine/reference_tainan/`、`bn_engine/results/taipei_v1/`、v1 五支腳本（只新增 `taipei_paths.villages_gdf`／`OUT_V2` 與 `taipei_common.village_population_strata`，v1 函式未改）。

## 10. 補充（2026-10-29）：pkl 路徑查核與建議新增的兩條邊

用 networkx 直接讀 `bn_engine/bn_v0220.pkl`（193 節點／269 邊），查 24 項基線證據到綜合風險 `O_TotalRisk_int` 的路徑。腳本 `scripts/make_bn_hub_edges_figure.py`（圖上每一條實線邊都 assert 存在、兩條建議邊都 assert 不存在）；圖 `docs/figures/bn_hub_two_edges.png`、`.svg`。pkl 未動。

查核結果：

- `O_TotalRisk_int` 父節點 R1_EconomicLoss_new／R2_Lifeline_new／R3_Vulnerable_new；祖先 84 個，其中根節點 32 個、未餵（均勻先驗）根節點 26 個。
- 24 項證據只有 15 項通到 `O_TotalRisk_int`。不通的 9 項：Children_Ratio（只到 OUT_FloodRiskIndex 旁支）、DR.NonStructural_DRRPolicy（→ Agricultural_Loss_Coverage，sink）、LP.river_corridor_designation（→ RiverWaterLevel，sink）、RiverWaterLevel（sink）、FloodZone_ElderlyAlone_Count／FloodZone_Disability_Count／FloodZone_Children_Count／FloodZone_Agri_km2（孤立節點，無進無出）、FloodZone_Vulnerable_Ratio（→ R3_rate，sink）。
- 樞紐 ModifiedFloodPotential（16 個子節點：R1、FloodDuration、OUT_FloodRiskIndex、全部 INFRA 脆弱度）父節點四個：OriginalFloodPotential（錨定）、PumpStationOperation（無證據；父 PumpMaintenanceFreq 未餵根＋PowerSupplyReliability）、TidalBackwater（父只有 NZ.SeaLevelRise_Scenario）、EnvironmentalDRRIntegration（父四個全是未餵根）。93 里之間的差異只來自第一個。
- 抽水容量證據 DR.StructuralMeasures_Coverage 只到 A_b_LifelineAdaptation（→ R2、INFRA 脆弱度）與 DrainageSystemEfficiency（→ FloodDuration）；直接接樞紐的是無證據的 PumpStationOperation（10/22 單節點掃描影響最大者）。
- Rainfall 三條出邊：OriginalFloodPotential（錨定後被覆蓋）、RiverWaterLevel、INFRA_DetentionFragility（後兩者 sink）。錨定之下 Rainfall 節點本身不影響結果。豪雨／大豪雨 O_total 同值，是因臺北潛勢圖在 6h150／12h200／24h200 與 6h250／12h300／24h350 的里均淹水面積只有 0.02–1%（幾乎全 FD1），且 E 情境同用 24h350；是臺北資料的事實，不是結構錯誤。

臺北端建議（不動 pkl，待臺南端裁定）：

1. 第 6 節第 5、6 項兩條邊（年底前唯一建議的結構更動）。
2. 北士科的危害輸入改接子三水理結果（多重現期與開發情境），取代潛勢圖錨定與安南代理式轉移。
3. 26 個未餵根節點中臺北可餵的約 8 個（UrbanDrainageStandard、LP.building_coverage_ratio、PHY_BuildingAge、EXP.* 三個密度、INST_MonitoringDensity、PumpMaintenanceFreq）另立「臺北擴充證據集」做敏感度，不進共用基線。
4. 不通到綜合風險的 9 項證據照算照交付，文件與簡報標明「有效 15 項」。
