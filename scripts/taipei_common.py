# -*- coding: utf-8 -*-
"""臺北（士林、北投）區級人口分層：供 compose_evidence 與 compute_E_exposure 共用。

資料：
  - data/taipei/pop_by_age_village_2023-01.csv  民政局「各里人口數按年齡分」（112 年 1 月），只取年齡結構比例
  - data/taipei/population_density_by_district_tsis.csv  主計處統計資料庫（114 年底）總人口、面積、密度
  - data/taipei/elderly_alone_by_district_tsis.csv       列冊獨居老人（114 年底）
  - data/taipei/disability_by_district_tsis.csv          身心障礙人數（114 年底）
人口分層 = 114 年底總人口 × 112/1 年齡比例（與臺南 v0151 以 114 年人口為基準對齊）。
"""
import re
import pandas as pd
from taipei_paths import DATA, DISTRICTS, read_csv_any


def latest_period(df, col="統計期"):
    """統計期如 '114年底' → 取最大年份。"""
    yrs = df[col].astype(str).str.extract(r"(\d+)")[0].astype(float)
    return df[col][yrs.idxmax()]


def _num(x):
    return float(str(x).replace(",", ""))


def district_population_strata():
    pop = read_csv_any(DATA / "pop_by_age_village_2023-01.csv", dtype=str)
    pop = pop[pop["性別"].isin(["計", "合計", "總計"])].copy()
    age_cols = [c for c in pop.columns if re.match(r"^\d+歲", c)]
    for c in age_cols + ["總計"]:
        pop[c] = pd.to_numeric(pop[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    g = pop.groupby("區域別")[age_cols + ["總計"]].sum()
    age_of = {c: int(re.match(r"^(\d+)", c).group(1)) for c in age_cols}
    c014 = [c for c in age_cols if age_of[c] <= 14]
    c65 = [c for c in age_cols if age_of[c] >= 65]
    ratio = pd.DataFrame({
        "children_ratio_pct": g[c014].sum(axis=1) / g["總計"] * 100,
        "elderly_ratio_pct": g[c65].sum(axis=1) / g["總計"] * 100,
        "pop_total_2023_01": g["總計"],
    })
    den = read_csv_any(DATA / "population_density_by_district_tsis.csv", dtype=str)
    per = latest_period(den)
    den = den[den["統計期"] == per].set_index("行政區別")
    alone = read_csv_any(DATA / "elderly_alone_by_district_tsis.csv", dtype=str)
    pa = latest_period(alone)
    alone = alone[(alone["統計期"] == pa) & (alone["性別"] == "總計")].set_index("行政區別")
    dis = read_csv_any(DATA / "disability_by_district_tsis.csv", dtype=str)
    pdz = latest_period(dis)
    dis = dis[(dis["統計期"] == pdz) & (dis["性別"] == "總計")].set_index("行政區別")
    rows = []
    for d in DISTRICTS:
        tot = _num(den.loc[d, "人口數/總計[人]"])
        area = _num(den.loc[d, "土地面積[平方公里]"])
        r_c = float(ratio.loc[d, "children_ratio_pct"])
        r_e = float(ratio.loc[d, "elderly_ratio_pct"])
        p65 = tot * r_e / 100
        p014 = tot * r_c / 100
        n_alone = _num(alone.loc[d, "獨居老人人數/總計"])
        n_dis = _num(dis.loc[d, "總計"])
        rows.append({
            "district": d, "pop_period": per, "pop_total": round(tot), "area_km2": area,
            "pop_density": round(tot / area, 1), "pop_65p": round(p65), "pop_0_14": round(p014),
            "children_ratio_pct": round(r_c, 2), "elderly_ratio_pct": round(r_e, 2),
            "age_structure_period": "112年1月(各里人口數按年齡分)",
            "pop_alone_elderly": round(n_alone), "alone_period": pa,
            "elderly_alone_ratio_pct": round(n_alone / p65 * 100, 3),      # 列冊獨居 / 65+（v0151 定義）
            "pop_disability": round(n_dis), "disability_period": pdz,
            "disability_pop_ratio_pct": round(n_dis / tot * 100, 2),
        })
    return pd.DataFrame(rows).set_index("district")


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(district_population_strata().T.to_string())


# ---------------------------------------------------------------- taipei_v2：里級人口分層（2026-10-26）
POP_VILLAGE_FILE = "pop_by_age_village_shilin_beitou_112-115.csv"   # data.taipei a6394e3f/c8f5b53d，里列，112/1–115/9
DISTRICT_CODE = {"63000110": "士林區", "63000120": "北投區"}


def village_population_strata(period=None):
    """93 里人口分層（供 v2 的 compose_evidence_village 與 compute_E_exposure_village 共用）。

    里級原生：總人口、0–14 歲、65 歲以上（民政局「各里人口數按年齡分」，單一期，預設取檔內最新一期）。
    區級複製：列冊獨居老人／65+ 比例、身心障礙／總人口 比例（主計處統計資料庫只到區）→ 乘上該里 65+ 或總人口得里級估計值。
    回傳 DataFrame，index=unit（區名＋里名）。
    """
    from taipei_paths import villages_gdf
    pop = read_csv_any(DATA / POP_VILLAGE_FILE, dtype=str)
    pop = pop[pop["性別"] == "計"].copy()
    pop["y"] = pop["年份"].astype(int)
    pop["m"] = pop["月份"].astype(int)
    if period is None:
        last = pop.sort_values(["y", "m"]).iloc[-1]
        period = (int(last["y"]), int(last["m"]))
    pop = pop[(pop["y"] == period[0]) & (pop["m"] == period[1])].copy()
    age_cols = [c for c in pop.columns if re.match(r"^\d+歲", c)]
    for c in age_cols + ["總計"]:
        pop[c] = pd.to_numeric(pop[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    age_of = {c: int(re.match(r"^(\d+)", c).group(1)) for c in age_cols}
    c014 = [c for c in age_cols if age_of[c] <= 14]
    c65 = [c for c in age_cols if age_of[c] >= 65]
    pop["district"] = pop["區域代碼"].astype(str).str[:8].map(DISTRICT_CODE)
    pop["village"] = pop["區域別"].astype(str).str.strip()
    pop["unit"] = pop["district"] + pop["village"]
    v = pop.set_index("unit")
    out = pd.DataFrame({
        "district": v["district"], "village": v["village"],
        "pop_total": v["總計"].round().astype(int),
        "pop_0_14": v[c014].sum(axis=1).round().astype(int),
        "pop_65p": v[c65].sum(axis=1).round().astype(int),
    })
    out["children_ratio_pct"] = (out["pop_0_14"] / out["pop_total"] * 100).round(2)
    out["elderly_ratio_pct"] = (out["pop_65p"] / out["pop_total"] * 100).round(2)
    out["pop_period"] = f"{period[0]}年{period[1]}月"
    # 區級複製：獨居老人、身障（主計處區級，最新期）
    alone = read_csv_any(DATA / "elderly_alone_by_district_tsis.csv", dtype=str)
    pa = latest_period(alone)
    alone = alone[(alone["統計期"] == pa) & (alone["性別"] == "總計")].set_index("行政區別")
    dis = read_csv_any(DATA / "disability_by_district_tsis.csv", dtype=str)
    pdz = latest_period(dis)
    dis = dis[(dis["統計期"] == pdz) & (dis["性別"] == "總計")].set_index("行政區別")
    d65 = out.groupby("district")["pop_65p"].sum()
    dtot = out.groupby("district")["pop_total"].sum()
    for d in DISTRICTS:
        n_alone = _num(alone.loc[d, "獨居老人人數/總計"])
        n_dis = _num(dis.loc[d, "總計"])
        m = out["district"] == d
        out.loc[m, "district_elderly_alone_ratio_pct"] = round(n_alone / d65[d] * 100, 3)   # 列冊獨居 / 65+
        out.loc[m, "district_disability_pop_ratio_pct"] = round(n_dis / dtot[d] * 100, 3)  # 身障 / 總人口
        out.loc[m, "alone_period"] = pa
        out.loc[m, "disability_period"] = pdz
    out["elderly_alone_ratio_pct"] = out["district_elderly_alone_ratio_pct"]          # 區級複製（里內同值）
    out["disability_pop_ratio_pct"] = out["district_disability_pop_ratio_pct"]        # 區級複製（里內同值）
    out["pop_alone_elderly"] = (out["pop_65p"] * out["elderly_alone_ratio_pct"] / 100).round(1)
    out["pop_disability"] = (out["pop_total"] * out["disability_pop_ratio_pct"] / 100).round(1)
    g = villages_gdf().set_index("unit")
    out["area_km2"] = g.loc[out.index, "area_km2"].round(4)
    out["pop_density"] = (out["pop_total"] / out["area_km2"]).round(1)
    cols = ["district", "village", "pop_period", "pop_total", "area_km2", "pop_density", "pop_65p", "pop_0_14",
            "children_ratio_pct", "elderly_ratio_pct", "elderly_alone_ratio_pct", "pop_alone_elderly", "alone_period",
            "disability_pop_ratio_pct", "pop_disability", "disability_period"]
    return out[cols].sort_values(["district", "village"])
