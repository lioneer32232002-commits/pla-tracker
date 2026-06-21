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
INDEX_HTML = ROOT / 'index.html'
RECORDS_HTML = ROOT / 'records.html'
VERSION_TXT = ROOT / 'version.txt'

EN_DIR = ROOT / 'en'
EN_INDEX   = EN_DIR / 'index.html'
EN_RECORDS = EN_DIR / 'records.html'
EN_MONTHLY = EN_DIR / 'monthly.html'

ABOUT_HTML = ROOT / 'about.html'
EN_ABOUT   = EN_DIR / 'about.html'

# 可嵌入圖表頁（媒體可引用：PNG 下載 + iframe 嵌入）
EMBED_SLUGS    = ['recent', 'ytd']
ZH_EMBED_DIR   = ROOT / 'embed'
EN_EMBED_DIR   = EN_DIR / 'embed'

SITEMAP    = ROOT / 'sitemap.xml'
ROBOTS     = ROOT / 'robots.txt'
OG_IMG     = ROOT / 'og.png'
OG_IMG_EN  = ROOT / 'og-en.png'
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


# ── HTML 驗證 ─────────────────────────────────────────────────────────────────

def validate_html():
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

    # ── 媒體可引用：首頁工具列 + 可嵌入圖表頁 ─────────────────────────────────
    import re as _re2
    # 首頁（中英）必須帶 PNG 下載 + 嵌入工具列，否則代表 build_index 工具列漏掉
    for idx_path, label in [(INDEX_HTML, 'index.html'), (EN_INDEX, 'en/index.html')]:
        if idx_path.exists():
            idx = idx_path.read_text(encoding='utf-8')
            for marker, desc in [('plaDownloadChart', 'PNG 下載按鈕/腳本'),
                                 ('class="embed-box"', 'iframe 嵌入碼區塊')]:
                if marker not in idx:
                    errors.append(f'{label} 缺少 {desc}（找不到「{marker}」）')

    # 可嵌入圖表頁本體：存在、noindex、Chart.js、canvas、頁腳回連本站
    embed_targets = (
        [(ZH_EMBED_DIR / f'{s}.html', f'embed/{s}.html', False) for s in EMBED_SLUGS] +
        [(EN_EMBED_DIR / f'{s}.html', f'en/embed/{s}.html', True) for s in EMBED_SLUGS]
    )
    for path, label, is_en in embed_targets:
        if not path.exists():
            errors.append(f'{label} 不存在（build 可能未產出嵌入頁）')
            continue
        if path.stat().st_size < 1_500:
            errors.append(f'{label} 檔案過小（{path.stat().st_size} bytes）')
            continue
        emb = path.read_text(encoding='utf-8')
        for marker, desc in [('name="robots" content="noindex', 'noindex 標記'),
                             ('cdn.jsdelivr.net/npm/chart.js', 'Chart.js 載入'),
                             ('<canvas', '圖表 canvas'),
                             (BASE_URL, '頁腳回連本站')]:
            if marker not in emb:
                errors.append(f'{label} 缺少 {desc}（找不到「{marker}」）')
        # 英文嵌入頁不得殘留中文（與英文主頁同規則，script 內資料不算）
        if is_en:
            no_script = _re2.sub(r'<script[^>]*>.*?</script>', '', emb, flags=_re2.DOTALL)
            cjk = _re2.findall(r'[一-鿿]+', no_script)
            if cjk:
                sample = '、'.join(sorted(set(cjk))[:5])
                errors.append(f'{label} 含有中文字元（翻譯規則可能遺漏）：{sample}')

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
    if mode in ('html', 'all'):
        results.append(validate_html())

    if all(results):
        pass  # silent on pass
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
