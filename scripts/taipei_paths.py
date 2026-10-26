# -*- coding: utf-8 -*-
"""共用路徑與讀檔小工具（臺北移植版）。所有輸入都放在 repo 內 data/taipei/。"""
import io, os, zipfile, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "taipei"
REF = ROOT / "bn_engine" / "reference_tainan"      # 臺南 v0.22.0 參考表（切點來源）
OUT = ROOT / "bn_engine" / "results" / "taipei_v1"
CPT = ROOT / "bn_engine" / "cpt_priors"
TMP = ROOT / "data" / "_unzipped"
DISTRICTS = ["士林區", "北投區"]
OUT.mkdir(parents=True, exist_ok=True)


def unzip_dir(zip_name):
    """解壓 data/taipei/<zip> 到 data/_unzipped/<stem>/，回傳資料夾路徑（已存在則略過）。"""
    d = TMP / Path(zip_name).stem
    if not d.exists():
        d.mkdir(parents=True)
        with zipfile.ZipFile(DATA / zip_name) as z:
            for i in z.infolist():
                n = i.filename
                if not (i.flag_bits & 0x800):
                    for enc in ("big5", "cp950"):
                        try:
                            n = n.encode("cp437").decode(enc); break
                        except Exception:
                            pass
                if i.is_dir():
                    continue
                with z.open(i) as s, open(d / Path(n).name, "wb") as t:
                    t.write(s.read())
    return d


def districts_gdf():
    """士林、北投區界（由民政局里界圖 dissolve），EPSG:3826。"""
    import geopandas as gpd
    d = unzip_dir("taipei_village_boundary_shp.zip")
    v = gpd.read_file(glob.glob(str(d / "*.shp"))[0], encoding="utf-8")
    v = v[v["TNAME"].isin(DISTRICTS)].to_crs(3826)
    g = v.dissolve(by="TNAME").reset_index()[["TNAME", "geometry"]].rename(columns={"TNAME": "district"})
    return g


def read_csv_any(path, **kw):
    import pandas as pd
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "big5", "cp950"):
        try:
            return pd.read_csv(io.StringIO(raw.decode(enc)), **kw)
        except Exception:
            continue
    raise ValueError(path)


# ---------------------------------------------------------------- taipei_v2：里級（2026-10-26）
OUT_V2 = ROOT / "bn_engine" / "results" / "taipei_v2_village"
OUT_V2.mkdir(parents=True, exist_ok=True)


def villages_gdf():
    """士林、北投 93 里（民政局里界圖 456 里中篩出），EPSG:3826。
    unit = 區名＋里名（例：士林區福安里），是 v2 所有里級表、evidence JSON、H2 錨定表的鍵。"""
    import geopandas as gpd
    d = unzip_dir("taipei_village_boundary_shp.zip")
    v = gpd.read_file(glob.glob(str(d / "*.shp"))[0], encoding="utf-8")
    v = v[v["TNAME"].isin(DISTRICTS)].to_crs(3826)
    g = v[["TNAME", "VNAME", "geometry"]].rename(columns={"TNAME": "district", "VNAME": "village"}).copy()
    g["unit"] = g["district"] + g["village"]
    g["area_km2"] = g.geometry.area / 1e6
    return g.sort_values(["district", "village"]).reset_index(drop=True)
