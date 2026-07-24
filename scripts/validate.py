"""
validate.py — 兩段式驗證工具
  python scripts/validate.py csv   → 驗 records.csv 資料完整性
  python scripts/validate.py html  → 驗 build 後 HTML 結構
  python scripts/validate.py all   → 兩段都跑

規則：驗過不開口（silent on pass），出錯才報告並以 exit code 1 終止。
"""

import sys
import io
import csv
from pathlib import Path
from datetime import datetime, timedelta

# Windows 終端機統一用 UTF-8 輸出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT      = Path(__file__).parent.parent
CSV_PATH  = ROOT / 'data' / 'records.csv'
ARSENAL_CSV = ROOT / 'data' / 'arsenal.csv'
PEERS_CSV   = ROOT / 'data' / 'arsenal_peers.csv'
ARSENAL_HTML    = ROOT / 'arsenal' / 'index.html'
EN_ARSENAL_HTML = ROOT / 'en' / 'arsenal' / 'index.html'
ARS_DETAIL_KEYS = ['harpoon', 'patriot', 'himars']
INDEX_HTML = ROOT / 'index.html'
RECORDS_HTML = ROOT / 'records.html'
VERSION_TXT = ROOT / 'version.txt'

EN_DIR = ROOT / 'en'
EN_INDEX   = EN_DIR / 'index.html'
EN_RECORDS = EN_DIR / 'records.html'
EN_MONTHLY = EN_DIR / 'monthly.html'

ABOUT_HTML = ROOT / 'about.html'
EN_ABOUT   = EN_DIR / 'about.html'

SITEMAP    = ROOT / 'sitemap.xml'
ROBOTS     = ROOT / 'robots.txt'
OG_IMG     = ROOT / 'og.png'
OG_IMG_EN  = ROOT / 'og-en.png'
ARSENAL_OG_IMG = ROOT / 'assets' / 'arsenal' / 'og-arsenal.jpg'
BASE_URL   = 'https://pla-tracker.pages.dev'

VALID_TYPES = {'manned', 'uav', 'mixed', 'zero',
               'Manned', 'UAV', 'Mixed', 'Zero',
               'Helicopter', 'helicopter'}

# ── CSV 驗證 ──────────────────────────────────────────────────────────────────

def validate_csv():
    errors = []

    if not CSV_PATH.exists():
        print(f'[FAIL] CSV 不存在：{CSV_PATH}')
        return False

    rows = []
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # 第1行是 header，資料從第2行起
            rows.append((i, row))

    seen_dates = {}

    for lineno, row in rows:
        date_str = row.get('date', '').strip()

        # 日期格式
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            errors.append(f'第{lineno}行：日期格式錯誤「{date_str}」（應為 YYYY-MM-DD）')
            continue

        # 重複日期
        if date_str in seen_dates:
            errors.append(f'第{lineno}行：日期重複「{date_str}」（首次出現於第{seen_dates[date_str]}行）')
        else:
            seen_dates[date_str] = lineno

        # 架次數字
        try:
            total = int(row['aircraft_total'])
            cross = int(row['median_line_cross'])
        except (ValueError, KeyError):
            errors.append(f'第{lineno}行 {date_str}：架次欄位非整數')
            continue

        if total < 0:
            errors.append(f'第{lineno}行 {date_str}：aircraft_total 不能為負數（{total}）')
        if cross < 0:
            errors.append(f'第{lineno}行 {date_str}：median_line_cross 不能為負數（{cross}）')
        if cross > total:
            errors.append(f'第{lineno}行 {date_str}：逾越中線（{cross}）不能大於總架次（{total}）')

        # cross_rate 一致性（允許 ±1% 誤差）
        rate_str = row.get('cross_rate', '').strip()
        if rate_str and rate_str != '':
            try:
                rate = float(rate_str)
                if total > 0:
                    expected = round(cross / total * 100, 2)
                    if abs(rate - expected) > 1.0:
                        errors.append(
                            f'第{lineno}行 {date_str}：cross_rate={rate} 與計算值 {expected} 差距超過 1%'
                        )
            except ValueError:
                errors.append(f'第{lineno}行 {date_str}：cross_rate 格式錯誤「{rate_str}」')

        # 艦艇數
        try:
            ships = int(row['ships_total'])
            if ships < 0:
                errors.append(f'第{lineno}行 {date_str}：ships_total 不能為負數（{ships}）')
        except (ValueError, KeyError):
            errors.append(f'第{lineno}行 {date_str}：ships_total 欄位非整數')

        # aircraft_type 合法值
        atype = row.get('aircraft_type', '').strip()
        if atype not in VALID_TYPES:
            errors.append(f'第{lineno}行 {date_str}：aircraft_type 值不合法「{atype}」（應為 Manned/UAV/Mixed/Zero）')

    # 最新資料是否過期（超過7天發警告，不阻擋）
    if seen_dates:
        latest = max(seen_dates.keys())
        latest_dt = datetime.strptime(latest, '%Y-%m-%d')
        if datetime.today() - latest_dt > timedelta(days=7):
            print(f'[WARN] 最新資料為 {latest}，距今超過 7 天，請確認是否有漏更新。')

    if errors:
        print(f'[FAIL] CSV 驗證發現 {len(errors)} 個問題：')
        for e in errors:
            print(f'  ✗ {e}')
        return False

    return True


# ── 軍購 CSV 驗證 ─────────────────────────────────────────────────────────────

ARS_COLUMNS = ['case_id', 'announce_date', 'system_zh', 'system_en', 'category',
               'value_usd_m', 'qty', 'qty_unit', 'delivery_status', 'first_delivery',
               'expected_complete', 'delivered_note', 'source_announce',
               'source_delivery', 'notes']
ARS_CATEGORIES = {'aircraft', 'missile', 'ground', 'naval', 'uas', 'c4isr', 'sustainment'}
ARS_STATUSES   = {'completed', 'delivering', 'announced', 'unknown', 'cancelled'}
PEERS_KEYS     = {'f16v', 'harpoon', 'himars', 'javelin', 'm1a2', 'mq9b', 'patriot', 'stinger'}


def validate_arsenal():
    errors = []

    # ── 主表 arsenal.csv ──
    if not ARSENAL_CSV.exists():
        print(f'[FAIL] 軍購主表不存在：{ARSENAL_CSV}')
        return False
    with open(ARSENAL_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ARS_COLUMNS:
            errors.append(f'arsenal.csv 欄位不符，應為 {ARS_COLUMNS}，實為 {reader.fieldnames}')
        rows = list(reader)
    seen_cases = set()
    for i, row in enumerate(rows, start=2):
        cid = row.get('case_id', '').strip()
        if not cid:
            errors.append(f'arsenal 第{i}行：case_id 空白')
        elif cid in seen_cases:
            errors.append(f'arsenal 第{i}行：case_id 重複「{cid}」')
        else:
            seen_cases.add(cid)
        # ISO 日期
        try:
            datetime.strptime(row.get('announce_date', '').strip(), '%Y-%m-%d')
        except ValueError:
            errors.append(f'arsenal 第{i}行 {cid}：announce_date 非 ISO 日期「{row.get("announce_date")}」')
        # category / status 列舉
        if row.get('category', '').strip() not in ARS_CATEGORIES:
            errors.append(f'arsenal 第{i}行 {cid}：category 不合法「{row.get("category")}」')
        if row.get('delivery_status', '').strip() not in ARS_STATUSES:
            errors.append(f'arsenal 第{i}行 {cid}：delivery_status 不合法「{row.get("delivery_status")}」')
        # value_usd_m 數字
        try:
            float(row.get('value_usd_m', '').strip())
        except ValueError:
            errors.append(f'arsenal 第{i}行 {cid}：value_usd_m 非數字「{row.get("value_usd_m")}」')
        # source_announce http 開頭
        if not row.get('source_announce', '').strip().startswith('http'):
            errors.append(f'arsenal 第{i}行 {cid}：source_announce 非 http 開頭')

    # ── 對比表 arsenal_peers.csv ──
    if not PEERS_CSV.exists():
        print(f'[FAIL] 軍購對比表不存在：{PEERS_CSV}')
        return False
    with open(PEERS_CSV, newline='', encoding='utf-8') as f:
        preader = csv.DictReader(f)
        prows = list(preader)
    for i, row in enumerate(prows, start=2):
        key = row.get('system_key', '').strip()
        if key not in PEERS_KEYS:
            errors.append(f'peers 第{i}行：system_key 不合法「{key}」')
        if not row.get('source', '').strip():
            errors.append(f'peers 第{i}行：source 空白（{row.get("buyer_country")}）')

    if errors:
        print(f'[FAIL] 軍購 CSV 驗證發現 {len(errors)} 個問題：')
        for e in errors:
            print(f'  ✗ {e}')
        return False
    return True


# ── HTML 驗證 ─────────────────────────────────────────────────────────────────

def validate_html():
    import re as _re0
    errors = []

    # 檔案存在且有內容
    for path in [INDEX_HTML, RECORDS_HTML]:
        if not path.exists():
            errors.append(f'檔案不存在：{path.name}')
            continue
        size = path.stat().st_size
        if size < 10_000:
            errors.append(f'{path.name} 檔案過小（{size} bytes），可能 build 失敗')

    # index.html 結構檢查
    if INDEX_HTML.exists():
        content = INDEX_HTML.read_text(encoding='utf-8')
        checks = [
            ('class="sitrep',       'SITREP 區塊'),
            ('class="stat"',        '統計數字區塊'),
            ('class="stats-row"',   '統計列'),
            ('至今',                ' 月份至今區塊'),
            ('name="description"',  'meta description'),
            ('rel="canonical"',     'canonical 連結'),
            ('property="og:image"', 'OG 圖標籤'),
            ('name="twitter:card"', 'Twitter 卡片'),
            ('application/ld+json',  'JSON-LD 區塊'),
            ('"@type": "Dataset"',  'Dataset 結構化資料'),
            ('class="sitrep-text"', '一句話文字 SITREP'),
            (f'{BASE_URL}/og.png',  'OG 圖絕對網址'),
            ('data-theme="',        '主題屬性（嚴重日配色）'),
        ]
        for marker, desc in checks:
            if marker not in content:
                errors.append(f'index.html 缺少 {desc}（找不到「{marker}」）')

        # 確認沒有明顯佔位文字（排除 JS 中的合法用法）
        for placeholder in ['TODO', 'PLACEHOLDER', 'NaN%']:
            if placeholder in content:
                errors.append(f'index.html 含有佔位文字：「{placeholder}」')

    # version.txt 存在
    if not VERSION_TXT.exists():
        errors.append('version.txt 不存在，build 可能未執行')

    # ── 英文版三頁檢查 ──────────────────────────────────────────────────────────

    EN_MIN_SIZES = {EN_INDEX: 10_000, EN_RECORDS: 10_000,
                    EN_MONTHLY: 1_000, EN_ABOUT: 3_000}
    for path in [EN_INDEX, EN_RECORDS, EN_MONTHLY, EN_ABOUT]:
        if not path.exists():
            errors.append(f'en/{path.name} 不存在（build 可能未產出英文版）')
            continue
        size = path.stat().st_size
        min_size = EN_MIN_SIZES[path]
        if size < min_size:
            errors.append(f'en/{path.name} 檔案過小（{size} bytes，預期 >{min_size}）')
            continue

        content = path.read_text(encoding='utf-8')

        # lang="en" 屬性
        if 'lang="en"' not in content:
            errors.append(f'en/{path.name} 缺少 <html lang="en">')

        # hreflang alternate 標籤
        for rel_type in ['hreflang="zh-Hant"', 'hreflang="en"']:
            if rel_type not in content:
                errors.append(f'en/{path.name} 缺少 <link rel="alternate" {rel_type}>')

        # en 頁面不得含中文字元（語言切換的「中文」二字除外）
        import re as _re
        html_no_script = _re.sub(r'<script[^>]*>.*?</script>', '',
                                 content, flags=_re.DOTALL)
        # 移除允許的「中文」切換標籤後再掃描
        html_cleaned = html_no_script.replace('中文', '')
        chinese_found = _re.findall(r'[一-鿿]+', html_cleaned)
        if chinese_found:
            sample = '、'.join(sorted(set(chinese_found))[:5])
            errors.append(
                f'en/{path.name} 含有中文字元（翻譯規則可能遺漏）：{sample}'
            )

    # ── 英文首頁 SEO 標籤（與中文首頁對稱，防止未來只在 zh 產生而 en 漏掉）─────
    if EN_INDEX.exists():
        en_idx = EN_INDEX.read_text(encoding='utf-8')
        for marker, desc in [
            ('name="description"',     'meta description'),
            ('rel="canonical"',        'canonical 連結'),
            ('property="og:image"',    'OG 圖標籤'),
            (f'{BASE_URL}/og-en.png',  'OG 圖(en)絕對網址'),
            ('name="twitter:card"',    'Twitter 卡片'),
            ('"@type": "Dataset"',     'Dataset 結構化資料'),
            ('class="sitrep-text"',    '一句話文字 SITREP'),
            ('data-theme="',           '主題屬性（嚴重日配色）'),
        ]:
            if marker not in en_idx:
                errors.append(f'en/index.html 缺少 {desc}（找不到「{marker}」）')

    # ── about.html（中文方法論頁）─────────────────────────────────────────────
    if not ABOUT_HTML.exists():
        errors.append('about.html 不存在（build 可能未產出方法論頁）')
    else:
        about = ABOUT_HTML.read_text(encoding='utf-8')
        if ABOUT_HTML.stat().st_size < 3_000:
            errors.append(f'about.html 檔案過小（{ABOUT_HTML.stat().st_size} bytes）')
        for marker, desc in [('方法論', '頁面標題'),
                             ('class="def-card"', '名詞定義卡'),
                             ('12 浬領海', '12浬領海定義'),
                             ('rel="canonical"', 'canonical 連結')]:
            if marker not in about:
                errors.append(f'about.html 缺少 {desc}（找不到「{marker}」）')

    # ── /arsenal/ 軍購儀表板（zh + en）────────────────────────────────────────
    for path, is_en in [(ARSENAL_HTML, False), (EN_ARSENAL_HTML, True)]:
        label = 'en/arsenal/index.html' if is_en else 'arsenal/index.html'
        if not path.exists():
            errors.append(f'{label} 不存在（build 可能未產出軍購頁）')
            continue
        if path.stat().st_size < 10_000:
            errors.append(f'{label} 檔案過小（{path.stat().st_size} bytes）')
            continue
        content = path.read_text(encoding='utf-8')
        for marker, desc in [
            ('class="ars-kpi', 'KPI 卡列'),
            ('class="ars-syscards"', '系統卡片牆'),
            ('class="ars-syscard"', '系統卡'),
            ('id="ars-year"', '年度金額圖'),
            ('class="ars-reads"', '質性判讀區塊'),
            ('class="ars-scope"', '口徑說明'),
            ('rel="canonical"', 'canonical 連結'),
            ('hreflang="zh-Hant"', 'hreflang zh'),
            ('hreflang="en"', 'hreflang en'),
            ('property="og:image"', 'OG 圖標籤'),
            ('assets/arsenal/og-arsenal.jpg', '軍購專屬 OG 縮圖'),
        ]:
            if marker not in content:
                errors.append(f'{label} 缺少 {desc}（找不到「{marker}」）')
        # canonical 應指向 /arsenal/ 目錄式路徑
        expect_canon = (f'{BASE_URL}/en/arsenal/' if is_en else f'{BASE_URL}/arsenal/')
        if f'href="{expect_canon}"' not in content:
            errors.append(f'{label} canonical 未指向 {expect_canon}')
        if is_en:
            if 'lang="en"' not in content:
                errors.append('en/arsenal/index.html 缺少 <html lang="en">')
            html_no_script = _re0.sub(r'<script[^>]*>.*?</script>', '', content, flags=_re0.DOTALL)
            html_cleaned = html_no_script.replace('中文', '')
            chinese_found = _re0.findall(r'[一-鿿]+', html_cleaned)
            if chinese_found:
                sample = '、'.join(sorted(set(chinese_found))[:5])
                errors.append(f'en/arsenal/index.html 含有中文字元（翻譯規則可能遺漏）：{sample}')

    # ── /arsenal/{harpoon,patriot,himars}.html 武器內頁（zh + en）───────────────
    for wkey in ARS_DETAIL_KEYS:
        for is_en in (False, True):
            path = (ROOT / 'en' / 'arsenal' / f'{wkey}.html') if is_en else (ROOT / 'arsenal' / f'{wkey}.html')
            label = f'{"en/" if is_en else ""}arsenal/{wkey}.html'
            if not path.exists():
                errors.append(f'{label} 不存在（build 可能未產出武器內頁）')
                continue
            if path.stat().st_size < 6_000:
                errors.append(f'{label} 檔案過小（{path.stat().st_size} bytes）')
                continue
            content = path.read_text(encoding='utf-8')
            markers = [
                ('class="ars-tl"', '採購時間軸'),
                ('class="ars-reads"', '實戰紀錄'),
                ('class="ars-role"', '台海角色'),
                ('class="ars-srclist"', '來源清單'),
                ('rel="canonical"', 'canonical 連結'),
                ('hreflang="zh-Hant"', 'hreflang zh'),
                ('hreflang="en"', 'hreflang en'),
            ]
            # 愛國者頁用使用國卡片牆取代排名圖；其餘頁有排名圖 canvas
            markers.append(('class="ars-userwall"', 'PAC-3 使用國卡片牆') if wkey == 'patriot'
                           else ('id="ars-rank"', '排名圖'))
            for marker, desc in markers:
                if marker not in content:
                    errors.append(f'{label} 缺少 {desc}（找不到「{marker}」）')
            expect_canon = (f'{BASE_URL}/en/arsenal/{wkey}.html' if is_en
                            else f'{BASE_URL}/arsenal/{wkey}.html')
            if f'href="{expect_canon}"' not in content:
                errors.append(f'{label} canonical 未指向 {expect_canon}')
            if is_en:
                if 'lang="en"' not in content:
                    errors.append(f'{label} 缺少 <html lang="en">')
                hns = _re0.sub(r'<script[^>]*>.*?</script>', '', content, flags=_re0.DOTALL)
                cf = _re0.findall(r'[一-鿿]+', hns.replace('中文', ''))
                if cf:
                    sample = '、'.join(sorted(set(cf))[:5])
                    errors.append(f'{label} 含有中文字元（翻譯規則可能遺漏）：{sample}')

    # ── sitemap.xml / robots.txt ─────────────────────────────────────────────
    if not SITEMAP.exists():
        errors.append('sitemap.xml 不存在')
    else:
        sm = SITEMAP.read_text(encoding='utf-8')
        for page in ['index', 'records', 'monthly', 'about']:
            if f'{BASE_URL}/{page}.html' not in sm:
                errors.append(f'sitemap.xml 缺少中文 {page} 頁')
            if f'{BASE_URL}/en/{page}.html' not in sm:
                errors.append(f'sitemap.xml 缺少英文 {page} 頁')
        for loc in [f'{BASE_URL}/arsenal/', f'{BASE_URL}/en/arsenal/']:
            if loc not in sm:
                errors.append(f'sitemap.xml 缺少 {loc}')
        for wkey in ARS_DETAIL_KEYS:
            for loc in [f'{BASE_URL}/arsenal/{wkey}.html', f'{BASE_URL}/en/arsenal/{wkey}.html']:
                if loc not in sm:
                    errors.append(f'sitemap.xml 缺少 {loc}')

    if not ROBOTS.exists():
        errors.append('robots.txt 不存在')
    else:
        rb = ROBOTS.read_text(encoding='utf-8')
        if f'Sitemap: {BASE_URL}/sitemap.xml' not in rb:
            errors.append('robots.txt 缺少正確的 Sitemap 指向')

    # ── OG 分享圖 ────────────────────────────────────────────────────────────
    for og in [OG_IMG, OG_IMG_EN]:
        if not og.exists():
            errors.append(f'{og.name} 不存在（請執行 scripts/make_og_image.py）')
        elif og.stat().st_size < 5_000:
            errors.append(f'{og.name} 檔案過小（{og.stat().st_size} bytes）')

    # ── 軍購武器影像資產（assets/arsenal/，靜態檔不由 build 產生）──────────────
    if not ARSENAL_OG_IMG.exists():
        errors.append(f'{ARSENAL_OG_IMG.relative_to(ROOT)} 不存在（軍購 OG 圖缺檔）')
    elif ARSENAL_OG_IMG.stat().st_size < 5_000:
        errors.append(f'{ARSENAL_OG_IMG.relative_to(ROOT)} 檔案過小（{ARSENAL_OG_IMG.stat().st_size} bytes）')

    if errors:
        print(f'[FAIL] HTML 驗證發現 {len(errors)} 個問題：')
        for e in errors:
            print(f'  ✗ {e}')
        return False

    return True


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    results = []

    if mode in ('csv', 'all'):
        results.append(validate_csv())
        results.append(validate_arsenal())
    if mode in ('html', 'all'):
        results.append(validate_html())

    if all(results):
        pass  # silent on pass
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
