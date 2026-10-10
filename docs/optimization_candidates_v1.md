# 臺北移植版 BN（taipei_v1）已驗證優化候選清單

> 驗證強度說明：
> - **3 視角**：正確性、價值、可行性各由一位審查者獨立驗證，共三票。
> - **1 視角**：由一位審查者合併三視角驗證，強度較低。
> - 「票」欄的 ✔ 表示該視角判定成立，✘ 表示該視角判 refuted。
> - 下文所列「建議做法」已採用審查者的修正版（revised_proposal），原始提案中被證實有誤的數值已更正。
> - 路徑凡未加前綴者都在臺北 repo 內；「tainan:」表示臺南 repo 快照。

---

## 一、high（10 條）

### C01 年齡結構誤用 43 期加總，應改取 114/12 單期
- **類別**：資料來源｜**驗證**：3 視角｜**票**：正確性 ✔ 0.82、價值 ✔ 0.90、可行性 ✔ 0.90
- **依據**
  - `data/taipei/pop_by_age_village_2023-01.csv` 共 258 列，等於 2 區 × 3 性別 × 43 期（112/1–115/7），檔內沒有里別。
  - `scripts/taipei_common.py:27-32` 只篩「性別=計」就 groupby 加總，沒有篩期別，等於把 43 期全部加在一起。
  - 程式註解、欄名與文件都寫成「112/1」：`taipei_common.py:5,9,39,64`、`docs/evidence_mapping_taipei_v1.md:11,69`、DRT 決策 6、README:67。DRT 決策 6 的理由是「最新檔未抓」，但這個前提不成立。
  - 改取 114/12 後，各齡加總與 TSIS 114 年底總人口完全相等（士林 258,163、北投 235,678）。老年比士林 25.36%、北投 23.42%；目前 pooled 的值是 24.00% 與 22.10%。
- **臺南對照**
  - tainan `scripts/compute_E_exposure_v0213.py:81-93` 用單一期別直接加總。
  - SKG 的 Children_Ratio 與 Elderly_Ratio 都標註「114/12 實測」。
- **建議做法**
  1. 在 `district_population_strata()` 只取「年份=114、月份=12、性別=計」的列，直接用各齡人數算 pop_0_14 與 pop_65p，並 assert 總計等於 TSIS 人口。
  2. 欄位改名為 `pop_total_11412`，`age_structure_period="114年12月(民政局區級月報)"`。
  3. 同步更新上述文件，以及 Data_taipei/README.md:11（實為區級月報，不是里級）。
  4. 重跑全鏈。
  5. 里級全市 Big5 檔（區域代碼前綴 63000110／63000120，要排除兩個區列，剩 93 里）只留給 C05 使用。
- **預期效果**
  - 16 個區級節點的狀態都不變。士林 Elderly_Ratio 由捨入邊界值 24.00 變成穩定的 25.36，仍是 high。
  - **E 節點會變**：士林 24h500 FloodZone_Elderly_Count 由 730.8 變成約 772，切點是 **740.1**（原候選寫 775.2 是錯的），由 medium 變 high。
  - 價值票實跑：士林 R3 由 0.4175 變 0.4587，O 由 0.7541 變 0.7723，聯合排名上移約 1–2 名，最終名次以 stage_mc 重算為準。
  - close report 要把這項列為本次修正的狀態翻轉。

### C02 RR_total 為負時不應報 share %；補 dsefix 分解欄並改寫 §3
- **類別**：結果合理性｜**驗證**：3 視角｜**票**：正確性 ✔ 0.92、價值 ✔ 0.75（建議降為 medium）、可行性 ✔ 0.90
- **依據**
  - `scripts/run_inference_taipei.py:246-248` 的條件是 `abs(tot) > 1e-9`；臺南 `run_ototal_mc_v0220.py:317-319` 的條件是 `tot > 1e-9`，RR 為負時留空。
  - 臺北 `ototal_policy_decomposition_taipei_v1.csv:2-3` 的 RR 是 −0.0046 和 −0.0069，卻仍報了 48.9/6.3/44.8 與 56.0/7.8/36.2。
  - `taipei_v1_close_report.md:43-48` 把這些數字當成「貢獻 %」，還拿來和臺南 >100% 的正效益比較。
  - 臺南安南、新營、麻豆、仁德、永康這幾區的 share 都是空白。
- **臺南對照**：tainan `run_ototal_mc_v0220.py:262-355`；`v0220_close_report.md:59-73`；`DRT-20260819-079`。
- **建議做法**
  1. 恢復 `tot > 1e-9` 的條件。
  2. 補上 `d_r_fx`、`contrib_fx`、`contrib_R1..3`、`share_*_pct_dsefix`，欄序和臺南 `:310-324` 一致。乾跑結果：士林 dsefix 分解 −7.0/11.5/95.5，北投 −8.3/16.3/92.0，和臺南安南 −16.7/17.2/99.5 同型。
  3. 加「2 區合計」列，但合計列也要套 `sum>1e-9` 的守門；臺南 `:342-344` 沒有守門，不要照抄。
  4. α∈{0.30, 0.51, 0.75} 的敏感度屬於 v0214a 的 RR_depth／dwet_cm 表，不在 v0220 的 stage_policy 內，另開一張表。實測 RR 差 ≤0.0002，要寫成「對 α 不敏感，因為 FD1 已達 0.993，沒有質量可移」。
  5. close report §3 改寫：
     - 兩區 status quo 都高，do() 沒有位移空間；
     - RR_total 應讀成 ≈0；
     - DSE 修正臂 +0.032／+0.046 是上界，分解只報 dsefix 臂；
     - 刪掉和臺南 >100% 的比較；
     - 保留「DR.SMC 已是高」這句解釋。
  6. **額外（N2）**：單軸 do(DR.NS) 與 do(DR.SMC) 的 ΔO 完全相同（−0.0019／−0.0031），來源是共同父節點 LP.policy_intervention 未觀測形成的後門路徑。所以負 RR 不能全歸因於 CPT 方向反置，§3 要一併寫清楚。
- **預期效果**：政策表不再把「傷害的分攤」讀成效益；表格與臺南同構，可以直接並列。

### C03 E 節點落在臺南「無觀測空隙」與邊界慣例
- **類別**：切點與規則｜**驗證**：3 視角｜**票**：正確性 ✘ 0.80（描述有誤，修正後仍成立）、價值 ✔ 0.85、可行性 ✔ 0.85
- **依據**
  - `compute_E_exposure_taipei.py:43-46` 取中點切點，`:51-55` 用 `v<=c`；`compose_evidence_taipei.py:55-59` 與臺南 v0188 都用 `<`。
  - 32 個 E 值中有 5 個落在臺南兩級之間的空隙。
  - pkl 實查只有 4 個 E 節點有子節點：Population_Ratio→R2、Building_Pct→R1、Elderly_Count→R3、Vulnerable_Ratio→R3_rate。ElderlyAlone、Children、Disability、Agri_km2 是懸空的根節點，**不影響推論**。
  - 因此真正有效的空隙案例只有 3 個：
    - 北投 24h500 Population_Ratio 0.0698，落在 (0.0618, 0.0700)；
    - 北投 Building_Pct 6.98，落在 (6.18, 7.00)；
    - 士林 Elderly_Count 730.8，落在 (669.9, 810.3)。
  - 另有北投 Vulnerable_Ratio 0.0275，距切點只有 2.5%。
  - 臺南的 tie 值有 3 個（5.18、0.0518、0.1），來源是 `discretize_E_nodes_v0213.py:39` 的 `rank(method='first')`；目前臺北的值沒有落在這些 tie 上。
  - 原候選有三處錯誤，已更正：「2.9 因 <= 歸 L4」不成立（浮點中點是 2.9000000000000004）；Building_Pct 是經由 R1，不是 R2；「另有 6 個值接近切點」實際只多 1 個。
- **臺南對照**：tainan `discretize_E_nodes_v0213.py:36-42`；`build_bn_v0214a.py:88-99`；`discretization_principles.md` 原則 3。
- **建議做法**
  1. 在 `E_node_levels_*.csv` 加欄：`in_pkl`、`feeds_inference`、`in_tainan_gap`（L_k max｜L_k+1 min）、`nearest_cut_rel_dist`、`boundary_note`（tie）。
  2. 只對有效的空隙案例做 level±1 推論，並用 stage_mc 重算排名區間：
     - 北投 Population_Ratio high 改 medium：R2 由 1.731 變 1.417，O 由 1.148 變 1.012，排名由 14 變 21；
     - Building_Pct：O 變 1.138，排名不變；
     - 士林 Elderly_Count：O 由 0.754 變 0.772。注意 C01 修完後，這一項會離開空隙。
  3. `level_of` 改用 `<`；實測對 32 個值都沒有影響，只是統一慣例。tie 值要標註；文件要註明切點來源是 4 位小數的捨入值（Vulnerable_Ratio 是 5 位）。
  4. DRT-TPE「需要臺南端回覆」新增一題：空隙案例的歸級規則（取中點、保守取低級、或改用絕對切點）。
- **預期效果**：把「北投 1.148、第 14」改成可辯護的區間（O 介於 1.00–1.15，排名 14–21），並明白寫出 4 個 E 節點不影響推論。

### C04 驗證缺席：建 stage_validate，逐軌標結果或 N/A
- **類別**：驗證｜**驗證**：3 視角｜**票**：正確性 ✔ 0.93、價值 ✔ 0.82、可行性 ✘ 0.70（原案的 LOEO 與 V-A 無對應物，已降級）
- **依據**
  - `taipei_v1_close_report.md:60` 與 README:63 寫「驗證：未做」；`run_inference_taipei.py:13-17` 只有 3 個 stage。
  - Data_taipei 已經有：
    - EMIC 積淹水（非演練）北投 145 筆、士林 56 筆；
    - 1999 派工 626 筆，其中 342 筆有里別；
    - 歷史積水 KML：士林 100 筆、北投 68 筆，含 Depth，時間 1991–2025；
    - 積水事件查詢網：士林 12 筆；
    - 事件日雨量摘要 102 日；
    - 主計處救助情形 111–114 年。
  - 錨定表 P(FD1) 在 0.84–0.9999 之間，所以 uniform 基準一定輸，不能只拿它當基準。
  - README:63「正樣本不足」與資料不符：2016-11 以後士林北投仍有 56 筆 KML 紀錄。
- **臺南對照**：tainan `run_ototal_mc_v0220.py:359-436`；`run_conditional_validation_v0212.py:60-65, 71-85, 163-195`；`ototal_validation_v0220.json`；README:37。
- **建議做法（降級版）**
  1. 新增 `stage_validate`，輸出 `ototal_validation_taipei_v1a.json`（含 version／date／config／tracks，每一軌都要有 result 或 `status="N/A"` 加原因）與 event_cells csv。
  2. **T1 事件條件 OFP 深度 Brier**，標題直接寫明「驗的是潛勢圖＋錨定，不是 BN」。理由：錨定後 P(OFP)≡P_shp，這一軌分不出 BN 和它的輸入。
     - 觀測：KML Depth ≥30 cm 共 86 筆，加查詢網 1 筆。<30 cm 的 82 筆只列筆數、不計分，因為那會被錯判成 FD1。
     - 事件日：同一天 FD2 以上觀測 ≥3 筆的日子。
     - H1：用平地站（社子、石牌、天母、士林、關渡）的 24h 雨量判定，排除鞍部、陽明山等山區站。1998–2017 用逐時寬表，2018 以後用摘要。另外並列「60 分鐘 >78.8 mm」規則；兩種規則都定不了的事件就排除。
     - 基準三種並報：uniform、P_shp、`two_district_pooled`。
  3. **T2 里級空間一致性**（取代 n=2 的區級排名）：
     - 1999 派工（有里別）、EMIC（有座標）、KML（用 sjoin）對應到 93 里，算每里的相異日數／年；
     - 用里界重算 P_shp(FD≥2 | 超大豪雨、極端降雨)；
     - 報 Spearman（n=93）。區級那一項標 N/A。
  4. **T3 一律 N/A 並寫原因**：FloodDuration（沒有延時欄）、70/30 hold-out 與 LOEO（沒有用事件擬合的參數）、V-A 複合 GT（沒有區級事件災損等級）、R3 收容弱標籤（只有 1 格非零）。
  5. **T4 數值自洽**（與 C30 共用）。
  6. close report §5 與 README:63 改寫，並加一句：臺南的 Brier 數字不適用於臺北。
- **預期效果**：從「未做」變成四軌、每一軌都有結果或 N/A，結構和臺南同構；臺南的數字不會再被誤引為臺北的。

### C05 用里級人口＋門牌點位檢驗「人口沿建築分布」假設
- **類別**：資料來源｜**驗證**：3 視角｜**票**：正確性 ✔ 0.88、價值 ✔ 0.85、可行性 ✔ 0.85
- **依據**
  - `compute_E_exposure_taipei.py:9, 96-97` 的公式是 E_pop = pop × flooded_building_area_pct，沿用臺南的假設。
  - 北投 24h350 的建物淹水比 0.02%，區淹水比 0.45%；24h500 的 E_pop 是 16,440，沒有任何外部數字可以對照。
  - Data_taipei 已有：里級單齡人口（全市 Big5 檔，最新到 115/7）、里界 SHP（456 面）、門牌 1,157,763 筆、保全戶表。
- **臺南對照**：tainan `compute_E_exposure_v0213.py:7-11, 150-151`。臺南用這個假設是因為只有區級人口。
- **建議做法**
  1. 里級人口：從全市 Big5 檔篩區域代碼 11 碼、前 8 碼為 63000110 或 63000120、且「區域別」含「里」的列；期別用 114/12。不要用 README:11 那份子集，它只有區級。
  2. 主方法用**門牌點法**：E_pop_x_addr = Σ_里 pop_x(里) × (潛勢區內門牌數 ÷ 里內門牌數)。需要把門牌子集（約 20.8 萬筆）放進 `data/taipei/`。**不要用里面積比法**：它會把關渡平原的農地也攤到人口上，北投 24h350 會高估約 50 倍。
  3. 輸出 `*_addr` 欄與里級明細，另產生 `E_node_levels_*_village.csv`，用旗標切換。基線維持建物法，因為臺南切點本身是由建物法算出的值決定的。
  4. 獨居、身障人口依里級 65+ 比例分攤。
  5. 保全戶（福安 2,136、富洲 1,000、八仙 492、一德 13）只當量級參考。注意「富州」要改成「富洲」；保全戶是堤外保全對象，和潛勢圖的語意不同。
- **預期效果（敏感度）**
  - 北投 24h350 的近零暴露**得到證實**：只有 10 筆門牌，約 27 人。
  - 北投 24h500 由 16,440 降到約 8,600，Population_Ratio 由 high 變 medium，O 由 1.148 降到 1.012，排名由 14 變 21。
  - 士林 24h350 由 940 升到約 3,600，24h500 由 3,046 升到約 5,800；Elderly 與 Children 變 very_high，O 增加 0.033，超過士林四個雨級之間的總差距。
  - close report §4 要新增「E 人口分配法敏感度」一段。

### C06 DR.StructuralMeasures_Coverage：登錄簿 CMS/km² 的 B 版敏感度
- **類別**：切點與規則｜**驗證**：3 視角｜**票**：正確性 ✔ 0.90、價值 ✔ 0.80、可行性 ✘ 0.80（滯洪與堤防兩項資料不存在，已降級）
- **依據**
  - `build_district_base_taipei.py:66-68` 用半年報的「行政區」欄加總。三站兩來源不一致（大龍、洲美、社子）。
  - 改用座標點落區驗算：大龍落在兩區之外、洲美落北投、社子落士林。**結果和現行「行政區」欄相同**（259.6／147.88），只需要補文件說明。
  - 登錄簿 `nodes_dr.json` 的公式是 pump + 管線 Manning + 滯洪 + 堤防，門檻 [1, 5] CMS/km²。只算抽水量時士林 4.16、北投 2.60，都是「中」。
  - 滯洪設施 geojson 的「體積」欄全是 0；堤防檔沒有設計流量。登錄簿 4 項在臺南端也沒有實作完整（DRT-052 仍 open，v0185 實際餵的是分位數）。
- **臺南對照**：tainan `extract_real_policy_evidence_v0185.py:89-142`；`nodes_dr.json`（DR.StructuralMeasures_Coverage）；`discretization_principles.md:21`。
- **建議做法**
  1. 改用座標落區，數值不變。另加三欄：`pump_capacity_cms_formal`、`pump_capacity_cms_temporary`、`pump_capacity_cms_by_pointfile`（數值為士林 233.0+26.6、北投 93.38+54.5；pointfile 版 285.48／126.0）。`_meta` 記錄三站的差異，以及 GIS 面積（61.08／57.38）與主計處面積（62.37／56.82）兩組分母。
  2. B 版只算「抽水＋管線」兩項，滯洪與堤防以 0 計並標註「未取得」。管線項兩種算法並列：
     - (a) 臺南的 0.1 cms/km 粗估；
     - (b) 每個主集水區只取末端幹管，用 Manning 公式（n=0.013），坡度 0 的管段用中位數補。
     要註明：加上管線後，士林可能回到「高」。
  3. 分母三組並列：行政區、都市發展地區（士林 16.01、北投 16.66 km²）、集水分區。集水分區（文林 56、洲美 40 CMS/km²）只當尺度效應附表，不進 evidence。
  4. `compose_evidence_taipei.py` 加 `--smc_rule cms_per_km2 --denominator {district|urban|catchment}` 參數；基線維持 A 版（v0185 五分位）。
  5. **可比性警語**：在同一公式下，臺南 37 區抽水量 cms/km² 最高的是北區 4.90，沒有一區達到「高」；v0185 標為「高」的 10 區落在 0.53–4.90。所以 B 版不能和臺南的排名並列。這一點要寫進 DRT 請臺南裁定。
- **預期效果（敏感度，行政區分母、抽水單項）**
  - SMC 由高改中：士林 O 由 0.754 升到 0.787，北投由 1.148 升到 1.207，排名由 14 變 11。
  - RR_total 由負轉正（+0.028／+0.052），R2 貢獻由 6–8% 變成 112–115%。
  - 也就是說，close report §3 的政策結論完全取決於這個口徑。

### C08 16 節點兩區 15 個同值；「兩區抽水量都超過臺南最高」為錯
- **類別**：切點與規則｜**驗證**：3 視角｜**票**：正確性 ✔ 0.90、價值 ✔ 0.70（建議降為 medium）、可行性 ✔ 0.85
- **依據**
  - `evidence_per_district_taipei_v1.json:88-123`：兩區 16 個節點中，只有 Elderly_Ratio 不同。
  - 和臺南 37 區比對，沒有任何一區 15 個節點完全相同；最接近的是新營、東區（9–10/15）。
  - README:60 與 evidence_mapping:24 說兩區都超過臺南最高值，這是錯的：北投 147.88 cms 落在臺南 L5 的範圍 44–182.75 內，只有士林 259.6 cms 超過。
  - 收容所郵遞區號 bug（N1）：`build_district_base_taipei.py:73-74` 回退用郵遞區號判區，把 26 筆大同區收容所算進士林。修正後士林由 69 處變 43 處，水災適用由 36 變 18，每千老人 0.694，仍是 L5「高」。
- **臺南對照**：`reference_tainan/policy_evidence_per_district_v0185.csv`；`nodes_dr.json`；`nodes_vulnerability_social.json`。
- **建議做法**
  1. 更正 README:60 與 evidence_mapping:24 的抽水量敘述（士林超過臺南最高；北投在 L5 範圍內），並註明登錄簿 CMS/km² 口徑下兩區都是「中」。
  2. `_meta` 加 `discrimination` 欄：同值 15、不同值 [Elderly_Ratio]、最接近的臺南剖面。
  3. 修正 N1：改成以「鄉鎮」欄為準，同步更新 `district_base_indicators`、JSON 的 raw_values、evidence_mapping:25。
  4. 敏感度表（超大豪雨、錨定）：
     - SMC 由高改中：0.787／1.207；由高改低：0.820／1.266（與 C06 共用）。
     - ElderlyAlone 並列兩種分母：以 65+ 為分母時，very_high 改 high 或 medium 得 0.7551／1.1504；以總人口為分母（登錄簿字面定義）時得 0.7568／1.1527。
     - Shelter 由高改中：0.768／1.167。
     - RiverWaterLevel 只寫文字：在 pkl 中是葉節點，結構上 ≡0。
  5. 附註：ElderlyAlone 調低時 R3 反而微升（≤0.002），是 CPT 方向問題，要回報臺南。
- **預期效果**：誠實呈現「兩區差異幾乎全部來自 H2 與 E」，事實錯誤被更正，並留下按登錄簿口徑重算的對照基線。

### C09 北投階梯拆成三成分
- **類別**：結果合理性｜**驗證**：3 視角｜**票**：正確性 ✔ 0.90、價值 ✔ 0.70、可行性 ✔ 0.85
- **依據**
  - (a) 臺北潛勢圖本身的門檻：北投淹水比例由 24h350 的 0.451% 跳到 24h500 的 10.848%，放大 ×24（`shp_baseline_taipei_v1.csv:16,18`）。臺南各區只有 ×1.5–3.2。
  - (b) `run_inference_taipei.py:51` 的 SCEN_BY_H1 讓 E 在一步之內整個換情境。
  - (c) 北投在豪雨與大豪雨下 R1=R2=0.162793，正好是臺南 `build_bn_v0213.py:297-298` product_cpd「任一 badness=0 則 center=0」的地板，和臺南南化至龍崎 8 區相同。但北投 R3=0.353，**不在地板**（Elderly_Count=low）；O=0.366，也高於臺南的地板 0.2921。
  - `taipei_v1_close_report.md:52` 只寫「E 情境切換」，沒有說明 (a) 與 (c)。
- **臺南對照**：tainan `run_conditional_validation_v0213_batch3.py:48-49`；`build_bn_v0213.py:284-304`；`v0220_close_report.md:83`。
- **建議做法**
  1. close report §4.1 改寫成三成分，每個成分附檔案與行號。用語要寫成「R1、R2 零暴露、R3 非零」，不能寫「被當成零暴露區」。要補一句：南化、龍崎 24h350 只淹 0.08–0.10%，卻和北投落在同一個地板。還要說明：在這兩個雨級下，H2 錨定對 R1、R2 沒有任何影響。
  2. 四雨級表加 R1 列（0.163/0.163/0.328/0.496）與 R3 列（0.353/0.354/0.510/0.545），地板值要加註。
  3. pooled E 對照臂與 C19 共用。預期效果是「把超大豪雨壓低、把極端降雨拉高」，也就是階梯移位，**不是變緩**；只當對照，不取代基線。
  4. 低成本反事實：把北投 24h350 的 Building_Pct 與 Population_Ratio 各調高一級，拆出「地板」與「切換」各佔多少。
- **預期效果**：讀者能分清楚哪些是臺北真實的門檻，哪些是臺南離散化與配方造成的。

### C10 H2 錨定對 O 影響小；close report 改 8 節點 × 4 雨級 × 2 配置表
- **類別**：結果合理性｜**驗證**：3 視角｜**票**：正確性 ✘ 0.75（機制描述有誤，修正後仍成立）、價值 ✔ 0.70（建議降為 medium）、可行性 ✔ 0.78
- **依據**
  - `posteriors_all_h1_taipei_v1.csv`（704 列）：在基線（超大豪雨）下，錨定與全域的 O 只差北投 +0.018、士林 −0.019。但在**北投極端降雨下差 +0.089**（R1 +0.163）。
  - E 情境切換讓北投 O 由 0.367 跳到 1.148。士林 OFP 由豪雨到極端放大約 ×200，O 只增加 0.022。
  - close report:28-39 的四雨級表只有 OFP、R2、O，沒有 R1、R3，也沒有全域對照。
  - 原候選的三個說法有誤：「H2 只透過 R1 進入」結構上不對（還有經 FloodDuration、INFRA 的路徑，只是 ΔR2 ≤0.011、ΔR3 ≤0.027）；「R3 由 FloodDuration 決定」不對（R3 主要由 E 驅動）；MFP「CPT 地板」的說法也不對。
- **臺南對照**：tainan `skg/INDEX.md:113-125`；`v0220_close_report.md:33-44, 67`。
- **建議做法**
  1. 直接把 posteriors csv 的 EV_idx 做 pivot：index 為 [district, node]，columns 為 [config, H1]。加一欄 anchored−global。主句寫成：「基線雨級下錨定對 O 的影響 ≤0.02；極端降雨時北投 +0.089；士林 OFP 放大約 ×200，O 只增加 0.022」。README:51 補一行全域對照（全域配置下北投仍排第 14，士林會越過新化升一名）。
  2. 機制句改成：O 的排名主要由 E 決定；H2 數值上主要經 MFP 影響 R1（|ΔR1| ≤0.16），對 R2、R3 的影響 ≤0.03；R2 幾乎只看 FloodZone_Population_Ratio，R3 由 Elderly_Count 與 FloodDuration 共同決定。
  3. MFP 在 P(OFP=FD1)=0.9995 時仍有 0.23 質量在 FD2，原因是 MFP 的父節點 PumpStationOperation、TidalBackwater、EnvironmentalDRRIntegration 都不在 evidence 內，後驗接近均勻。CPT 在最佳父節點組合下的地板只有 0.042；加上 PSO=正常 後，FD2 會降到 0.044。這要列成「evidence 覆蓋問題」回報臺南，不是 CPT 查核問題。臺北可以另做 PSO 的情境掃描當敏感度（不宣稱是觀測）。
- **預期效果**：對外不再把「臺北潛勢圖」說成結果的主因，並指出改善的槓桿在 E 節點的資料。

### C12 PHY_BuildingAge 可餵「老>30yr」——只做敏感度
- **類別**：資料來源｜**驗證**：3 視角｜**票**：正確性 ✔ 0.90、價值 ✘ 0.68、可行性 ✔ 0.80（建議降為 medium-low）
- **依據**
  - 主計處 114 年資料：士林 28,343 棟中 30 年以上 25,251 棟（89.1%）；北投 21,921 棟中 19,246 棟（87.8%）。來源 `Data_taipei/econ/臺北市現有營造建築物棟數_...csv:143-144`。
  - pkl：這是根節點，先驗均勻；路徑為 →INFRA_BuildingVulnerability→R1→O。
  - 臺南與臺北**目前都沒有餵**（v0210 audit 第 134 行標 generic_root_prior）。
- **臺南對照**：tainan `DRT-20260818-076.md:29-31`（屋齡 ×0.85/1.00/1.25）；`nodes_vulnerability_physical.json`（PHY_BuildingAge）。
- **建議做法**
  1. 把主計處屋齡檔複製到 `data/taipei/`。
  2. **基線不改。** 另設 B 組敏感度：30 年以上比例 ≥0.5 就判「老>30yr」，raw 欄記比例。DRT 要註明：登錄簿的原定義是「平均屋齡、村里級」，這裡用的是區級比例代理。
  3. 軟先驗版本（「新」用 100 年後的使用執照棟數）和硬設定只差 0.001–0.004，用硬 evidence 就夠了。
  4. 結果分組報告：A 組不餵，用來和臺南聯合排名；B 組餵。
  5. 北士科（軟橋段、新洲美段共 35 照）只留文字說明，B 版模型目前不存在。
  6. 原候選提到的「R1 貨幣化」應引用 DRT-081（NTD 軌），不是 082；而且臺北目前並沒有計算 NTD。
- **預期效果（敏感度）**：R1 士林由 0.221 升到 0.230，北投由 0.328 升到 0.352；O 分別 +0.004／+0.011。北投因此越過安南，這純粹是只有一邊餵資料造成的，必須在文中說明。

---

## 二、medium（6 條，皆為 1 視角驗證）

### C19 H2 用 pooled、E 用單一情境
- **類別**：方法與推論｜**驗證**：1 視角（正確性＋價值＋可行性）✔ 0.72
- **依據**
  - h2 JSON:73-87 北投超大豪雨是 pooled，6.725%；E 用的是 24h500，10.848%，兩者比 1.61，超出臺南 36 區的 0.55–1.33。
  - `compute_E_exposure_taipei.py:30` 其實算了 24h350 與 24h500 兩個情境；「基線只用 24h500」是由 `run_inference_taipei.py:51` 決定的。
  - 極端降雨時：H2 用 24h650（15.84%），E 用 24h500（10.85%），方向相反。
  - 豪雨群不包含 24h350。
- **臺南對照**：tainan `build_h2_district_conditional_table_v0212.py:32-37`；`run_ototal_mc_v0220.py:181`。臺北是忠實繼承臺南。
- **建議做法**
  1. 基線維持臺南慣例。
  2. close report 加對照表：每個雨級的 H2 情境群與 %、E 情境與 % 和建物 %、兩者比值（極端降雨也要列）。
  3. 新增 pooled 敏感度臂：SCENARIOS 擴到 10 個情境，依 RAINFALL_SCENARIO_MAP 取群平均。切點借用 24h350（豪雨、大豪雨）與 24h500（超大豪雨、極端降雨），並標明是借用的。輸出 `E_node_levels_*_pooled.csv`。
  4. Data_taipei/README 補登 10 情境潛勢圖 SHP 的出處。
  5. DRT 請臺南確認這個不一致是否為刻意設計。
- **預期效果（初算）**：北投 O 由 1.148 降到約 1.00，R2 由 1.73 降到 1.42，排名約由 14 變 21；士林不變。結論寫成「北投第 14 名對 E 情境的選擇很敏感」。

### C20 排名應報區間與兩兩機率
- **類別**：結果合理性｜**驗證**：1 視角 ✔ 0.75
- **依據**
  - joint csv:14-15：安南 1.1485，北投 1.1484。
  - 以 seed 42 重算：P(北投>安南)=0.481、P(北投>中西)=0.924、P(北投>士林)=1.000。
  - 北投的排名範圍 12–16（中位數 14），士林 23–30（中位數 27，但報告寫 26）；P(士林>柳營)=0.484。
  - `TAINAN_POST`（`run_inference_taipei.py:42`）有定義但沒有被使用。
- **臺南對照**：`v0220_close_report.md:29-30, 46`。附帶：臺南安南自己的排名範圍也是 7–15，可見「排序穩定」只對間距大的情況成立。
- **建議做法**
  1. 在 stage_mc 用同一組 W 算出 39 區每次抽樣的 EV，新增欄位 `rank_min/p2.5/median/p97.5/max`、`P_gt_nearest_above/below`、`P_beitou_gt_shilin`。
  2. close report:26 與 README:48-49 改寫成「均值排第 14，逐抽樣名次 12–16；與安南的差小於 MC 標準誤（約 0.001），P=0.48，無法區分」。
  3. **不要**用「低於近似誤差 0.0009」當理由：approx_gap 兩區同號，而且 exact 值仍是安南較大。
  4. 註明「CI 重疊不代表排序不確定；在 CRN 下 P(北投>士林)=1」。
- **預期效果**：排名的敘述和 MC 不確定性一致。

### C22 山區稀釋：都市發展地區遮罩敏感度
- **類別**：切點與規則｜**驗證**：1 視角 ✔ 0.70
- **依據**
  - lulc csv 的 ΔNbS_eff 是 2.85／3.08，落在臺南最低的四分位（臺南 min 1.59、25% 3.77）。
  - 森林約占兩區面積的一半。
  - 臺南 v0186 本身也用全區當分母（`spatial_aggregate_lulc_v0186.py:196`），所以全區分母本身就是可比的定義，不算錯誤。
  - 主計處的「都市發展地區」只有面積，不能直接當分母，分子也必須疊圖裁切。
- **臺南對照**：tainan `update_evidence_real_v0188.py:37-65`；`policy_aware_anchored_inference_v0214.py:55-75`。
- **建議做法**
  1. 基線維持全區分母。
  2. `build_district_base_taipei.py` 加遮罩參數：用 `Data_taipei/policy/臺北市都市計畫使用分區SHP.zip` 排除保護區、農業區、風景區、河川區、河道、陽明山公園，分子與分母同時裁切。遮罩面積要和主計處的 1,601.2／1,666.19 ha 對帳（北投差約 18%）。
  3. 敏感度臂只替換 LandUseImperviousness、NbS_Coverage_Ratio、LP.green_infrastructure_coverage 三個節點。
  4. ΔNbS 與 α 不重跑，只在 summary 寫一行：即使 ΔNbS 放大 3 倍、α=0.75，ΔE[FD] 仍 ≤0.005，瓶頸在 P(FD1)=0.993／0.933。轉換率 0.05/0.08/0.10 照抄並標為「佔位參數」。
  5. 集水分區只做描述性剖面。洲美集水分區 2023 年有 30.7 ha 空置地。
- **預期效果（試算）**
  - 不透水率 59.6%／62.4%，判「極高」；A1 20.3%／17.4%，判「低」。
  - O 士林 +0.016、北投 +0.023，北投排名約由 14 變 12。
  - 用這張表取代 evidence_mapping §4 第 1 點的口頭說明。

### C23 「繼承、未在地化參數」表
- **類別**：方法與推論｜**驗證**：1 視角 ✔ 0.60
- **依據**
  - FloodDuration 後驗幾乎不隨 OFP 變動，P(極長)≈0.165。分解原因：MFP=FD1 時 P(極長) 仍有 0.111；DSE 後驗為「不足」0.53，這是 SMC→DSE 反置讓臺北的 FD 被抬高；TidalBackwater 用的是臺南先驗。
  - OUT_FRI 有 7 個父節點，被稀釋。
  - close report 裡沒有繼承參數清單。
- **臺南對照**：tainan `skg/INDEX.md:37-42, 70-71, 111-118, 844`；`DRT-20260822-082.md:19-21`。
- **建議做法**：新增一張表，欄位為「參數｜臺南來源（INDEX／DRT 行號）｜在臺北推論中的作用｜影響的輸出｜臺北可替代資料（已有／代理／缺）｜在地化屬於輸入層還是要改 pkl」。至少列這幾項：
  - OFP CPT（只影響全域對照）；
  - MFP 的 β 與 σ；
  - FloodDuration CPT；
  - SMC→DSE 反置；
  - TidalBackwater 先驗；
  - CI fragility；
  - DR 11 節點的鹽水溪 AHP；
  - A_a/A_b/A_c 的 AHP 比例；
  - c 鏈基準曲線與 γ；
  - R1 等權。

  可替代資料要寫實：
  - **FloodDuration 標「缺」**：積水事件查詢網與 KML 沒有延時欄，原候選說「可用來校準」是錯的。代理只能用抽水站內水位超過閾值的時數（2020-10 至 2023-11，21 站，需要先去突波）。
  - **β_Tidal** 要校準就得改 pkl，要回臺南開 DRT；臺北只能把外水位轉成 evidence（輸入層）。

  §4 另補一條：FD 與 OUT_FRI 對降雨反應遲鈍，是繼承的 CPT 造成的。
- **預期效果**：審查者一眼看得出哪些數字是臺南的，也可以據此排 taipei_v2 的在地化順序。

### C30 regress 與 check_consistency
- **類別**：驗證｜**驗證**：1 視角 ✔ 0.82
- **依據**
  - repo 內沒有任何測試或回歸檢查；`TAINAN_POST` 沒被使用。
  - `reference_tainan/` 的檔案與臺南原檔、pkl 的 md5 相同（pkl 為 48549a16…）。
  - 審查者實測：用臺北的函式套臺南輸入，5 區後驗的最大差是 2.2e-16；37 區 MC 共 185 格，0 格不符。
  - 但用臺南 lulc 跑 stage_policy 時，安南的 share 不一致（臺北輸出 52.6/8.1/39.3，臺南是空值），這正是 C02 的問題。
- **臺南對照**：tainan `run_ototal_mc_v0220.py:195-258`；`v0213/batch3_validation_report.md:37-39`（V4 回歸）。
- **建議做法**
  1. `load_e_levels` 改成接受路徑清單（合併 v0213 與 v0214a），`LULC_CSV` 與 `OUT` 改成參數。
  2. stage `regress`：
     - (a) 37 區後驗，要求 |Δ| <1e-9；
     - (b) 用 seed 42 重算 MC 五欄，四位小數完全相同；
     - (c) 把臺南的 `ototal_policy_decomposition_v0220.csv` 複製到 reference_tainan，用 HOTSPOT8 跑 policy 逐欄比對。預期 C02 修正前會 FAIL，修正後 PASS。
  3. 結果寫進 `summary.regression`，並附 pgmpy 與 numpy 版本。
  4. `scripts/check_consistency_taipei.py` 只保留有意義的檢查：錨定後 OFP 等於 H2 表、H2 表可以由 shp_baseline 重算、MC 與排名可重算、殘差與 share 加總、E 等級對得上 tainan_cuts、比率可由分子分母重算。不要放「後驗加總為 1」這類由 pgmpy 保證的項目。
  5. close report 新增 V4 回歸段。
- **預期效果**：「照抄」有機器可驗的等價證明，之後的改動也有回歸保護。

### C31 溯源欄位、固定版本日期、鎖 pgmpy
- **類別**：文件與登錄｜**驗證**：1 視角 ✔ 0.60
- **依據**
  - `run_inference_taipei.py:261-262` 的 summary 只有 version、date、model 檔名、H1。
  - 主 pkl 從未跑過 `check_model`（只有 `:155` 對 do 引擎跑過）。
  - `build_shp_baseline_taipei.py:117`、`compose_evidence_taipei.py:95`、`run_inference_taipei.py:262` 都用 `date.today()`。
  - requirements 寫的是 `pgmpy>=1.1.2`。
  - 實測：pkl sha256 為 2cbe3f43…2ce0，與臺南快照相同；check_model=True；DAG=True；193/269；n_evidence 兩區各 24，沒有被丟棄的鍵。
  - 原候選要修正的地方：close report:4、:15 其實已經寫了節點數、邊數與 α/N/seed；臺南快照不是 git repo，所以沒有 commit 可記；臺南自己也沒有鎖 pgmpy 版本。
- **臺南對照**：tainan `v0220_close_report.md:3-5`；`bn_v0220_build_summary.json`；`build_h2_district_conditional_table_v0212.py:91-92`；`run_ototal_mc_v0220.py:410`。
- **建議做法**
  1. 在 `taipei_paths.py` 定義 `VERSION`、`RELEASE_DATE`，三支腳本改為引用；重跑時升 patch 號。
  2. 在 main 開頭 assert `check_model`、DAG、(193, 269)。
  3. summary 加 provenance：`bn_pkl_sha256`、`pgmpy_version`、`python_version`、`check_model`、`dag_acyclic`、`tainan_snapshot="tainan-flood-bn-20260903"`、常數（DIRICHLET_ALPHA、N_MC、SEED、W_EQ、SIGMA、NBS）、`dropped_evidence_keys`。
  4. requirements 鎖 `pgmpy==1.1.2`，其餘套件鎖成實測版本。
  5. close report 標頭補「check_model PASS、DAG 無環、sha256 前 12 碼、pgmpy 1.1.2」。
- **預期效果**：能追溯結果是用哪個 pkl、哪個 pgmpy 版本跑的，臺南升版時也能判斷要不要重跑。

---

## 三、審查過程額外發現（未獨立投票，請 Codex 覆核）

| id | 內容 | 位置 |
|---|---|---|
| N1 | 收容所用郵遞區號回退判區，把 26 筆大同區收容所算進士林（69→43、水災適用 36→18），狀態仍是「高」 | `scripts/build_district_base_taipei.py:73-74` |
| N2 | 政策 do 臂移除 DR evidence 後，經未觀測的 LP.policy_intervention 形成後門，單軸 do(DR.NS) 與 do(DR.SMC) 的 ΔO 完全相同 | `scripts/run_inference_taipei.py:144-156, 225-252` |
| N3 | README:63「2016 後幾乎沒有 ≥15 cm 紀錄」與 KML 2016-11 以後士林北投仍有 56 筆不符 | `README.md:63` |
| N4 | RiverWaterLevel 的兩個父節點都已設 evidence，它本身又沒有子節點，敏感度精確為 0；close report:62 的待辦可以撤除 | `taipei_v1_close_report.md:62` |
| N5 | Data_taipei/README.md:11 把區級月報誤寫成里級 | Data_taipei |

---

## 四、被駁回的候選（不建議照原案做）

| id | 標題（簡） | 駁回理由 | 可保留的降級做法 |
|---|---|---|---|
| C07 | RiverWaterLevel 等三節點是死端 | 判準錯了：out_degree 或是否為祖先，不等於 evidence 敏感度。只有 RiverWaterLevel ≡0；LP.river_corridor 與 DR.NS 經後門 \|ΔO\|≤0.006；GEO_StormSurgeRisk 餵入後 ΔO 可達 0.011；DetentionPond 與 EconomicActivity 其實在 pkl 內（孤立節點）；DRT-072 的引用錯置 | 只寫 N4，並說明後門機制 |
| C11 | UrbanDrainageStandard 餵「低標準」 | 78.8 mm/hr 是下水道設計標準，登錄簿的變數是區域排水重現期；社子島、關渡洲美並非 5 年標準；結果方向完全取決於尺度選擇（低標準 O +0.022／+0.041，高標準 −0.021／−0.039）；只餵臺北會破壞對稱 | 兩種方向各跑一條敏感度 |
| C13 | AccessToShelters 改距離法或改分子 | 臺南程式只用到 cuts[0..2]，實際 L5 門檻 >0.201，所以三種口徑都是 L5；臺南本身也沒做距離法；只改臺北會破壞可比性 | 無（N1 另案修正） |
| C14 | A4／A5 切點應重算 | L4 與 L5 都對應到「高」，兩區都不受影響 | 文件勘誤：L5 門檻應為 40.64 cms／0.201（cuts[3] 沒被使用），不是 44／0.216 |
| C15 | Other_pct 定義不同 | 定義確實不同（07/08 對 07/08/09 再扣 A1/A2），但對 RR 的影響 <0.0003，看不出差別 | 可選：`build_district_base_taipei.py:43` 改成 v0186 定義，求文件一致 |
| C16 | 捨入造成狀態翻轉 | 臺南 LULC 也先捨入；根本原因是 C01；C01 修正後沒有任何值落在切點 ±0.005 內 | 無 |
| C17 | VS 切點不可觀測且衝突 | 登錄簿和 v0151 只在 ElderlyAlone 一個節點衝突；預期的 R3 方向寫反；ΔO ≤0.0046；DRT 決策 3 已記錄 | 可補 ElderlyAlone 110–114 年穩定性表（登錄簿切點下士林 high、北投 medium） |
| C18 | Population／BuildingDensity 改用登錄簿口徑 | 一旦有 BD 的 evidence，PD 就被 d-分離；登錄簿的棟/ha 用在高樓化的臺北會整市都判「低」，是尺度假象；臺南 37 區用的也是代理值 | 加一行 BD 敏感度（BD 高→低：北投 O 1.148→1.058，排名約 17；士林 0.754→0.706） |
| C21 | 缺 R3_rate、人數型 E 節點 | 4 個 E 節點是懸空根節點，不影響任何結果；臺南 v0220 也沒有 R3_rate | targets 加 R3_rate（士林 0.355、北投 0.476），並註明那 4 個 E 節點沒有作用 |
| C24 | TidalBackwater 餵外水位 | 登錄簿是類別式定義；臺南有分區規則可循（`compute_district_policy_evidence.py:546-600`）；外水位高程基準不一；計畫洪水位沒有士林北投的點；只餵臺北破壞可比性；給「中」反而讓 MFP 略降 | 用潮差判斷是否感潮，做敏感度（給「高」時 O 士林 0.799、北投 1.215，排名 14→10） |
| C25 | PumpStationOperation／INFRA_DrainageFragility 用代理值 | 「正式站比例」的語意倒置，而且和 SMC 重複計算；燈號是需求驅動，不代表能力；do(DSE) 本來就切斷父節點；沒有符合定義的資料；IDF 的 ΔO <0.005 | PSO 情境掃描當敏感度（O 士林 0.695／0.735／0.841） |
| C26 | Monitoring／Substation／TransportHub 餵值 | 效果 ΔO ≤0.01，遠小於 CI；登錄簿 TransportHub 是加權定義；只餵臺北破壞對稱 | 無 |
| C27 | EconomicVulnerability 餵低收比 | 不是 R 或 O 的祖先；OUT_FRI 只變 0.0003；臺南沒有餵 | 文件註明 `low_income_by_district_tsis.csv` 沒被使用 |
| C28 | 用 1999 派工建 λ_event | 口徑不同：臺北 λ 22.5／15.2 天/年，臺南最高只有 7.57；n=2 無法做 A3 | H2 JSON 補 event_conditional_framework 欄位，README 與 close report 寫明「只能做事件條件機率」；λ 只能用 CWA 事件日過濾後當敏感度 |
| C29 | FD1 文件說法錯誤 | 錯誤說法源自臺南 v0212 的 docstring；數值不受影響；n_polygons_flooded 沒被下游使用 | 低優先文件勘誤（DRT 決策 1、evidence_mapping:47、JSON:7 的「自分母剔除」改為「併入 FD1」） |
| C32 | 補齊臺南的交付清單 | 大多是格式要求；DAG 圖內容兩邊相同 | literature 權重 MC 一行穩健性說明（北投排名 13、士林 26，結論不變） |
| C33 | close report 與 DRT 對齊固定章節 | 不動清單與變更檔清單是 minutes 的慣例，不是 close report 的固定章節；臺南 DRT 格式本身也不統一 | DRT-TPE 擴充「需要臺南端回覆」（空隙歸級、MFP 父節點的 evidence 覆蓋、SCEN_BY_H1 與 H2 情境群不一致、quantile 切點跨市使用、R3 對 ElderlyAlone 的方向），並加「上游 pkl 升版即觸發重跑」條款 |
| C34 | RiverWaterLevel 改資料法則 | Δ=0 已用數值確認；洲美外水位感測器失效；沒有堤頂高；沒有 2019 年資料 | 與 N4 相同 |
| C35 | DR.NonStructural 改用 AHP 計分 | AHP 五個分量有三個缺資料；門檻沒有校準；改了破壞可比性 | 加一行敏感度：DR.NS 高／中／低（北投 1.148／1.151／1.154，會和安南對調名次） |
| C36 | 河廊改用河川區域線判態 | 登錄簿 thresholds 是 null；DRT 第 3 題未回覆；只改臺北破壞可比性；後門影響很小 | 計算描述性指標（河濱高灘地：士林 2.53%、北投 0.59%；堤防長度），但不改狀態；改寫 DRT 第 3 題 |

---

## 五、未驗證的候選（超過 36 條驗證上限，未經任何審查）

下列 6 條在合併後排在第 37–42 名（全部 low），沒有進入驗證階段。內容是讀者原始提出的版本，數值與行號**未經覆核**，請 Codex 當作線索自行查證，不要直接採用。

| id | 類別 | 標題 | 依據（未覆核） | 建議做法（未覆核） |
|---|---|---|---|---|
| C37 | 程式正確性 | 區面積分母來源不一（潛勢圖與 LULC 用里界 dissolve、人口密度用 TSIS 土地面積，士林差 1.3 km²）且 flooded_building_area_pct 捨 2 位後 E_pop 無法由 CSV 重算 | scripts/build_shp_baseline_taipei.py:53 town = d.geometry.area（里界 dissolve，EPSG:3826）→ shp_baseline town_area_m2 士林 61,078,024／北投 57,381,714；build_district_base_taipei.py:44 area_km2 同源 61.078/57.382（本次複核 :44 area_km2 = dist.geometry.area/1e6）；taipei_common.py:53,62 pop_density 用 TSIS 土地面積 62.3682/56.8216（district_base_indicators_taipei_v1.csv:2-3），士林差 2.1 %、北投差 1.0 %。lulc_total_km2 與 dissolve 面積完全相等（57.382）顯示 LULC 以同一里界裁切，GIS 內部一致。E_stratified_exposure_taipei_v1.csv:3 北投 24h350 E_pop_total 50.8，但用該列已捨入的 flooded_building_area_pct 0.02 重算得 47.1（實際 pct 0.022，compute_E_exposure_taipei.py:91 round 2 位、:97 用未捨入值）。臺南 v0191:49 潛勢統計用 town shp 面積，v0181:91 人口密度直接讀 opendata（臺南 lulc_aggregation_v0186.csv 的 area_km2 vs lulc_total_km2 亦未統一）。 | (1) district_base_indicators 同時輸出 area_km2_gis 與 area_km2_tsis，evidence_mapping §4 註明分母來源；若要統一，pop_density 改用 GIS 面積或反之，二擇一並記錄與主計處差異；(2) flooded_building_area_pct 存 4 位小數或另存 km² 讓 E_pop 可由 CSV 重算；(3) CSV _meta 或 README 寫明分母來源。（狀態判定前的捨入問題見 C16。） |
| C38 | 程式正確性 | unzip_dir 以「資料夾存在」當作已解壓，中斷後會靜默缺檔；read_csv_any 吞掉所有例外可能落到錯誤編碼；OUT.mkdir 在 import 時執行 | scripts/taipei_paths.py:18-20 if not d.exists() 才解壓，解壓中途失敗會留下不完整資料夾且下次直接跳過；:50-54 except Exception: continue 會把 pandas 解析錯誤也當編碼錯誤，接著以 big5/cp950 解一個其實是 UTF-8 的檔；:13 OUT.mkdir 在 import 時執行。LULC zip 檔名含中文（flag_bits 判斷 :24-29 目前正確解出）。 | 解壓到 d.with_suffix('.tmp') 完成後 rename，或寫 _done 標記；read_csv_any 只攔 UnicodeDecodeError，解析錯誤直接拋出；mkdir 移到各 main()。 |
| C39 | repo結構 | 低優先清理：res_a 重複推論、TAINAN_POST 未使用、data/taipei 三個副本與 reference_tainan 數檔無腳本讀取、人口檔檔名與 README 標示誤導、缺 min(pct,100)／GRIDCODE 白名單／零面積防呆 | scripts/run_inference_taipei.py:187,193-194 在 anchor 迴圈結束後再呼叫 res_a() 多做一次 OFP 錨定推論只為列印；:42 TAINAN_POST 未使用。本次複核 ls data/taipei 確認 12 檔；grep 顯示 low_income_by_district_tsis.csv、pump_stations_taipei_2026H1.csv、taipei_pump_catchments.kml 與 bn_engine/reference_tainan/E_stratified_exposure_v0213.csv、build_bn_v0220.py、per_district_conditional_inference_v0212.py 無腳本引用（實際讀取：taipei_common.py:27,41,44,47 四個 csv；build_district_base_taipei.py:66,72；compute_E_exposure_taipei.py:61-62 與 taipei_paths.py:40 三個 zip）。pop_by_age_village_2023-01.csv 檔名暗示 2023-01 與里級，實為 112/1–115/7 區級月序列（C01）；README.md:27 稱 data/taipei 為「臺北輸入資料副本」、close_report:66 交付清單「data/taipei/*（12 檔輸入副本）」。compose_evidence_taipei.py:122 缺 v0188:125 的 min(pct,100)（臺北 LULC 總面積＝區面積，目前無影響）；build_shp_baseline_taipei.py:59 a[int(GRIDCODE)] 對 1–5 以外的值會 KeyError、:97 a_fd.sum()==0 無防呆。 | 刪 res_a；TAINAN_POST 改用於 C30 回歸 stage；三個未用副本要嘛在 C06（KML／半年報）、C27（低收入）用上，要嘛在 README「內容導覽」註明「備用、未進推論」並列出附檔用途或移到 docs/；人口檔改名為 pop_by_age_district_monthly_2023-01_2026-07.csv 或改放真正的里級檔；加 min(pct,100)、GRIDCODE 白名單與零面積防呆。 |
| C40 | 方法與推論 | 短延時積水模擬圖（78.8/100/130 mm/hr）與事件日短延時雨量可作北士科 H2 的補充情境（A 版不改 H2 表） | 臺北 H2 錨定表只用水利署 24h 潛勢圖 10 情境（shp_baseline_taipei_v1.csv：24h200 北投淹水面積 0%、24h350 0.45%、24h500 10.85%），BN H1 為 CWA 24h 雨級。Data_taipei/hazard/臺北市降雨積水模擬圖_78.8mmhr.kml、_100mmhr.kml、_130mmhr.kml（112 年版，含深度分級，≤15 cm 不顯示；README:49）；事件日雨量摘要顯示臺北事件常為短延時主導（2019-05-20 60 分 88 mm 超 78.8 mm/hr）。 | A 版不改 H2 表（保持與臺南可比），另算三個短延時情境的區級／集水分區級 FD 分布作附錄敏感度；B 版北士科模型以短延時圖為主要危害層。 |
| C41 | 資料來源 | 透水鋪面、雨水流出抑制設施、公共設施基地保水圖層可餵 PermeablePavement_Ratio／NZ 節點與 NbS 子設施，但在 v0220 不影響 R/O | Data_taipei/policy/水綠地圖集/3.透水鋪面_人行道透水鋪面.geojson 848 筆（含 面積/體積）、停車場/公園/學校/PAC 鋪面各一層、6.保水防災_雨水流出抑制設施.geojson 858 筆（士林北投約 177 筆字串命中）、6.保水防災_公共設施基地保水.geojson 168 筆。登錄簿 nodes_nz.json #8 PermeablePavement_Ratio thresholds [0.05, 0.3]（透水鋪面面積／路面總面積），v0210 溯源 calibrated_NZ文獻、未餵；pkl 實查 PermeablePavement_Ratio 與 NZ.RainGarden_Bioswale_Density 只指向 ESS_* 節點，非 R/O 祖先；NbS_Coverage_Ratio 登錄簿 sub_facilities 5 子設施。 | 算區級透水鋪面面積／道路面積（交通使用 438.0/434.4 ha）與抑制設施體積密度，寫入 district_base 作 NbS 子設施佐證與 B 版輸入；不急著餵入 A 版。 |
| C42 | 文件與登錄 | DisabilityPopulation_Ratio 與 E 節點身障數在臺北是 114 年底區級實測，evidence JSON 應逐節點加 data_quality 欄（real_measured 等四級）並註明與臺南 proxy 不同 | scripts/taipei_common.py:47-49,68 用 data/taipei/disability_by_district_tsis.csv（主計處 114 年底 總計）；Data_taipei/social/臺北市身心障礙人口數_行政區別_102年以後_主計處.csv 另有長序列。臺南登錄簿 nodes_vulnerability_social.json DisabilityPopulation_Ratio data_availability「High (proxy)」、R2（全市率×老化調整），臺南 E 節點身障數亦為全市 102,142 依等級分攤。evidence_mapping:14 未標資料品質。 | evidence JSON _meta 加 data_quality 欄（仿臺南 real_measured/real_calculated/proxy/estimate 四級）逐節點標示；此節點標 real_measured；FloodZone_Disability_Count 亦註明分子是實測而臺南是分攤估計。 |
