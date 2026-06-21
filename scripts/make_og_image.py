"""
make_og_image.py — 產生社群分享用的 Open Graph 圖（1200×630）。

這是「靜態品牌圖」，與當日資料無關，因此只需在本機跑一次，產出
og.png（中文）與 og-en.png（英文）後 commit 即可。
刻意不放進 build_site.py / 每日 GitHub Actions，避免 CI 缺 CJK 字型而失敗。

用法：python scripts/make_og_image.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent

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


def draw_shield(d, cx, top, h, outline, width=6):
    """Stylized shield polygon (decorative watermark)."""
    w = h * 0.86
    pts = [
        (cx - w / 2, top),
        (cx + w / 2, top),
        (cx + w / 2, top + h * 0.52),
        (cx, top + h),
        (cx - w / 2, top + h * 0.52),
    ]
    d.polygon(pts, outline=outline, width=width)


# 底部裝飾用的固定長條剪影（非真實資料，純品牌視覺）
BARS = [4, 9, 23, 11, 4, 20, 9, 34, 26, 9, 5, 2, 13, 42, 11, 3,
        14, 8, 2, 30, 8, 36, 12, 6, 16, 19, 11, 25, 22, 15, 29, 32]


def render(out_name, lang):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)

    # 邊框
    d.rectangle([0, 0, W - 1, H - 1], outline=BDR, width=2)

    # 右側大型盾牌浮水印（低對比）
    draw_shield(d, cx=1055, top=120, h=300, outline=(30, 46, 54), width=10)
    draw_emblem(d, 1055, 250, 46, ring=(40, 58, 50), width=7)

    # 底部長條剪影（資料感）
    base_y = H - 70
    bw, gap = 22, 12
    total = len(BARS) * (bw + gap)
    bx = (W - total) // 2
    for hgt in BARS:
        bh = int(hgt * 3.0)
        d.rectangle([bx, base_y - bh, bx + bw, base_y], fill=(20, 28, 30))
        bx += bw + gap

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
