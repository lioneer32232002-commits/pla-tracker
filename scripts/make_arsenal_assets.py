"""
make_arsenal_assets.py — 一次性本機工具：從已下載的 DVIDS 公有領域原始照
（output/og_assets/raw/*.jpg，不進 git）裁切/縮圖成軍購儀表板用的圖片資產。

定位與 make_og_image.py 相同：本機執行一次、產出靜態檔後 commit，不進
build_site.py / 每日 CI（本機可用 Pillow，CI 不行）。

前置條件：output/og_assets/raw/ 下已備妥以下檔案（本次由人工查證 DVIDS
頁面 + curl 下載 2000w_q95.jpg 版本取得，來源與授權見下方 MANIFEST／
HERO_MANIFEST 的 page_url／photographer／note）：
    og_harpoon_f16.jpg（OG 主圖來源）
    stinger.jpg, m1a2.jpg, f16v.jpg, mk48.jpg, slamer.jpg, himars.jpg（舊縮圖來源，
        已被 hero_himars_src.jpg 取代，檔案保留但不再使用),
    mq9b.jpg, m109a6.jpg, harpoon_air.jpg, aim9x.jpg, volcano.jpg,
    mk75.jpg, m109a7.jpg, tow.jpg, javelin.jpg, altius700.jpg,
    hero_himars_src.jpg, hero_patriot_src.jpg, hero_harpoon_src.jpg（2026-07-24
        補：武器內頁橫幅＋重製縮圖用，來源見 HERO_MANIFEST）

輸出：
    assets/arsenal/og-arsenal.jpg          1200x630，品質85，目標 <250KB
    assets/arsenal/thumb-{key}.jpg         480x480，品質82，目標 <45KB
    assets/arsenal/hero-{key}.jpg          1600 寬 x 640~700 高（依項目），品質82，目標 <120KB
    assets/arsenal/credits.json            每檔的來源/攝影者/單位/型號備註

用法：python -X utf8 scripts/make_arsenal_assets.py
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent.parent
RAW = ROOT / 'output' / 'og_assets' / 'raw'
OUT = ROOT / 'assets' / 'arsenal'

OG_SIZE = (1200, 630)
THUMB_SIZE = (480, 480)
HERO_WIDTH = 1600
OG_MAX_KB = 250
THUMB_MAX_KB = 45
HERO_MAX_KB = 120


def save_with_budget(img, path, max_kb, start_quality):
    """存檔，若超過 KB 預算就逐步降品質重存，直到達標或降到品質 40 為止。"""
    quality = start_quality
    while True:
        img.save(path, 'JPEG', quality=quality, optimize=True)
        kb = path.stat().st_size / 1024
        if kb <= max_kb or quality <= 40:
            return kb, quality
        quality -= 5


def crop_square(im, box=None):
    """回傳正方形裁切後的圖（box=(left,top,right,bottom) 覆寫；否則置中裁切）。"""
    if box is not None:
        return im.crop(box)
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


# ---------------------------------------------------------------------------
# OG 主圖：8889192「魚叉掛載正面特寫」，原圖 5334x3632（下載版 2000x1362）。
# 構圖以座艙下方進氣口與右翼掛架為視覺中心，裁掉頂部大面積天空後
# 符合 1200x630（1.905:1）比例，不疊任何文字。
# ---------------------------------------------------------------------------
OG_SOURCE = 'og_harpoon_f16.jpg'
OG_CROP_BOX = (0, 312, 2000, 1362)  # 2000x1050，裁除頂部 312px 天空
OG_CREDIT = {
    'dvids_page_url': 'https://www.dvidshub.net/image/8889192/test-integrates-navy-missile-f-16',
    'photographer': 'Airman 1st Class Timothy Perish',
    'unit': '53rd Wing, Nellis Air Force Base, Nevada (U.S. Air Force)',
    'note': 'F-16 測試掛載美國海軍 Harpoon 飛彈系統之示意畫面（2025-02-27），'
            '非台灣專屬機種或塗裝，僅作魚叉飛彈+F-16平台的視覺代表。',
}

# ---------------------------------------------------------------------------
# 縮圖清單。crop_box=None 代表用置中正方形裁切（多數案例已目視核對足夠清楚）；
# 有 crop_box 的是人工核對原圖後認為需要偏移/放大裁切才能保住主體的案例。
# ---------------------------------------------------------------------------
MANIFEST = [
    dict(
        key='stinger', src='stinger.jpg',
        crop_box=(666, 0, 1999, 1333),  # 1333x1333，偏右裁切保留發射士兵與煙霧
        page_url='https://www.dvidshub.net/image/9210690/marines-launch-stinger-missile-target-aircraft-during-live-fire-exercise-twentynine-palms',
        photographer='Lance Cpl. Manuel Valdez',
        unit='3rd Low Altitude Air Defense Battalion, U.S. Marine Corps',
        note='',
    ),
    dict(
        key='m1a2', src='m1a2.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/6745913/m1a2-abrams-live-fire',
        photographer='Staff Sgt. Austin Berner',
        unit='3rd Squadron, 16th Cavalry Regiment, U.S. Army Reserve',
        note='美軍通用 M1A2 SEP V2，非台灣專屬 M1A2T 塗裝，僅供型號視覺代表。',
    ),
    dict(
        key='f16v', src='f16v.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/8511173/morris-angb-receives-initial-delivery-slovak-f-16-block-70-aircraft',
        photographer='Senior Airman Guadalupe Beltran',
        unit='162nd Wing, Arizona Air National Guard',
        note='斯洛伐克籍 F-16 Block 70 交機畫面，非台灣專屬塗裝（台灣機尚未交機）。',
    ),
    dict(
        key='mk48', src='mk48.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/8380753/uss-frank-cable-sailors-assist-weapons-load-mark-48-torpedoes-uss-annapolis',
        photographer='Mass Communication Specialist 1st Class Nikita Custer',
        unit='USS Frank Cable (AS 40) / USS Annapolis (SSN 760), U.S. Navy',
        note='',
    ),
    dict(
        key='slamer', src='slamer.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/7707420/vmfa-115-loads-slam-er-hot-loads-harpoons',
        photographer='Cpl. Tyler Harmon',
        unit='VMFA-115, 1st Marine Aircraft Wing, U.S. Marine Corps',
        note='',
    ),
    dict(
        key='himars', src='hero_himars_src.jpg',
        crop_box=(775, 615, 1475, 1315),  # 700x700，聚焦發射車本體（2026-07-24 換源重製）
        page_url='https://www.dvidshub.net/image/9644594/balikatan-2026-us-army-conducts-himars-launch-exercise',
        photographer='Staff Sgt. Yesenia Carrero Jimenez',
        unit='7th Infantry Division (Multi-Domain Command - Pacific)',
        note='2026-07-24 換源重製：改用 Balikatan 2026 演習照（原圖 8459531 距離更遠、'
             '車輛偏小），與新增之 hero-himars.jpg 同一來源，方形構圖聚焦發射車本體。',
    ),
    dict(
        key='mq9b', src='mq9b.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/9551424/mq-9-takes-off-over-holloman',
        photographer='Airman 1st Class Ryan Witkop',
        unit='29th Attack Squadron, 49th Wing, Holloman AFB',
        note='通用 MQ-9A Reaper，非確認為海事型 MQ-9B SeaGuardian 構型，示意用。',
    ),
    dict(
        key='m109a6', src='m109a6.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/1853828/several-m109a6-paladin-self-propelled-howitzers-conduct-test-fire',
        photographer='Spc. Nicole R. Paese',
        unit='7th Army Joint Multinational Training Command, Grafenwoehr, Germany',
        note='此採購案已於 2022-05 確認終止未交運，收錄僅供型號參考。',
    ),
    dict(
        key='harpoon_air', src='harpoon_air.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/6434271/sailors-load-agm-84d-harpoon-missile-onto-p-8a-poseidon',
        photographer='Mass Communication Specialist 2nd Class Austin Ingram',
        unit='VP-46 "Grey Knights", NAS Sigonella',
        note='圖為 AGM-84D（P-8A 掛載），非 CSV 案內的 AGM-84L-1（F-16 空射 Block II），'
             '同系列不同型號／不同掛載機種，示意用。',
    ),
    dict(
        key='aim9x', src='aim9x.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/5392749/loading-aim-9x-missile-f-16',
        photographer='Tech. Sgt. John Raven',
        unit='40th Flight Test Squadron, Holloman AFB',
        note='',
    ),
    dict(
        key='volcano', src='volcano.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/9352050/pm-ccs-demonstrates-m139-volcano',
        photographer='Spc. Hector Blanco',
        unit='1st Cavalry Division',
        note='原候選圖（同圖集 ID 9352048，頁面標示「Image 6 of 9」）之 CDN 圖檔實際'
             '內容為室內簡報聽眾照，與裝備本體不符（人工目視核對發現），改用同一活動'
             '圖集中的第 5 張（ID 9352050），為 M139 Volcano 布雷罐體＋控制盒特寫。',
    ),
    dict(
        key='mk75', src='mk75.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/8714752/coast-guard-cutter-mohawk-last-its-class-fire-mk-75-mm-gun-prior-service-life-extension',
        photographer='Ensign Brian Morel',
        unit='U.S. Coast Guard Cutter Mohawk (WMEC 613)',
        note='攝影單位為美國海岸防衛隊（USCG，屬國土安全部），非傳統陸海空軍/陸戰隊/DoD；'
             '畫面因擊發瞬間煙霧遮擋，砲身僅部分可見。',
    ),
    dict(
        key='m109a7', src='m109a7.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/9417170/us-soldiers-fire-m109a7-paladin-self-propelled-howitzer',
        photographer='Pfc. Gabriel Martinez',
        unit='Bravo Battery, 2nd Battalion, 82nd Field Artillery Regiment',
        note='',
    ),
    dict(
        key='tow', src='tow.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/8730661/tow-missile-training-fort-mccoy',
        photographer='Amanda Clark',
        unit='Fort McCoy (支援 1st Battalion, 128th Infantry, Wisconsin National Guard)',
        note='通用 TOW 發射器/彈體，未確認為 CSV 案內指定的 2B 彈頭型號。',
    ),
    dict(
        key='javelin', src='javelin.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/7111641/javelin-idaho-army-national-guard',
        photographer='Thomas Alvarez',
        unit='Charlie Company, 2-116th Combined Arms Battalion, Idaho Army National Guard',
        note='通用 Javelin 彈體，未逐一確認是否為 CSV 案內指定的 FGM-148F 型號。',
    ),
    dict(
        key='altius700', src='altius700.jpg', crop_box=None,
        page_url='https://www.dvidshub.net/image/8178544/altius-700-air-vehicle-flight',
        photographer='David Hylton',
        unit='Capability Program Executive Aviation (U.S. Army)',
        note='ALTIUS 700 基礎型飛行畫面，非確認為 CSV 案內「700M」衍生變體。',
    ),
]

# ---------------------------------------------------------------------------
# 武器內頁橫幅（2026-07-24 新增）。crop_box 為矩形（非正方形），resize 目標寬
# 固定 1600、高依 height 逐項設定（640~700 區間），以保留發射瞬間/煙尾為視覺
# 中心、裁掉多餘天空或前景。
# ---------------------------------------------------------------------------
HERO_MANIFEST = [
    dict(
        key='himars', src='hero_himars_src.jpg',
        crop_box=(500, 672, 1900, 1258), height=670,  # 1400x586 -> 1600x670
        page_url='https://www.dvidshub.net/image/9644594/balikatan-2026-us-army-conducts-himars-launch-exercise',
        photographer='Staff Sgt. Yesenia Carrero Jimenez',
        unit='7th Infantry Division (Multi-Domain Command - Pacific)',
        note='Balikatan 2026 演習（菲律賓巴拉望）HIMARS 發射車就位畫面，非台灣專屬車輛。',
    ),
    dict(
        key='patriot', src='hero_patriot_src.jpg',
        crop_box=(0, 380, 1999, 1200), height=656,  # 1999x820 -> 1600x656
        page_url='https://www.dvidshub.net/image/7275187/patriot-missile-launches-during-palau-live-fire-exercise',
        photographer='Maj. Nicholas Chopp',
        unit='94th Army Air and Missile Defense Command',
        note='Valiant Shield 22 演習、帛琉 PAC-2 Patriot 攔截彈實彈發射畫面，非台灣'
             '專屬批次或塗裝，僅作型號視覺代表。',
    ),
    dict(
        key='harpoon', src='hero_harpoon_src.jpg',
        crop_box=(0, 150, 2000, 970), height=656,  # 2000x820 -> 1600x656
        page_url='https://www.dvidshub.net/image/8543404/hnlms-tromp-fires-harpoon-missile-during-rimpac-2024',
        photographer='Maj. Christina Judd',
        unit='Commander, U.S. 3rd Fleet',
        note='發射艦為荷蘭海軍 Tromp 號（HNLMS Tromp, F803），示意圖：RIMPAC 2024 期間'
             '發射 Harpoon 反艦飛彈，非台灣籍艦艇或美軍艦，僅作 Harpoon 飛彈視覺代表。',
    ),
]

# 查無、本次不產縮圖的系統（已窮盡合理關鍵字組合，寧缺勿錯，詳見
# scratchpad/arsenal_thumbs_candidates.md）：
SKIPPED = [
    'MS-110 偵照莢艙',
    '岸置魚叉發射車（RGM-84L-4 Coastal Defense System 卡車）',
    'Switchblade 300 游蕩彈藥（僅查到 600 型，不湊用）',
    'ALTIUS 600M-V / ALTIUS-600M 情監偵型',
    'NASAMS 中程防空系統（唯一候選為挪威政府攝影師，不符美國聯邦政府作品限定）',
    'MIDS JTRS（Link-16 終端機）',
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    credits = {}
    report = []

    # --- OG 主圖 ---
    src_path = RAW / OG_SOURCE
    im = Image.open(src_path).convert('RGB')
    cropped = crop_square(im, OG_CROP_BOX)  # 這裡其實是矩形裁切，函式名沿用但傳入的是矩形 box
    resized = cropped.resize(OG_SIZE, Image.LANCZOS)
    out_path = OUT / 'og-arsenal.jpg'
    kb, q = save_with_budget(resized, out_path, OG_MAX_KB, start_quality=85)
    report.append(('og-arsenal.jpg', resized.size, kb, q))
    credits['og-arsenal.jpg'] = OG_CREDIT

    # --- 縮圖 ---
    for item in MANIFEST:
        src_path = RAW / item['src']
        if not src_path.exists():
            report.append((f"thumb-{item['key']}.jpg", None, None, None))
            continue
        im = Image.open(src_path).convert('RGB')
        cropped = crop_square(im, item['crop_box'])
        resized = cropped.resize(THUMB_SIZE, Image.LANCZOS)
        out_path = OUT / f"thumb-{item['key']}.jpg"
        kb, q = save_with_budget(resized, out_path, THUMB_MAX_KB, start_quality=82)
        report.append((out_path.name, resized.size, kb, q))
        credits[out_path.name] = {
            'dvids_page_url': item['page_url'],
            'photographer': item['photographer'],
            'unit': item['unit'],
            'note': item['note'],
        }

    # --- 武器內頁橫幅 ---
    for item in HERO_MANIFEST:
        src_path = RAW / item['src']
        if not src_path.exists():
            report.append((f"hero-{item['key']}.jpg", None, None, None))
            continue
        im = Image.open(src_path).convert('RGB')
        cropped = im.crop(item['crop_box'])
        resized = cropped.resize((HERO_WIDTH, item['height']), Image.LANCZOS)
        out_path = OUT / f"hero-{item['key']}.jpg"
        kb, q = save_with_budget(resized, out_path, HERO_MAX_KB, start_quality=82)
        report.append((out_path.name, resized.size, kb, q))
        credits[out_path.name] = {
            'dvids_page_url': item['page_url'],
            'photographer': item['photographer'],
            'unit': item['unit'],
            'note': item['note'],
        }

    credits_path = OUT / 'credits.json'
    with open(credits_path, 'w', encoding='utf-8') as f:
        json.dump(credits, f, ensure_ascii=False, indent=2)

    # --- 報告 ---
    print('=== 產出檔案 ===')
    total_kb = 0.0
    for name, size, kb, q in report:
        if size is None:
            print(f'  [SKIP] {name} — 來源檔缺失')
            continue
        total_kb += kb
        print(f'  {name}: {size[0]}x{size[1]}, {kb:.1f} KB, quality={q}')
    print(f'總大小：{total_kb:.1f} KB ({total_kb/1024:.2f} MB)')
    print(f'credits.json 條目數：{len(credits)}')
    print()
    print('=== 本次查無、未產縮圖的系統（預期行為）===')
    for s in SKIPPED:
        print(f'  - {s}')


if __name__ == '__main__':
    main()
