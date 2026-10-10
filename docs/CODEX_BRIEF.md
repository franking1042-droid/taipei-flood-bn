# 給 Codex 的任務簡報：臺北移植版 BN（taipei_v1）覆核與優化

> 工作目錄：`C:\Users\R1462\OneDrive\中鋼計畫\taipei-flood-bn`（git repo，分支 `main`；taipei_v1 結果在 commit `5084067`）
> 所有輸出一律用繁體中文。引用檔案時寫相對路徑加行號，例如 `scripts/run_inference_taipei.py:246`。只寫你實際讀到的內容，讀不到就寫「讀不到」，不要猜。

---

## 1. 任務目標

1. **先讀臺南版**（NTU-STEMLab 臺南市 37 區淹水風險 BN，v0.22.0 快照 2026-09-03），弄懂四件事：H2 錨定表、16 節點 evidence、E 暴露節點、O_total MC 與三軸政策分解是怎麼算的，以及實驗室的版本與 DRT 規範。
2. **再審臺北版 taipei_v1**。它把臺南 `bn_v0220.pkl` 直接移植到士林區、北投區（北士科所在）：pkl 與 CPT 完全不動，只換三份輸入（H2 錨定表、區級 16 節點 evidence、潛勢區暴露 E 節點）。
3. 先前已有一輪三視角審查（正確性、價值、可行性），產出 **16 條已確認的優化候選**（第 4 節）和 **20 條被駁回的候選**（第 5 節）。你要做的是：
   - 逐條覆核已確認候選：判定同意、修正或反對，並附上你自己讀到的「檔:行」證據；
   - 補充審查遺漏的問題；
   - 對每一條給出**具體修改方案**：要改哪些檔、diff 或步驟、驗證方式，以及預期數值；
   - 經使用者同意後才實作。實作要依第 6 節的硬規則進行。

---

## 2. 路徑與角色

| 角色 | 絕對路徑 | 權限 |
|---|---|---|
| 臺北 repo（工作目錄） | `C:\Users\R1462\OneDrive\中鋼計畫\taipei-flood-bn` | 可改（受第 6 節限制） |
| 臺南 repo 快照 | `C:\Users\R1462\OneDrive\中鋼計畫\tainan-flood-bn-20260903` | **唯讀**。此資料夾不是 git repo |
| 臺北原始資料倉 | `C:\Users\R1462\OneDrive\中鋼計畫\團隊內部討論紀錄\中綱BN建構\Data\Data_taipei` | **唯讀** |

- **Data_taipei/README.md 的角色**：它是臺北所有原始資料的登錄簿，分 social／lifeline／econ／hazard／policy 五類，列出每個檔的出處、筆數與限制。repo 內的 `data/taipei/` 只是其中 12 個檔的副本。要新增輸入時，先查這份 README，再把需要的子集複製到 `data/taipei/`，並在 repo README 註明來源。
- 已知 README 誤記：Data_taipei/README.md:11 說「士林北投_各里人口數按年齡分.csv」是里級，實際是**區級 2 區 × 3 性別 × 43 期（112/1–115/7）的月報**。真正的里級資料要從全市 Big5 檔 `social/臺北市各里人口數按年齡分.csv` 篩區域代碼 11 碼的列（見 C01、C05）。
- 你的沙盒如果讀不到工作目錄以外的兩個路徑，請直接告訴使用者，不要用猜的內容代替。

---

## 3. 建議閱讀順序

**臺南（先讀，核心 12 檔）**，前綴為 `C:\Users\R1462\OneDrive\中鋼計畫\tainan-flood-bn-20260903\`：

1. `README.md`：協作約定，包括「模型修改必留 DRT」與「條件式 dual Brier 不得回退」。
2. `skg\INDEX.md`：重點讀 1–140 行（v0.21.x–v0.22.1 變化重點與待辦）、243–253（GC1 與分母定義）、325–434（16 節點 evidence 與切點）。
3. `skg\decisions\notes\discretization_principles.md`：原則 3「永不採 quantile」。
4. `skg\decisions\DRT\open\DRT-20260819-079.md`：O_total 等權配方，以及 SMC→DSE、NbS→RC 兩條方向反置邊。
5. `bn_engine\results\v0220\v0220_close_report.md`：close report 的固定章節。
6. `scripts\build_h2_district_conditional_table_v0212.py`：H2 錨定表的產生方式。
7. `scripts\per_district_conditional_inference_v0212.py`：virtual evidence 錨定。
8. `scripts\update_evidence_real_v0188.py`：6 個注入節點的切點。
9. `scripts\compute_E_exposure_v0213.py` 與 `scripts\discretize_E_nodes_v0213.py`：E 暴露與情境內五分位。
10. `scripts\policy_aware_anchored_inference_v0214.py`：ΔNbS_eff 與 α 三值。
11. `scripts\run_ototal_mc_v0220.py`：stage_mc、stage_policy、stage_validate。
12. `scripts\run_conditional_validation_v0212.py`：EVENT_H1_MAP、λ_event、Brier 計算。

需要時再讀：`scripts\extract_real_policy_evidence_v0185.py`、`scripts\spatial_aggregate_lulc_v0186.py`、`skg\nodes\nodes_vulnerability_social.json`、`skg\nodes\nodes_dr.json`、`bn_engine\results\v0210\provenance_audit_all172_v0210.csv`、`scripts\build_bn_v0213.py`（R 配方 product_cpd 的定義在 284–304 行）。

**臺北（全部讀）**：

`README.md` → `docs\DRT-TPE-20261010-001_transplant_v0220_to_taipei.md` → `docs\evidence_mapping_taipei_v1.md` → `bn_engine\results\taipei_v1\taipei_v1_close_report.md` → `taipei_v1_summary.json` → `scripts\taipei_paths.py` → `scripts\taipei_common.py` → 依執行順序讀五支腳本（見 AGENTS.md）→ `bn_engine\cpt_priors\h2_district_conditional_table_taipei_v1.json` → `bn_engine\results\taipei_v1\*.csv/json` → `bn_engine\reference_tainan\`（臺南參考表副本，其中 pkl 與臺南原檔 md5 相同）。

最後讀 **Data_taipei\README.md**。

---

## 4. 已確認候選（請逐條覆核）

驗證強度的意思：「3 視角」表示正確性、價值、可行性各由一位審查者驗過；「1 視角」表示由一位審查者合併三視角驗證，強度較低，請你特別仔細覆核。括號內的「異議」表示三票中有一票判 refuted，但候選整體仍成立，必須採用修正版做法（詳見 `docs/optimization_candidates_v1.md`）。

| id | 類別 | 嚴重度 | 驗證強度 | 一句話 |
|---|---|---|---|---|
| C01 | 資料來源 | high | 3 視角 | `taipei_common.py:27-32` 把 112/1–115/7 共 43 期月報全部加總，當成「112/1 年齡比例」。應改取 114/12 單期，直接用該期的各齡人數。改完後士林 FloodZone_Elderly_Count 24h500 約 772，會跨過切點 740.1（不是 775.2），由 medium 變 high |
| C02 | 結果合理性 | high（價值票建議 medium） | 3 視角 | RR_total 為負時仍輸出 share_%（`run_inference_taipei.py:246-248` 用的是 `abs(tot)`）。應改回臺南的 `tot>1e-9` 條件，補 contrib 與 share_*_dsefix 欄，並改寫 close report §3 |
| C03 | 切點與規則 | high | 3 視角（正確性異議） | 有 5/32 個 E 值落在臺南兩級之間的「無觀測空隙」。其中只有 3 個節點會進推論。北投 Population_Ratio 單獨決定了 O=1.148 與第 14 名：若歸 medium，O 為 1.012、排第 21 |
| C04 | 驗證 | high | 3 視角（可行性異議） | 目前完全沒有驗證。應建 stage_validate：深度 Brier（明寫「驗的是潛勢圖加錨定」）、里級 λ 空間排序，做不到的軌一律標 N/A |
| C05 | 資料來源 | high | 3 視角 | 「人口沿建築分布」假設可以用里級人口加門牌點位來檢驗。北投 24h350 近零暴露經檢驗是真的；北投 24h500 人口暴露約減半；士林上修 2–4 倍。這些結果只放敏感度臂 |
| C06 | 切點與規則 | high | 3 視角（可行性異議） | DR.StructuralMeasures_Coverage 依登錄簿定義應為 CMS/km²，兩區會變成「中」。目前只有「抽水量加管線」兩項有資料。只做 B 版敏感度臂；基線維持 A 版 |
| C08 | 切點與規則 | high（價值票建議 medium） | 3 視角 | 16 節點中有 15 個兩區同值。README:60 與 evidence_mapping:24「兩區抽水量都超過臺南最高」為錯：北投 147.88 cms 小於臺南永康 182.75。另發現收容所郵遞區號 bug |
| C09 | 結果合理性 | high | 3 視角 | 北投「大豪雨→超大豪雨」的階梯應拆成三個成分：臺北潛勢圖本身的門檻、SCEN_BY_H1 單情境切換、product_cpd 的零暴露地板。R1、R2 落在地板 0.1628；R3 不在地板 |
| C10 | 結果合理性 | high（價值票建議 medium） | 3 視角（正確性異議） | H2 錨定在基線雨級對 O 的影響 ≤0.02，結果主要由 E 節點決定。close report 應改成 8 節點 × 4 雨級 × {錨定, 全域} 的表。MFP 的 0.23 來自未觀測父節點，不是 CPT 地板 |
| C12 | 資料來源 | high（建議降 medium-low） | 3 視角（價值異議） | PHY_BuildingAge 可餵「老>30yr」（士林 89.1%、北投 87.8%），但臺南沒餵，只能當 B 組敏感度。效果 O +0.004／+0.011 |
| C19 | 方法與推論 | medium | 1 視角 | 同一次推論中，H2 用情境群 pooled，E 用單一 24h 情境。北投兩者比 1.61，超出臺南 0.55–1.33 的範圍。極端降雨的情況方向相反 |
| C20 | 結果合理性 | medium | 1 視角 | 北投與安南只差 0.0001，P(北投>安南)=0.481。排名應報區間：北投 12–16、士林 23–30 |
| C22 | 切點與規則 | medium | 1 視角 | 山區稀釋。以都市發展地區遮罩做敏感度臂：北投排名約 14→12。ΔNbS/α 不必重跑，瓶頸在 P(FD1) |
| C23 | 方法與推論 | medium | 1 視角 | close report 加「繼承、未在地化參數」表。FloodDuration 鈍化來自 MFP 分散、DSE 反置與 OUT_FRI 7 父稀釋 |
| C30 | 驗證 | medium | 1 視角 | 新增 stage regress，用臺南輸入逐位比對 v0220（已實測差 2.2e-16）。policy 回歸預期會在 share 欄 FAIL（與 C02 相關） |
| C31 | 文件與登錄 | medium | 1 視角 | 補上溯源：check_model、DAG、pkl sha256、pgmpy 版本。三支腳本的 `date.today()` 改成固定 RELEASE_DATE；鎖定 `pgmpy==1.1.2` |

**審查過程額外發現（請一併覆核）**：

- **N1 收容所郵遞區號 bug**：`scripts/build_district_base_taipei.py:73-74` 會回頭用郵遞區號判區。`shelters_taipei.csv` 有 26 筆「鄉鎮=大同區」（編號 SA103-xxxx），郵遞區號誤填為 111，因而被算進士林。修正後士林收容所 69→43、水災適用 36→18，每千老人 1.114→0.694，仍是 L5「高」。需同步更新 evidence_mapping:25 與 JSON 的 raw_values。
- **N2 政策 RR 的後門機制**：單軸 do(DR.NS=高) 與 do(DR.SMC=高) 的 ΔO 完全相同（士林 −0.0019、北投 −0.0031）。原因是 do 臂會從 evidence 移除該節點，而兩者共同的父節點 `LP.policy_intervention` 未被觀測，形成後門路徑。所以 close report:48 把負 RR 全歸因於「CPT 方向反置洩漏」並不完整。請用 pgmpy 的 `is_dconnected` 或 `active_trail_nodes` 確認，再寫進 C02 的改寫。
- **N3**：README.md:63 寫「2016 後幾乎沒有 ≥15 cm 積水紀錄」，但歷史積水 KML 在 2016-11 以後士林北投仍有 56 筆。這與 C04 相關。
- **N4**：RiverWaterLevel 的兩個父節點都在 evidence 內，而且它沒有子節點，所以敏感度**精確為 0**。close report:62 的待辦可以撤除，改寫成一句說明。

---

## 5. 被駁回的候選（不要重做）

C07、C11、C13、C14、C15、C16、C17、C18、C21、C24、C25、C26、C27、C28、C29、C32、C33、C34、C35、C36。理由與「可保留的降級做法」見 `docs/optimization_candidates_v1.md` 第四節。其中下列幾條的**降級版**可以順手做，但不列為主任務：

- C11、C18、C24、C25、C35：各加一行敏感度表；
- C21：targets 加 R3_rate；
- C28：H2 JSON 補 event_conditional_framework 欄位，並寫明「只能做事件條件機率，不得做年度風險」；
- C33：DRT-TPE 擴充「需要臺南端回覆」的題目，並加「上游 pkl 升版即觸發重跑」條款；
- C14、C29：文件勘誤。

**未驗證的 C37–C42**（low，超過 36 條驗證上限，未經任何審查）列在 `docs/optimization_candidates_v1.md` 第五節：面積分母來源不一、`unzip_dir`／`read_csv_any` 的防呆、repo 清理、短延時積水圖補充情境、透水鋪面圖層、data_quality 欄。請當作線索自行查證，確認屬實再提修改方案。

---

## 6. 硬規則

1. **不得修改** `bn_engine/bn_v0220.pkl`、任何 CPT、節點、狀態或邊，也不得 `pickle.dump` 覆寫 pkl。模型本體的問題（例如兩條方向反置邊、MFP 父節點的 evidence 覆蓋）只能寫成「回報臺南端」的 DRT 問題。
2. **不得修改** `bn_engine/reference_tainan/` 的既有檔。可以新增臺南參考檔（例如 `ototal_policy_decomposition_v0220.csv`），但要在 README 註明來源路徑與 md5。
3. 臺南 repo 與 Data_taipei **唯讀**。
4. `bn_engine/results/taipei_v1/` 保留 v1 原樣。新版本以 `taipei_paths.py` 的 `VERSION="taipei_v1a"` 產出到 `bn_engine/results/taipei_v1a/`（見 C31）。日期用固定的 `RELEASE_DATE`，不要用 `date.today()`。
5. **基線與敏感度臂要分開**：
   - 會破壞與臺南 37 區可比性的改動，一律只做敏感度臂，不改基線。這類包括：E 用門牌法、SMC 用 CMS/km²、只有臺北餵的新節點、pooled E、都市發展地區分母。
   - 只有 bug 修正與文件更正會改基線，例如 C01、C02 的條件、N1、C31。
6. 每項改動都要寫進 DRT。新開 `docs/DRT-TPE-YYYYMMDD-002_<主題>.md`，frontmatter 沿用 001 的欄位（id／title／status／date／scope／related）並加 `related_drt`。本文依序為：背景 → 資料與方法 → 結果（表）→ resolution → 新發現 → known limitations → 交付（變更檔清單）→ 不動清單（pkl、CPT、reference_tainan、taipei_v1 結果）。
7. 不得把臺南的 Brier 數字（0.5801、0.5810、0.5248 等）當成臺北的成績；不得出現「年度風險」或「年期望損失」。
8. 每次重跑後，先跑 C30 的 regress 與 check_consistency，PASS 才更新報告。
9. 所有數值結論都要附重算指令或腳本路徑。

---

## 7. 建議施作順序

- **Phase A（安全網與溯源）**：C31 → C30。先讓回歸測試可以跑。
- **Phase B（會改基線的修正）**：C01 → N1 → C02（含 N2 的敘述）→ 重跑全鏈 → 重算 C03 的空隙清單。C01 會讓士林 Elderly_Count 離開空隙，所以 C03 的數字要以 C01 修完後為準。
- **Phase C（報告重寫，不改數字）**：C09、C10、C20、C23、C08 的文件修正，以及 N3、N4。
- **Phase D（敏感度臂）**：C03 level±1、C05 門牌法、C06 B 版、C08/C06 SMC 表、C12、C19/C09 共用的 pooled E、C22 遮罩。每一臂都要有獨立 CLI 旗標，輸出放在 `taipei_v1a/sensitivity/`。
- **Phase E（驗證）**：C04 的 stage_validate。
- 每個 Phase 結束要停下來回報，等使用者同意再進下一個 Phase。

---

## 8. 回報格式

**(a) 覆核總表**

| id | 你的判定（同意／修正／反對） | 覆核證據（檔:行） | 要改的檔案 | 基線或敏感度臂 | 驗證方式 | 預期數值 | 狀態（未動／已實作／PASS／FAIL） |
|---|---|---|---|---|---|---|---|

**(b) 逐條細節**：判定理由；修改方案用 unified diff，或寫明逐步步驟加函式簽名；驗證指令與實際輸出摘要；與審查者給的預期數值對照，若有差異要說明原因。

**(c) 新發現**：用同一格式列出你找到、而清單沒有的問題。

**(d) 待臺南端回覆的問題清單**：可直接貼進 DRT-TPE 的「需要臺南端回覆」。

**(e) 執行紀錄**：跑過的指令、耗時、regress 與 check_consistency 的 PASS／FAIL 清單、pgmpy 版本、pkl sha256。
