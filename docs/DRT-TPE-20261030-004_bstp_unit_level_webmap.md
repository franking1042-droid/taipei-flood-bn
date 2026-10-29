---
id: DRT-TPE-20261030-004
title: taipei_v3_bstp_units — 北士科 67 個街廓（土地使用單元）各一組風險值，與瀏覽器端動態推論的互動地圖
status: implemented（臺北端）；街廓級計畫暴露量、tpe1 CPT 正式值待團隊／臺南端
date: 2026-10-30
depends_on: DRT-TPE-20261026-002（里級輸入）、DRT-TPE-20261029-003（tpe1 提案模型）
model: bn_v0220.pkl（不動）；bn_v0220_tpe1.pkl（提案）可切換
---

## 1. 問題

子計畫一要的是「每個土地使用單元一組風險值」（經濟損失 R1、生命線中斷 R2、弱勢人口 R3、綜合總風險 O），
而且要能隨輸入參數動態調整，不是寫死的表。里級（v2）只有兩個里蓋住園區（建民里 50%、洲美里 49%），分不出街廓。
本版把空間單元換成北士科的街廓，並做一張純靜態的互動地圖：模型 CPT 載進瀏覽器，改參數就在瀏覽器裡重算整張圖。

## 2. 空間單元：北士科 67 個街廓

- 來源：地政局開發總隊「臺北市區段徵收區」SHP（data.taipei，2026-04 版）`ZEPN_1.shp`，北投士林科技園區 67 個街廓多邊形。
  T1–T16、T1718（17 個，25.04 ha）；R1–R16、R21–R32、R24-1（29 個，19.67 ha）；未編碼公設 21 個（公園 4、綠地 11、
  學校／國小／高中 3、機關 1、交通 1、抽水站 1；28.72 ha）。合計 73.44 ha；外框 104.99 ha，差額是道路與河川。
  未編碼者給 `P01`–`P21`，名稱＝分區＋序號（例：`公園用地-2`）。
- 分區：臺北市都市計畫使用分區 SHP「細計-面」（Data_taipei policy；原檔無 .prj，座標範圍即 TWD97 TM2，設為 EPSG:3826），
  裁到外框 100 m 內另存 `data/taipei/bstp_detail_plan_zoning.geojson`（131 個多邊形）。每街廓取交集面積最大的分區
  （排除「規劃範圍」「細部計畫範圍」兩個外框多邊形）。T 全部對到科技產業專用區；R 對到第三種住宅區(特) 12、
  第三之二種住宅區(特) 9、市民住宅區 5、住商混合區 3；交集占比 ≥99%（T1718 91%）。
- 宿主里：與街廓交集面積最大的里。建民里 34 個、洲美里 33 個（福興里只擦到園區邊，不是任何街廓的宿主）。

## 3. 三份輸入到街廓

| 輸入 | 方法 | 尺度 |
|---|---|---|
| H2 錨定表 | 潛勢圖 10 情境多邊形 overlay 街廓（`build_shp_baseline_village` 同法，`profile()` 直接沿用）→ `cpt_priors/h2_bstp_unit_conditional_table_v3.json` | **街廓原生** |
| evidence 16 節點 | 整份繼承宿主里的 v2 里級 evidence，再依計畫用途規則（§4）覆寫 5 個土地使用節點；兩版都存：`evidence_inherited`、`evidence_planned` | 里級繼承＋計畫分區 |
| E 節點 8 個 | 繼承宿主里的 `E_node_levels_village_v2`（24h350／24h500） | 里級 |

潛勢圖在街廓上的事實（`shp_baseline_bstp_units_v3.csv`）：豪雨、大豪雨的六張圖 67 個街廓全部 0%；超大豪雨（24h500）
只有 9 個街廓有淹水：P10 公園 40.9%、T13 12.8%、T14 10.5%、T11 10.0%、T10 6.2%，都在洲美側西緣；
極端降雨（24h650）63/67 個街廓淹水，R 平均 66%、T 63%、P 46%。所以街廓間的差異主要出現在超大豪雨與極端降雨。

## 4. 計畫用途規則（D3）

街廓現況（國土利用 112 年）是空置地與營建中（T／R 街廓 44.7 ha 內空置地 25.5 ha、其他建築用地 13.4 ha），
用現況算不透水率會把未來的科技產業／住宅街廓判成「低」。所以 evidence 預設版本依細部計畫分區定土地使用節點的狀態：

| 分區 | 覆寫 |
|---|---|
| 科技產業專用區 | 不透水率 極高、建築密度 高、NbS 覆蓋 低（人口密度沿用宿主里：日間工作人口非常住） |
| 住宅區四種 | 不透水率 極高、建築密度 高、人口密度 高、NbS 覆蓋 低 |
| 公園、綠地 | 不透水率 低、建築密度 低、人口密度 低、NbS 覆蓋 高、綠基盤 >30% |
| 學校、國小、高中、機關 | 不透水率 高、建築密度 中 |
| 交通、抽水站、堤防 | 不透水率 高 |

規則依據寫在 `evidence_per_bstp_unit_v3.json` 的 `_meta.rule_basis`（v0186 不透水率切點、v0181 建築密度代理、A1／A2 規則）。
67 個街廓共改掉 145 個節點狀態。其餘節點（人口比例、獨居、身障、收容所、河川水位、抽水 cms、河川廊道、非結構政策）
在同一宿主里的街廓之間同值。地圖上每個節點的來源（里級繼承／計畫用途規則／使用者覆寫／E 節點）都標在街廓的彈出視窗裡。

## 5. 推論：靜態交付檔與瀏覽器端動態推論

- **靜態**：`scripts/run_inference_bstp_units.py` 用 `run_inference_taipei.anchored_query` 原函式，67 街廓 × 2 模型 × 4 雨級
  （planned）＋ 超大豪雨 inherited 對照 → `results_bstp_units_v3.csv`（每列：P(OFP≥FD2)、MFP／延時／OUT_FRI／R1–R3／O 期望值、
  P(O≥高)、P(抽水運作＝正常)、P(外水頂托＝高)）、`posteriors_all_bstp_units_v3.csv`（全部後驗）、`map_bstp_units_v3_超大豪雨.png`。
- **動態**：`webmap/bstp_risk_map.html`（Leaflet）＋ `webmap/bn_engine.js`（瀏覽器端 variable elimination）＋ `webmap/data/*.js`
  （兩個模型的全部 CPT、街廓 GeoJSON、H2 表、evidence、E 節點、控制面板清單；由 `scripts/export_webmap_data.py` 產生）。
  - 錨定等價性：pgmpy 的 virtual evidence 是加一個二元子節點、P(=0|OFP)＝lik 再觀測為 0，數學上就是把 lik 乘進聯合分布。
    網頁端算 P(目標, OFP | e) 一次，再 P(t|e,錨定) = Σ_k P(t,OFP=k|e)·lik_k ／ Σ_k P(OFP=k|e)·lik_k，lik＝p_shp／max(P(OFP|e),1e-12) 正規化，
    與 `anchored_query` 逐式相同。同一組證據的聯合分布快取；不同街廓只差 p_shp，加權即可。67 街廓、8 組不同證據：0.05 s。
  - 自我檢核（頁面按鈕或 `?selftest=1`）：60 個 pgmpy 對照案例（6 街廓 × 4 雨級 × 2 模型，加 inherited、不錨定、抽水失效、
    外水頂托高＋一級警戒、多節點覆寫、海平面 RCP8.5 等）共 2,208 個機率值，**最大絕對誤差 1.3e-10**（容忍 1e-6），
    證據字典與 Python 端逐鍵相同（0 不一致）。
  - 可調參數：模型（v0220／tpe1）、雨級、evidence 版本（計畫用途／只繼承宿主里）、是否錨定、16 個 evidence 節點與 8 個 E 節點的
    全域覆寫、9 個機制／情境節點（抽水站運作、外水頂托、供電可靠度、維護頻率、海平面情境、環境減災整合、排水標準、
    政策介入、建築脆弱度）的硬證據。節點旁標示該模型下是否通到綜合總風險。
  - 輸出：點街廓看完整分布（O、R1–R3、延時、修正潛勢、原始潛勢、抽水運作、外水頂托）、錨定用的潛勢統計、該街廓用的證據與來源；
    「匯出 CSV」把目前情境下 67 個街廓的指標與全部分布存成 UTF-8 BOM CSV（含 overrides 欄位），即子計畫一的輸入格式。
  - 底圖用國土測繪中心 WMTS（通用電子地圖／正射影像）與 OSM；推論本身不需網路。直接開 html 檔即可（Leaflet 由 CDN 載入）。
  - 網頁引擎不含 `OUT_FloodRiskIndex`（7 個父節點、390,625 格）；靜態 CSV 有。

## 6. 結果（bn_v0220、計畫用途 evidence、街廓錨定）

| 雨級 | T（17） | R（29） | P（21） | 全部 67 | 備註 |
|---|---|---|---|---|---|
| 豪雨、大豪雨 | 0.292 | 0.292 | 0.292 | 0.292 | 街廓無潛勢、E 節點 24h350 全 very_low：底值 |
| 超大豪雨 | 0.861 | 0.816 | 0.751 | 0.807（0.671–0.970） | 洲美側 T13 0.970、T14 0.952、T11 0.949、T10 0.939 |
| 極端降雨 | 1.259 | 1.194 | 0.989 | 1.146（0.671–1.710） | 63 街廓淹水 |

- 街廓間的差異有三層：潛勢（T13／T14／T11／T10 與 P10 在超大豪雨就有淹水）、宿主里（洲美側街廓底值 0.911、建民側 0.78 上下，
  來自里級節點：建民 Elderly high、人口密度高；洲美 Children high、獨居 very_high、不透水中）、計畫用途（T／R 比 inherited 高 +0.03、
  公園綠地低 −0.04）。
- tpe1 − v0220：67 街廓一律 −0.006 到 −0.010（兩里抽水覆蓋皆為高，K＝2 佔位下幅度小），排序不變。
- 超大豪雨下 P(O≥高) 最高只有 0.017（T13）；所有數字是事件條件機率，不是年度風險。

讀法：這版的鑑別力主要來自潛勢圖與計畫用途；里級節點在同一宿主里內同值，E 節點更是里級絕對暴露量。
街廓級的「計畫暴露量」（計畫人口、樓地板、建蔽率）接上之後，R1／R3 才會在街廓之間真正分開。

## 7. 決定

| # | 決定 | 理由 |
|---|---|---|
| D1 | 單元＝ZEPN_1 街廓，不是細部計畫分區多邊形 | 子計畫一與 10/22 簡報都用街廓碼；分區多邊形把綠地切成 11 片小條 |
| D2 | 分區以細計-面交集最大者對應；原檔無 CRS，設 3826 | 座標範圍與里界一致；T／R 對應 ≥99% 驗證 |
| D3 | evidence 預設 planned（繼承宿主里＋計畫用途規則），inherited 保留為對照 | 現況是空置地；規則與依據見 §4，地圖可切換 |
| D4 | E 節點先繼承宿主里 | 街廓級計畫暴露量要計畫書數字，另案 |
| D5 | 網頁引擎排除 OUT_FloodRiskIndex | 390,625 格；它是輸出指數、不是 O 的祖先 |
| D6 | 互動地圖純靜態，`webmap/data/*.js` 由腳本產生、不手改 | 不用伺服器就能開、能交給子計畫一 |
| D7 | 錨定在瀏覽器端用聯合分布加權實作，並以 60 案例逐格對照 pgmpy | 與 virtual evidence 等價（§5），檢核 1.3e-10 |
| D8 | 輸出到 `results/taipei_v3_bstp_units/`；v2 結果不動 | 版本分離 |

## 8. 需要團隊／臺南端回覆

1. 街廓級計畫暴露量的口徑：各街廓計畫人口（住宅戶數 × 戶量）、樓地板面積、建蔽率，從北士科細部計畫書取，
   接 FloodZone_Population_Ratio、FloodZone_Building_Pct、FloodZone_Elderly_Count（只有這 3 個 E 節點通到 O）。
2. 子計畫一要的風險值格式：期望值、完整分布、或 P(O≥高)；CSV 三種都給。
3. tpe1 兩張 CPT 的正式值（DRT-003 §2）。

## 9. Known limitations

- 里級節點在同一宿主里的街廓之間同值；E 節點是里級絕對暴露量。街廓之間的差異目前主要來自潛勢錨定與計畫用途。
- 計畫用途規則是分區 → 狀態的知識法則，未用計畫書的建蔽率、容積率數字校準。
- 潛勢圖（2016）早於園區填土與排水工程；街廓在超大豪雨幾乎不淹，可能已反映填土，也可能是圖資解析度，未查證。
- v0220 既有問題原樣存在（CPT 方向反置、豪雨／大豪雨同值、降雨只經 OFP 傳遞）；tpe1 是 K＝2 佔位。
- 網頁底圖需網路；Leaflet 由 CDN 載入。推論本身離線可用。

## 10. 交付

`scripts/build_bstp_units.py`、`run_inference_bstp_units.py`、`export_webmap_data.py`；`data/taipei/bstp_detail_plan_zoning.geojson`；
`bn_engine/cpt_priors/h2_bstp_unit_conditional_table_v3.json`；`bn_engine/results/taipei_v3_bstp_units/`（`bstp_units_v3.csv`／`.geojson`、
`shp_baseline_bstp_units_v3.csv`、`evidence_per_bstp_unit_v3.json`、`E_node_levels_bstp_unit_v3.csv`、`results_bstp_units_v3.csv`、
`posteriors_all_bstp_units_v3.csv`、`taipei_v3_bstp_units_summary.json`、`map_bstp_units_v3_超大豪雨.png`）；
`webmap/bstp_risk_map.html`、`bn_engine.js`、`data/bn_v0220.js`、`bn_v0220_tpe1.js`、`bstp_units.js`、`selftest.js`。

## 11. 不動清單

`bn_engine/bn_v0220.pkl`、`bn_v0220_tpe1.pkl`、`reference_tainan/`、`results/taipei_v1/`、`results/taipei_v2_village/`、`results/taipei_tpe1/`、
v1／v2 腳本既有函式（本版只在 `taipei_paths.py` 末尾加 `OUT_V3`、`WEB` 兩個常數）。
