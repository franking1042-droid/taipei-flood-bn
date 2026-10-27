#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_bstp_map.py — 北投士林科技園區（地政局區段徵收範圍）與有交集的里：示意地圖

資料：
- data/taipei/taipei_zone_expropriation_ZEPN.zip：地政局開發總隊「臺北市區段徵收區」（data.taipei 1ab43adf，2026-04-07 版）。
  ZEPN.shp＝20 個區段徵收區外框（北投士林科技園區 ID 018，104.99 ha）；ZEPN_1.shp＝北士科 67 個街廓（T1–T18、R1–R32 等）。
- 民政局里界（taipei_paths.villages_gdf）、國土利用現況調查 112 年（底圖）、水綠地圖集河川與堤防、河川區域線、抽水站點位。
- 里級結果：results_village_v2.csv、shp_baseline_village_v2.csv、village_base_indicators_v2.csv。
輸出（bn_engine/results/taipei_v2_village/）：
  map_bstp_villages_v2.png                   示意地圖（園區紅框＋街廓，有交集的里半透明上色並標示占比）
  bstp_villages_v2.csv                       有交集的里：交集面積、里面積占比、園區面積占比、人口、潛勢、里級結果
  bstp_boundary_and_villages_v2.geojson      園區外框、街廓、有交集的里（WGS84，給 GIS）
"""
import glob
import io
import sys

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import pyogrio
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box

from taipei_paths import DATA, DISTRICTS, OUT_V2, read_csv_any, unzip_dir, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
matplotlib.rcParams["font.family"] = ["Microsoft JhengHei", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
H1 = "超大豪雨"
PAD = 900  # 地圖範圍＝園區外框外擴 m
LULC_COLOR = {"01": "#eef3d8", "02": "#d9ead3", "03": "#f4f4f4", "04": "#dbe9f6", "05": "#d6d6d6",
              "06": "#e9e2f0", "07": "#e2f0d9", "08": "#f0e6d2", "09": "#f7f7f7"}
VIL_COLORS = ["#f4a582", "#92c5de", "#fdd49e", "#b2df8a", "#cab2d6", "#fb9a99", "#a6cee3", "#ffe680",
              "#b3de69", "#fccde5", "#bc80bd", "#ccebc5", "#ffed6f", "#8dd3c7", "#fdb462", "#80b1d3"]


def load_bstp():
    d = unzip_dir("taipei_zone_expropriation_ZEPN.zip")
    z = pyogrio.read_dataframe(str(d / "ZEPN.shp"), encoding="utf-8")
    z = z.set_crs(3826, allow_override=True) if z.crs is None else z.to_crs(3826)
    row = z[z["開發案"] == "北投士林科技園區"]
    bstp = row.geometry.union_all()
    blocks = pyogrio.read_dataframe(str(d / "ZEPN_1.shp"), encoding="utf-8")
    blocks = blocks.set_crs(3826, allow_override=True) if blocks.crs is None else blocks.to_crs(3826)
    blocks = blocks[blocks["開發案"] == "北投士林科技園區"].copy()
    return bstp, row, blocks


def main():
    bstp, bstp_row, blocks = load_bstp()
    area_ha = bstp.area / 1e4
    vil = villages_gdf()
    vil["geometry"] = vil.geometry.make_valid()
    inter = vil[vil.intersects(bstp)].copy()
    inter["overlap_ha"] = inter.geometry.intersection(bstp).area / 1e4
    inter = inter[inter.overlap_ha > 0.01].copy()                       # 剔除邊界切割的極小碎片
    inter["pct_of_village_in_bstp"] = (inter.overlap_ha / (inter.area_km2 * 100) * 100).round(1)
    inter["pct_of_bstp_in_village"] = (inter.overlap_ha / area_ha * 100).round(1)
    inter["overlap_ha"] = inter["overlap_ha"].round(2)
    res = pd.read_csv(OUT_V2 / "results_village_v2.csv", encoding="utf-8-sig").set_index("unit")
    base = pd.read_csv(OUT_V2 / "village_base_indicators_v2.csv", encoding="utf-8-sig").set_index("unit")
    shp = pd.read_csv(OUT_V2 / "shp_baseline_village_v2.csv", encoding="utf-8-sig")
    fl500 = shp[shp.scenario == "24h500"].set_index("unit")["flooded_area_pct"]
    inter = inter.set_index("unit")
    inter["pop_total"] = base.loc[inter.index, "pop_total"]
    inter["Impervious_pct"] = base.loc[inter.index, "Impervious_pct"]
    inter["pump_capacity_cms_eff"] = base.loc[inter.index, "pump_capacity_cms_eff"]
    inter["flooded_area_pct_24h500"] = fl500.loc[inter.index].round(2)
    for c in [f"P_OFP_ge_FD2|{H1}", f"FloodDuration_EV|{H1}", f"R1_EV|{H1}", f"R2_EV|{H1}", f"R3_EV|{H1}", f"O_EV|{H1}"]:
        inter[c] = res.loc[inter.index, c]
    inter = inter.sort_values("overlap_ha", ascending=False).reset_index()
    cols = ["unit", "district", "village", "overlap_ha", "pct_of_village_in_bstp", "pct_of_bstp_in_village", "area_km2", "pop_total",
            "Impervious_pct", "pump_capacity_cms_eff", "flooded_area_pct_24h500", f"P_OFP_ge_FD2|{H1}", f"FloodDuration_EV|{H1}",
            f"R1_EV|{H1}", f"R2_EV|{H1}", f"R3_EV|{H1}", f"O_EV|{H1}"]
    inter[cols].to_csv(OUT_V2 / "bstp_villages_v2.csv", index=False, encoding="utf-8-sig")
    print(f"北投士林科技園區 區段徵收範圍 {area_ha:.2f} ha；有交集的里 {len(inter)}（面積占比總和 {inter.pct_of_bstp_in_village.sum():.1f}%）")
    print(inter[cols[:8] + [f"O_EV|{H1}"]].to_string(index=False))

    # ---- GeoJSON（WGS84）----
    g_b = gpd.GeoDataFrame({"layer": ["bstp_boundary"], "name": ["北投士林科技園區區段徵收範圍"], "area_ha": [round(area_ha, 2)]},
                           geometry=[bstp], crs=3826)
    g_k = gpd.GeoDataFrame({"layer": "bstp_block", "name": blocks["街廓碼"].fillna("")}, geometry=blocks.geometry.values, crs=3826)
    g_v = gpd.GeoDataFrame(inter[cols].assign(layer="village", name=inter["unit"]), geometry=inter.geometry.values, crs=3826)
    pd.concat([g_b, g_k, g_v], ignore_index=True).to_crs(4326).to_file(OUT_V2 / "bstp_boundary_and_villages_v2.geojson", driver="GeoJSON")

    # ---- 地圖 ----
    minx, miny, maxx, maxy = bstp.bounds
    ext = box(minx - PAD, miny - PAD, maxx + PAD, maxy + PAD)
    lulc_dir = unzip_dir("lulc_2023_shilin_beitou_shp.zip")
    lulc = gpd.read_file(glob.glob(str(lulc_dir / "*.shp"))[0], encoding="utf-8", bbox=ext.bounds).to_crs(3826)
    lulc["c1"] = lulc["LCODE_C1"].astype(str).str.zfill(2)
    rivers = gpd.read_file(DATA / "taipei_rivers_watergreen.geojson").to_crs(3826)
    levees = gpd.read_file(DATA / "taipei_levees_watergreen.geojson").to_crs(3826)
    rlines = gpd.read_file(DATA / "taipei_river_zone_lines.kml", driver="KML").to_crs(3826)
    pumps = read_csv_any(DATA / "pump_stations_shilin_beitou.csv")
    pumps = gpd.GeoDataFrame(pumps, geometry=gpd.points_from_xy(pumps["X_TWD97"].astype(float), pumps["Y_TWD97"].astype(float)), crs=3826)
    pumps = pumps[pumps.within(ext) & (pumps["站別"] == "正式站")]

    fig, ax = plt.subplots(figsize=(15, 12))
    for c1, col in LULC_COLOR.items():
        sub = lulc[lulc.c1 == c1]
        if len(sub):
            sub.plot(ax=ax, color=col, edgecolor="none", zorder=1)
    rivers.plot(ax=ax, color="#bcd8ef", edgecolor="none", zorder=2)
    rlines.plot(ax=ax, color="#5b9bd5", linewidth=1.0, zorder=3)
    levees.plot(ax=ax, color="#444444", linewidth=1.3, linestyle="--", zorder=4)
    vil.plot(ax=ax, facecolor="none", edgecolor="#8c8c8c", linewidth=0.8, zorder=5)
    for i, (_, r) in enumerate(inter.iterrows()):
        col = VIL_COLORS[i % len(VIL_COLORS)]
        gpd.GeoSeries([r.geometry], crs=3826).plot(ax=ax, facecolor=col, edgecolor="#333333", linewidth=1.4, alpha=0.38, zorder=6)
        lab = r.geometry.intersection(ext).difference(bstp.buffer(60))
        pt = (lab if not lab.is_empty else r.geometry.intersection(ext)).representative_point()
        ax.annotate(f"{r.village}\n{r.pct_of_village_in_bstp:.0f}% 在園區內", (pt.x, pt.y), ha="center", va="center", fontsize=10,
                    color="#111111", zorder=12, bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75))
    blocks.plot(ax=ax, facecolor="none", edgecolor="#c00000", linewidth=0.6, alpha=0.9, zorder=8)
    for _, b in blocks[blocks["街廓碼"].notna()].iterrows():
        c = b.geometry.centroid
        ax.text(c.x, c.y, b["街廓碼"], fontsize=6.5, color="#8b0000", ha="center", va="center", zorder=9)
    gpd.GeoSeries([bstp], crs=3826).plot(ax=ax, facecolor="#ff0000", edgecolor="#c00000", linewidth=3.0, alpha=0.07, zorder=7)
    gpd.GeoSeries([bstp.boundary], crs=3826).plot(ax=ax, color="#c00000", linewidth=3.0, zorder=10)
    pumps.plot(ax=ax, marker="^", color="black", markersize=70, zorder=11)
    for _, p in pumps.iterrows():
        ax.annotate(f"{p['抽水站名稱']}抽水站", (p.geometry.x, p.geometry.y), xytext=(6, 6), textcoords="offset points", fontsize=9, zorder=12)
    ax.set_xlim(ext.bounds[0], ext.bounds[2])
    ax.set_ylim(ext.bounds[1], ext.bounds[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    # 比例尺、指北
    x0, y0 = ext.bounds[0] + 150, ext.bounds[1] + 150
    ax.plot([x0, x0 + 500], [y0, y0], color="black", linewidth=3, zorder=13)
    ax.text(x0 + 250, y0 + 40, "500 m", ha="center", fontsize=9, zorder=13)
    ax.annotate("N", (ext.bounds[2] - 180, ext.bounds[3] - 130), ha="center", fontsize=13, fontweight="bold", zorder=13)
    ax.annotate("", (ext.bounds[2] - 180, ext.bounds[3] - 150), (ext.bounds[2] - 180, ext.bounds[3] - 420),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=2), zorder=13)
    handles = [Patch(facecolor="#ff0000", edgecolor="#c00000", alpha=0.25, linewidth=2, label=f"北投士林科技園區 區段徵收範圍（{area_ha:.1f} ha）"),
               Line2D([0], [0], color="#c00000", linewidth=0.8, label="園區街廓（T／R 編號）"),
               Patch(facecolor="#92c5de", edgecolor="#333333", alpha=0.5, label=f"與園區有交集的里（{len(inter)} 里，半透明）"),
               Line2D([0], [0], color="#8c8c8c", linewidth=0.8, label="其他里界"),
               Line2D([0], [0], color="#444444", linewidth=1.3, linestyle="--", label="堤防"),
               Line2D([0], [0], color="#5b9bd5", linewidth=1.0, label="河川區域線"),
               Line2D([0], [0], marker="^", color="black", linestyle="none", markersize=8, label="雨水抽水站（正式站）"),
               Patch(facecolor="#d6d6d6", label="建築用地（土地利用現況 112 年）"),
               Patch(facecolor="#eef3d8", label="農業用地"), Patch(facecolor="#dbe9f6", label="水利用地")]
    ax.legend(handles=handles, loc="lower right", fontsize=9, framealpha=0.92)
    ax.set_title("北投士林科技園區（地政局區段徵收範圍）與有交集的里 — 示意圖", fontsize=15, pad=12)
    fig.text(0.5, 0.015, "資料：臺北市地政局開發總隊「臺北市區段徵收區」SHP（data.taipei，2026-04 版）、民政局里界圖、國土測繪中心國土利用現況調查 112 年、"
             "水利處水綠地圖集（河川、堤防）、河川區域線、抽水站設施概況 115 上半年。里內百分比＝該里面積落在園區內的比例。",
             ha="center", fontsize=8.5, color="#444444")
    # 小圖：在士林北投的位置
    ins = fig.add_axes([0.065, 0.66, 0.2, 0.26])
    vil.plot(ax=ins, facecolor="#f2f2f2", edgecolor="#bbbbbb", linewidth=0.3)
    gpd.GeoSeries([bstp], crs=3826).plot(ax=ins, facecolor="#ff0000", edgecolor="#c00000", alpha=0.6)
    gpd.GeoSeries([ext.boundary], crs=3826).plot(ax=ins, color="#c00000", linewidth=0.8)
    ins.set_title("位置（士林、北投 93 里）", fontsize=8)
    ins.set_xticks([])
    ins.set_yticks([])
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = OUT_V2 / "map_bstp_villages_v2.png"
    fig.savefig(out, dpi=160)
    print("saved", out.name, "bstp_villages_v2.csv", "bstp_boundary_and_villages_v2.geojson")


if __name__ == "__main__":
    main()
