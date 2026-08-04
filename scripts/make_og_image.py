"""
make_og_image.py — 產生社群分享用的 Open Graph 圖（1200×630）。

這是「靜態品牌圖」，與當日資料無關，因此只需在本機跑一次，產出
og.png（中文）與 og-en.png（英文）後 commit 即可。
刻意不放進 build_site.py / 每日 GitHub Actions，避免 CI 缺 CJK 字型而失敗。

用法：python scripts/make_og_image.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).parent.parent
# 背景照片（愛國者飛彈發射車，Unsplash 授權，作者 Gabriel Vasiliu）。
# 原檔 6000×4000 已縮到 2400 寬存進 repo，讓這支腳本可重跑。
PHOTO = ROOT / 'assets' / 'og-source.jpg'

W, H = 1200, 630
BG   = (9, 13, 15)
SUR  = (14, 22, 24)
BDR  = (26, 40, 48)
Y    = (245, 200, 66)
Y_DK = (138, 112, 32)
R    = (224, 85, 85)
TX   = (224, 232, 236)
SUB  = (138, 159, 170)

# 字型候選（找不到就往後退）
JH_BD  = ['C:/Windows/Fonts/msjhbd.ttc']
JH     = ['C:/Windows/Fonts/msjh.ttc']
LAT_BD = ['C:/Windows/Fonts/segoeuib.ttf', 'C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/msjhbd.ttc']
LAT    = ['C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/msjh.ttc']


def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tracked_text(d, xy, text, fnt, fill, spacing=0):
    """Draw text with extra letter-spacing (for uppercase labels)."""
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=fnt, fill=fill)
        x += d.textlength(ch, font=fnt) + spacing
    return x


def draw_emblem(d, cx, cy, r, ring=Y, width=5):
    """Crosshair: ring + plus, echoing favicon.svg."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring, width=width)
    d.line([cx, cy - r * 1.5, cx, cy + r * 1.5], fill=ring, width=width)
    d.line([cx - r * 1.5, cy, cx + r * 1.5, cy], fill=ring, width=width)


def _ramp(stops, horizontal=True):
    """由 (位置0~1, 不透明度0~255) 節點做出線性漸層遮罩，回傳 W×H 的 'L' 圖。"""
    n = W if horizontal else H
    g = Image.new('L', (n, 1) if horizontal else (1, n))
    px = g.load()
    for i in range(n):
        t = i / (n - 1)
        val = stops[-1][1]
        for (p0, a0), (p1, a1) in zip(stops, stops[1:]):
            if t <= p1:
                k = 0 if p1 == p0 else min(1, max(0, (t - p0) / (p1 - p0)))
                val = a0 + (a1 - a0) * k
                break
        if horizontal:
            px[i, 0] = int(val)
        else:
            px[0, i] = int(val)
    return g.resize((W, H), Image.BILINEAR)


def photo_bg():
    """照片底：cover 裁切 → 壓暗降彩 → 左側深色壓字條 + 上下暗角。"""
    src = Image.open(PHOTO).convert('RGB')
    sw, sh = src.size
    # cover：以寬度為準裁掉上下，取景偏上以保留發射架、切掉底部機場雜物
    ch = int(sw * H / W)
    top = int((sh - ch) * 0.34)
    img = src.crop((0, top, sw, top + ch)).resize((W, H), Image.LANCZOS)

    img = ImageEnhance.Color(img).enhance(0.66)       # 降彩度（天空太藍會蓋過品牌色）
    img = ImageEnhance.Brightness(img).enhance(0.86)  # 壓暗，但要留得住發射架輪廓
    img = ImageEnhance.Contrast(img).enhance(1.14)
    img = Image.blend(img, Image.new('RGB', (W, H), BG), 0.16)  # 往品牌深色調

    dark = Image.new('RGB', (W, H), BG)
    # 左半壓字條：文字區幾乎全暗，右側留照片
    img = Image.composite(dark, img, _ramp(
        [(0.0, 240), (0.44, 216), (0.64, 104), (0.82, 26), (1.0, 14)]))
    # 上下暗角（標籤列與網址列的可讀性）
    img = Image.composite(dark, img, _ramp(
        [(0.0, 150), (0.16, 26), (0.80, 26), (0.90, 140), (1.0, 190)],
        horizontal=False))
    return img


def render(out_name, lang):
    img = photo_bg()
    d = ImageDraw.Draw(img)

    # 邊框
    d.rectangle([0, 0, W - 1, H - 1], outline=BDR, width=2)

    base_y = H - 70
    margin = 80

    # 頂部分類標籤
    lbl = font(LAT_BD, 22)
    tracked_text(d, (margin, 70),
                 'UNCLASSIFIED  //  OPEN SOURCE  ·  TAIWAN STRAIT',
                 lbl, SUB, spacing=3)
    d.line([margin, 112, W - margin, 112], fill=BDR, width=1)

    # 標題區
    draw_emblem(d, margin + 22, 210, 22, ring=Y, width=6)

    if lang == 'en':
        title_f = font(LAT_BD, 72)
        sub_f   = font(LAT_BD, 38)
        tag_f   = font(LAT, 30)
        d.text((margin + 60, 188), 'PLA Activity Tracker', font=title_f, fill=TX)
        d.text((margin, 290), 'Taiwan Strait', font=sub_f, fill=Y)
        d.text((margin, 350),
               'Daily PLA sorties, median-line crossings',
               font=tag_f, fill=SUB)
        d.text((margin, 392),
               '& naval activity — sourced from ROC MND',
               font=tag_f, fill=SUB)
    else:
        title_f = font(JH_BD, 76)
        sub_f   = font(LAT_BD, 34)
        tag_f   = font(JH, 30)
        d.text((margin + 64, 178), '中國擾台趨勢數據分析', font=title_f, fill=TX)
        d.text((margin, 290), 'PLA Activity Around Taiwan', font=sub_f, fill=Y)
        d.text((margin, 348),
               '每日追蹤共機架次・逾越海峽中線・共艦動態',
               font=tag_f, fill=SUB)
        d.text((margin, 390),
               '資料來源：中華民國國防部',
               font=tag_f, fill=SUB)

    # 底部網址列
    d.line([margin, base_y + 18, W - margin, base_y + 18], fill=BDR, width=1)
    url_f = font(LAT_BD, 30)
    d.text((margin, base_y + 30), 'pla-tracker.pages.dev', font=url_f, fill=Y)
    cred_f = font(LAT, 24)
    cred = 'Source: ROC MND' if lang == 'en' else '資料來源：國防部'
    cred_f2 = font(JH, 24) if lang != 'en' else cred_f
    cw = d.textlength(cred, font=cred_f2)
    d.text((W - margin - cw, base_y + 34), cred, font=cred_f2, fill=SUB)

    img.save(ROOT / out_name)
    print(f'[OK] {out_name}')


if __name__ == '__main__':
    render('og.png', 'zh')
    render('og-en.png', 'en')
    print('[DONE] OG images')
