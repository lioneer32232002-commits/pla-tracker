# -*- coding: utf-8 -*-
"""共軍侵擾示意圖卡原型：真實海岸線 + 依數量生成的扁平圖示。"""
import json, math, random, sys
from PIL import Image, ImageDraw, ImageFont

GEO = r"D:\repos\pla-tracker\data\geo_card.json"
W, H = 1080, 1920
LON0, LON1 = 115.6, 122.3
LAT0, LAT1 = 21.6, 27.40
MW = 1240
MX0 = (W - MW) / 2
MH = MW * ((LAT1 - LAT0) / ((LON1 - LON0) * math.cos(math.radians(24.6))))
MY0 = 395
MARGIN = 46
LON_VIS_LO = LON0 + (MARGIN - MX0) * (LON1 - LON0) / MW
LON_VIS_HI = LON0 + (W - MARGIN - MX0) * (LON1 - LON0) / MW

BG = (11, 16, 19)
SEA = (17, 27, 33)
CN_FILL = (48, 27, 30)
CN_LINE = (104, 52, 56)
TW_FILL = (206, 214, 206)
TW_LINE = (240, 246, 240)
AIR = (232, 236, 238)
AIR_X = (255, 61, 0)
SHIP = (150, 200, 210)
YEL = (255, 235, 59)
RING = (255, 61, 0)

FB = r"C:\Windows\Fonts\msjhbd.ttc"
FR = r"C:\Windows\Fonts\msjh.ttc"


def proj(lon, lat):
    x = (lon - LON0) / (LON1 - LON0) * MW + MX0
    y = (LAT1 - lat) / (LAT1 - LAT0) * MH + MY0
    return x, y


def median_lon(lat):
    """戴維斯線：北緯 27 度／東經 122 度 到 北緯 23 度／東經 118 度。"""
    return 118.0 + (lat - 23.0)


def edge_fn(rings, lat_lo, lat_hi, step, pick):
    """把多邊形依緯度切片，取每一片的極值經度，做出海岸線函數。"""
    bins = {}
    for ring in rings:
        for lon, lat in ring:
            k = round(lat / step)
            bins.setdefault(k, []).append(lon)
    keys = sorted(bins)
    table = [(k * step, pick(bins[k])) for k in keys]

    def f(lat):
        if lat <= table[0][0]:
            return table[0][1]
        if lat >= table[-1][0]:
            return table[-1][1]
        for i in range(len(table) - 1):
            a, b = table[i], table[i + 1]
            if a[0] <= lat <= b[0]:
                t = (lat - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
                return a[1] + t * (b[1] - a[1])
        return table[-1][1]

    return f


def poly(d, rings, fill, line, wid=2):
    for ring in rings:
        pts = [proj(lon, lat) for lon, lat in ring]
        if len(pts) > 2:
            d.polygon(pts, fill=fill, outline=line)
            d.line(pts + [pts[0]], fill=line, width=wid)


def mirror(half):
    return half + [(x, -y) for x, y in reversed(half[:-1])]


PLANE = mirror([(1.00, 0.00), (0.25, 0.12), (-0.25, 0.85), (-0.55, 0.85),
                (-0.35, 0.12), (-0.85, 0.12), (-1.00, 0.45), (-1.15, 0.45),
                (-1.05, 0.00)])
DRONE = mirror([(1.00, 0.00), (0.30, 0.09), (0.05, 1.00), (-0.20, 1.00),
                (-0.15, 0.09), (-0.95, 0.09), (-1.05, 0.38), (-1.20, 0.38),
                (-1.10, 0.00)])
BOAT = mirror([(1.00, 0.00), (0.30, 0.30), (-0.80, 0.30), (-1.00, 0.10),
               (-1.00, 0.00)])


def icon(d, shape, x, y, s, color):
    d.polygon([(x + px * s, y - py * s) for px, py in shape], fill=color)


def dashed(d, p0, p1, color, wid, dash=18, gap=14):
    x0, y0 = p0
    x1, y1 = p1
    total = math.hypot(x1 - x0, y1 - y0)
    n = int(total // (dash + gap))
    for i in range(n + 1):
        a = i * (dash + gap) / total
        b = min(1.0, (i * (dash + gap) + dash) / total)
        d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=color, width=wid)


def build(date_label, air, cross, ships, kind, insight, out):
    geo = json.load(open(GEO, encoding="utf-8"))
    cn_edge = edge_fn(geo["cn"], LAT0, LAT1, 0.25, max)
    tw_w = edge_fn(geo["tw"], LAT0, LAT1, 0.25, min)
    tw_e = edge_fn(geo["tw"], LAT0, LAT1, 0.25, max)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, MY0 - 60, W, MY0 + MH + 60], fill=SEA)

    poly(d, geo["cn"], CN_FILL, CN_LINE, 2)
    poly(d, geo["tw"], TW_FILL, TW_LINE, 2)

    dashed(d, proj(122.0, 27.0), proj(118.0, 23.0), (150, 170, 180), 3)

    # 侵擾區域：同心等高線，中心放在西南空域
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    cx, cy = proj(119.9, 22.6)
    for i in range(6):
        r = 60 + i * 62
        a = int(120 * (1 - i / 6.0))
        od.ellipse([cx - r * 1.25, cy - r, cx + r * 1.25, cy + r],
                   outline=RING + (a,), width=3)
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)

    rnd = random.Random(date_label)
    shape = DRONE if kind == "UAV" else PLANE
    size = max(13, min(30, int(150 / max(4, air) ** 0.55) + 10))

    placed = []

    def ok(x, y, gap):
        return all((x - a) ** 2 + (y - b) ** 2 > gap ** 2 for a, b in placed)

    def put(lat_lo, lat_hi, lon_fn, n, color, shp, s):
        got = 0
        tries = 0
        while got < n and tries < n * 500:
            tries += 1
            lat = rnd.uniform(lat_lo, lat_hi)
            lo, hi = lon_fn(lat)
            # 夾在畫布可見範圍內，圖示不能被邊緣切掉，否則數量對不上
            lo = max(lo, LON_VIS_LO)
            hi = min(hi, LON_VIS_HI)
            if hi - lo < 0.05:
                continue
            lon = rnd.uniform(lo, hi)
            x, y = proj(lon, lat)
            if not ok(x, y, s * 1.9):
                continue
            placed.append((x, y))
            icon(d, shp, x, y, s, color)
            got += 1
        return got

    put(23.0, 25.6, lambda la: (median_lon(la) + 0.12, tw_w(la) - 0.18),
        cross, AIR_X, shape, size)
    put(21.9, 26.8, lambda la: (cn_edge(la) + 0.18, median_lon(la) - 0.15),
        air - cross, AIR, shape, size)

    def sea_lon(la):
        if la < 22.3 or la > 25.4:
            return (median_lon(la) + 0.1, 122.1)
        return (tw_e(la) + 0.25, 122.15)

    put(21.9, 26.4, sea_lon, ships, SHIP, BOAT, int(size * 0.95))

    f_big = ImageFont.truetype(FB, 108)
    f_date = ImageFont.truetype(FR, 58)
    f_num = ImageFont.truetype(FB, 62)
    f_foot = ImageFont.truetype(FR, 40)
    f_mark = ImageFont.truetype(FR, 36)

    def ctr(txt, y, font, fill):
        w = d.textbbox((0, 0), txt, font=font)[2]
        d.text(((W - w) / 2, y), txt, font=font, fill=fill)

    ctr("中國侵擾台灣", 78, f_big, YEL)
    ctr(date_label, 212, f_date, (255, 255, 255))
    ctr(f"偵獲共機 {air} 架次", 286, f_num, (255, 255, 255))

    y = 1560
    ctr(f"逾越中線 {cross} 架次", y, f_num, AIR_X)
    ctr(f"共艦＋公務船 {ships} 艘", y + 84, f_num, (255, 255, 255))
    ctr(insight, y + 190, f_foot, (168, 178, 184))
    ctr("skyfaringyt", H - 96, f_mark, (120, 130, 136))

    img.save(out)
    print(out, "->", air, cross, ships)


if __name__ == "__main__":
    build("2026.8.1-2", 5, 3, 10, "Manned",
          "逾越中線比例 60%，為近 30 日最高",
          r"C:\Users\User\AppData\Local\Temp\claude\D--repos-skyfaring\e333c895-fb2e-4e6c-8602-5afe3c1fc516\scratchpad\map_card_light.png")
    build("2026.2.12-13", 42, 32, 11, "Manned",
          "單日 42 架次，為近 30 日最高",
          r"C:\Users\User\AppData\Local\Temp\claude\D--repos-skyfaring\e333c895-fb2e-4e6c-8602-5afe3c1fc516\scratchpad\map_card_busy.png")
