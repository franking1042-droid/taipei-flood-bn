#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_village_maps.py — taipei_v2 D：里級結果地圖、GeoJSON 與北士科周邊里清單

- map_village_v2_超大豪雨.png：六格（24h500 淹水面積%、P(OFP≥FD2)、R1、R2、R3、O_total 期望值），疊北士科示意中心
  （121.507°E、25.105°N，與 10/22 簡報同）1.5 km 圓。
- results_village_v2.geojson：里界 × results_village_v2.csv × E 24h500 暴露，給 GIS 用。
- bstp_neighbourhood_villages_v2.csv：與 1.5 km 圓相交的里（面積占比、各項結果），即「北士科＋洲美」要看的里集合。
"""
import io
import sys

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import Point

from taipei_paths import OUT_V2, villages_gdf

if getattr(sys.stdout, "encoding", "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
matplotlib.rcParams["font.family"] = ["Microsoft JhengHei", "Noto Sans CJK TC", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
BSTP_LONLAT = (121.507, 25.105)
RADIUS_M = 1500
H1 = "超大豪雨"


def main():
    vil = villages_gdf()
    res = pd.read_csv(OUT_V2 / "results_village_v2.csv", encoding="utf-8-sig")
    shp = pd.read_csv(OUT_V2 / "shp_baseline_village_v2.csv", encoding="utf-8-sig")
    e = pd.read_csv(OUT_V2 / "E_stratified_exposure_village_v2.csv", encoding="utf-8-sig")
    fl500 = shp[shp.scenario == "24h500"].set_index("unit")["flooded_area_pct"].rename("flooded_area_pct_24h500")
    fl350 = shp[shp.scenario == "24h350"].set_index("unit")["flooded_area_pct"].rename("flooded_area_pct_24h350")
    e500 = e[e.scenario == "24h500"].set_index("unit")[["flooded_building_area_pct", "E_pop_total", "E_pop_65p"]].add_suffix("_24h500")
    g = vil.merge(res, on=["unit", "district", "village"]).set_index("unit").join(fl500).join(fl350).join(e500).reset_index()
    g.to_crs(4326).to_file(OUT_V2 / "results_village_v2.geojson", driver="GeoJSON")

    centre = gpd.GeoSeries([Point(*BSTP_LONLAT)], crs=4326).to_crs(3826).iloc[0]
    circle = centre.buffer(RADIUS_M)
    g["bstp_share_pct"] = (g.geometry.intersection(circle).area / g.geometry.area * 100).round(1)
    g["dist_to_bstp_centre_m"] = g.geometry.distance(centre).round(0)
    nb = g[g.bstp_share_pct > 0].sort_values("dist_to_bstp_centre_m")
    cols = ["unit", "district", "village", "dist_to_bstp_centre_m", "bstp_share_pct", "area_km2", "flooded_area_pct_24h350", "flooded_area_pct_24h500",
            "flooded_building_area_pct_24h500", "E_pop_total_24h500", f"P_OFP_ge_FD2|{H1}", f"FloodDuration_EV|{H1}",
            f"R1_EV|{H1}", f"R2_EV|{H1}", f"R3_EV|{H1}", f"O_EV|{H1}"]
    nb[cols].to_csv(OUT_V2 / "bstp_neighbourhood_villages_v2.csv", index=False, encoding="utf-8-sig")
    print("北士科 1.5 km 圓相交的里：", len(nb))
    print(nb[cols].round(3).to_string(index=False))

    panels = [("flooded_area_pct_24h500", "24h500 淹水潛勢面積 %", "Blues"),
              (f"P_OFP_ge_FD2|{H1}", f"P(原淹水潛勢 ≥ 0.3 m | {H1})", "Blues"),
              (f"R1_EV|{H1}", f"R1 經濟損失 期望等級 0–3 | {H1}", "Oranges"),
              (f"R2_EV|{H1}", f"R2 維生系統 期望等級 0–3 | {H1}", "Oranges"),
              (f"R3_EV|{H1}", f"R3 弱勢族群 期望等級 0–3 | {H1}", "Oranges"),
              (f"O_EV|{H1}", f"O 綜合總風險 期望等級 0–4 | {H1}", "Reds")]
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    for ax, (col, title, cmap) in zip(axes.flat, panels):
        g.plot(column=col, cmap=cmap, legend=True, ax=ax, edgecolor="#777", linewidth=0.3,
               legend_kwds={"shrink": 0.6})
        gpd.GeoSeries([circle.exterior], crs=3826).plot(ax=ax, color="red", linewidth=1.5)
        ax.plot(centre.x, centre.y, "r+", markersize=12)
        ax.set_title(title, fontsize=12)
        ax.set_axis_off()
    fig.suptitle("臺北市士林、北投 93 里 — 臺南 BN v0.22.0 直接移植（taipei_v2_village）；紅圈＝北士科示意中心 1.5 km", fontsize=14)
    fig.tight_layout()
    out_png = OUT_V2 / f"map_village_v2_{H1}.png"
    fig.savefig(out_png, dpi=130)
    print("saved", out_png.name, "results_village_v2.geojson", "bstp_neighbourhood_villages_v2.csv")


if __name__ == "__main__":
    main()
