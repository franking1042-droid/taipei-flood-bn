# taipei_v2_village 結案報告 — 臺南 BN v0.22.0 直接移植，空間單元＝士林、北投 93 里

日期：2026-10-26。模型：`bn_engine/bn_v0220.pkl`（193 節點／269 邊，不動）。決策紀錄：`docs/DRT-TPE-20261026-002_village_level_inputs.md`。輸入尺度清單：`docs/data_input_scale_taipei_v2.md`。

## 1. 回答的問題

把 v1 的 2 區輸入換成 93 里輸入之後，同一個 BN 在里尺度會給出什麼風險分布；哪些輸入真的有里級資料、哪些只能區級複製。

## 2. 方法

與 v1 完全同法（臺南 v0212 錨定、v0220 MC 與三軸政策分解），只換三份輸入：
1. H2 錨定表：潛勢圖 overlay 里界 → 93 里 × 4 雨級 × FD1–5；
2. 16 節點 status-quo evidence：里級人口（115/9）、里級 LULC、集水分區加權抽水量、服務里別收容所；獨居、身障、三個知識法則節點區級複製；
3. 8 個 E 節點：LULC 代表點落里、潛勢區內外，臺南絕對切點。

腳本順序：`build_shp_baseline_village.py` → `build_village_base.py` → `compute_E_exposure_village.py` → `compose_evidence_village.py` → `run_inference_village.py all` → `make_village_maps.py`。

## 3. 檢核

| 檢核 | 結果 |
|---|---|
| 93 里潛勢面積加總回推 2 區 vs v1 區級錨定表 | 最大差 0.000000 |
| LULC 裁切面積總和 vs 里界面積 | 118.46 vs 118.46 km² |
| LULC 建築／農地代表點落在 93 里之外 | 0 筆 |
| 抽水站對集水分區 | 29 站 within、5 站 ≤83 m 最近分區 |
| 收容所服務里別無法對上的里名 | 0（正規化後） |
| evidence 狀態字串 vs pkl state_names | 93 里 × 16 節點全部通過 assert |
| 每里 evidence 數 | 24（16 ＋ 8 E 節點，與 v1、臺南 v0220 相同） |

## 4. 結果（H1＝超大豪雨＋E 24h500，錨定，等權 w）

- 64 里無潛勢區暴露，O_total 期望值＝0.292（模型底值）；29 里 >0.3。
- 前十：吉慶 1.62、立賢 1.56、八仙 1.54、立農 1.47、一德 1.29、尊賢 1.24、大同 1.19、福華 1.15、豐年 1.08、福安 1.07。前四里放進臺南 37 區皆第 1（臺南最高安南 1.1485 附近）。
- 四雨級 O_total 均值：豪雨 0.381、大豪雨 0.381、超大豪雨 0.509、極端降雨 0.558；降雨幅度在豪雨→大豪雨間完全傳不到（E 情境同為 24h350），與 v1、臺南行為測試一致。
- 區均值（人口加權）：北投 0.60、士林 0.47；v1 區級值 1.148／0.756 偏高是 E 節點絕對暴露量的尺度效應。
- 北士科周邊（示意中心 1.5 km）：洲美 0.98、建民 0.78、福華 1.15、後港 0.94、福安 1.07；最高的吉慶 1.62、立賢 1.56 在圓內北側（石牌）。
- 政策：RR_total 均值 0.010、最大 0.115（一德）；DSE 修正臂均值 0.015。

地圖：`map_village_v2_超大豪雨.png`；GIS：`results_village_v2.geojson`。

## 5. 驗證

未做。可用的里級災情資料：1999 積淹水派工定位到里（342 筆有里別）、EMIC 2006–2021 士林北投積淹水 226 筆含座標、水利處積水事件 ≥15 cm 115 筆；事件候選：納莉 2001（正）、璨樹 2021（負）、0604 豪雨 2021、0626 豪雨 2026（正）。設計另案（四層可信度論證：結構、行為、事件重演、PHD 物理對照）。

## 6. 交付清單

見 `docs/data_input_scale_taipei_v2.md` 第 7 節。

## 7. Known limitations

1. 這仍是移植版：切點、CPT、權重全是臺南的；E 節點等級語意是「放進臺南 37 區分布屬第幾級」。
2. 區級複製的四個節點（獨居、身障、DR.NonStructural、RiverWaterLevel）在里級地圖上沒有變化。
3. AccessToShelters 全為「高」、ElderlyAlone_Ratio 全為 very_high、DisabilityPopulation_Ratio 全為 medium，在臺北無鑑別力。
4. 關渡、知行兩個集水分區無對應站（暫 0 cms）。北士科正式範圍（地政局區段徵收區 SHP，104.99 ha）只與建民里、洲美里各約一半交集，見 `map_bstp_villages_v2.png`、`bstp_villages_v2.csv`。
5. 計數型 E 節點在里尺度多為 very_low，是尺度效應；替代分級 `level_q93` 未用於推論。
6. 臺南端未裁定的問題原樣存在（VS 切點版本、SMC→DSE 與 NbS→RC 方向反置、降雨幅度傳不到 O_total、Brier 數字不可引用）。
7. 數字是事件條件下的風險等級期望值，不是年度風險。
8. （2026-10-29 補）24 項證據只有 15 項通到 `O_TotalRisk_int`；樞紐 ModifiedFloodPotential 的四個父節點有三個無證據（抽水運作、外水頂托、環境減災整合），里間差異只來自錨定的原始潛勢。建議新增的兩條邊與細節見 DRT-TPE-20261026-002 第 10 節、`docs/figures/bn_hub_two_edges.png`。

## 8. 不動清單

`bn_engine/bn_v0220.pkl`、`bn_engine/reference_tainan/`、`bn_engine/results/taipei_v1/`、v1 腳本的既有函式。
