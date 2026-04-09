#!/usr/bin/env python3
"""
backfill_history.py — 補抓 ROC MND 歷史資料（不需 Claude API）
從 plaactlist 所有分頁收集文章，解析文字，補填 records.csv 缺少的日期

用法：
  python scripts/backfill_history.py          # 預覽模式（只印出，不寫檔）
  python scripts/backfill_history.py --write  # 實際寫入 records.csv
"""

import csv
import re
import time
import html as html_lib
import urllib.request
import ssl
import sys
from pathlib import Path

# 政府網站使用自簽憑證，略過驗證
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
BASE_URL  = 'https://www.mnd.gov.tw'
LIST_BASE = f'{BASE_URL}/news/plaactlist'

CSV_COLS = ['date', 'aircraft_total', 'median_line_cross', 'cross_rate',
            'aircraft_type', 'ships_total', 'activity_start', 'activity_end',
            'special_event']

# ── HTTP ──────────────────────────────────────────────────────────────────────

def fetch(url, delay=0.6):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (compatible; pla-tracker-backfill)'})
    try:
        with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
            raw = resp.read()
        time.sleep(delay)
        return raw.decode('utf-8', errors='replace')
    except Exception as e:
        print(f'[WARN] fetch {url}: {e}')
        return ''


# ── 日期轉換 ──────────────────────────────────────────────────────────────────

def roc_to_ad(roc_str):
    """115.04.09 → 2026-04-09"""
    m = re.match(r'(\d{2,3})\.(\d{1,2})\.(\d{1,2})', roc_str.strip())
    if not m:
        return None
    y = int(m.group(1)) + 1911
    mo = int(m.group(2))
    d  = int(m.group(3))
    return f'{y:04d}-{mo:02d}-{d:02d}'


# ── 清單頁面：收集所有文章 URL ────────────────────────────────────────────────

def collect_articles(max_pages=15):
    """回傳 [(ad_date, article_url), ...] 按日期排序
    HTML 結構：
      <a href="news/plaact/XXXXX" class="news_list">
      <div class="date headline-h5">115.04.09</div>
    """
    seen   = set()
    result = []

    for page in range(1, max_pages + 1):
        url  = f'{LIST_BASE}/{page}'
        body = fetch(url)
        if not body:
            break

        # 找每個 news_list 鏈接，再往後找最近的日期 div
        pairs = re.findall(
            r'href="(news/plaact/\d+)"[^>]*class="news_list"[\s\S]{0,300}?'
            r'class="date[^"]*">(\d{3}\.\d{2}\.\d{2})<',
            body)
        if not pairs:
            # fallback：先日期後連結
            pairs_alt = re.findall(
                r'class="date[^"]*">(\d{3}\.\d{2}\.\d{2})<[\s\S]{0,300}?'
                r'href="(news/plaact/\d+)"',
                body)
            pairs = [(p, d) for d, p in pairs_alt]

        if not pairs:
            print(f'[WARN] page {page}: no articles found, stopping')
            break

        added_this_page = 0
        for path, roc_date in pairs:
            ad = roc_to_ad(roc_date)
            if ad and path not in seen:
                seen.add(path)
                result.append((ad, f'{BASE_URL}/{path}'))
                added_this_page += 1

        print(f'[list] page {page}: {added_this_page} articles  '
              f'({pairs[0][1]} → {pairs[-1][1]})')

        # 最早日期已在 2025 年以前就停止（只要 2026 資料）
        earliest = roc_to_ad(pairs[-1][1])
        if earliest and earliest < '2026-01-01':
            print(f'[list] reached pre-2026 data, stopping')
            break

        # 判斷是否還有下一頁
        if f'plaactlist/{page + 1}' not in body:
            print(f'[list] no page {page + 1}, done')
            break

    result.sort(key=lambda x: x[0])
    # 只保留 2026 年以後
    result = [(d, u) for d, u in result if d >= '2026-01-01']
    return result


# ── 單篇解析 ──────────────────────────────────────────────────────────────────

def strip_tags(s):
    return html_lib.unescape(re.sub(r'<[^>]+>', ' ', s))


def parse_article(url, ad_date):
    body = fetch(url)
    if not body:
        return None

    text = strip_tags(body)
    # 只保留主要內容段落（減少雜訊）
    # 抓 "偵獲共機" 所在段落前後 500 字
    anchor = text.find('偵獲共機')
    if anchor == -1:
        anchor = text.find('共機')
    snippet = text[max(0, anchor - 100): anchor + 600] if anchor != -1 else text

    # ── 架次 ──
    ac_m = re.search(r'偵獲共機(\d+)架次', snippet)
    if not ac_m:
        ac_m = re.search(r'偵獲共機(\d+)架[，、。\s]', snippet)
    aircraft = int(ac_m.group(1)) if ac_m else 0

    # ── 越中線 ──
    cr_m = re.search(r'逾越中線[^，。]*?(\d+)架次', snippet)
    if not cr_m:
        cr_m = re.search(r'越中線[^，。]*?(\d+)架', snippet)
    crosses = int(cr_m.group(1)) if cr_m else 0
    if crosses > aircraft:
        crosses = aircraft  # 修正異常值

    cross_rate = f'{crosses / aircraft * 100:.0f}' if aircraft > 0 else ''

    # ── 艦艇（只算 共艦，不含公務船）──
    sh_m = re.search(r'共艦(\d+)艘', snippet)
    ships = int(sh_m.group(1)) if sh_m else 0

    # ── 機型 ──
    if aircraft == 0:
        atype = 'zero'
    else:
        has_uav   = bool(re.search(r'無人機|無人載具', snippet))
        has_manned = bool(re.search(r'戰機|轟炸機|運輸機|偵察機|預警機|電戰機|反潛機|Su-|J-\d|H-\d', snippet))
        has_heli  = bool(re.search(r'直升機|武直', snippet))

        types = ([('manned'    , has_manned),
                  ('uav'       , has_uav),
                  ('helicopter', has_heli)])
        active = [t for t, v in types if v]

        if len(active) > 1:
            atype = 'mixed'
        elif active:
            atype = active[0]
        else:
            atype = 'manned'   # 預設：有機即有人機

    # ── 特殊事件 ──
    specials = []
    full_text = strip_tags(body)
    if re.search(r'氣球', full_text):
        # 抓氣球相關句子
        m = re.search(r'[^。]*氣球[^。]*。', full_text)
        specials.append(m.group(0).strip() if m else '氣球')
    if re.search(r'火箭|彈道飛彈|天舟|長征', full_text):
        m = re.search(r'[^。]*(?:火箭|飛彈|天舟|長征)[^。]*。', full_text)
        specials.append(m.group(0).strip() if m else '火箭/飛彈')
    # 越線進入哪個空域
    zone_m = re.search(r'逾越中線進入([^，。\s]+空域)', snippet)
    if zone_m and crosses > 0:
        specials.append(f'越線：{zone_m.group(1)}')

    return {
        'date'             : ad_date,
        'aircraft_total'   : aircraft,
        'median_line_cross': crosses,
        'cross_rate'       : cross_rate,
        'aircraft_type'    : atype,
        'ships_total'      : ships,
        'activity_start'   : '',
        'activity_end'     : '',
        'special_event'    : '；'.join(specials),
    }


# ── CSV 工具 ──────────────────────────────────────────────────────────────────

def load_existing_dates():
    if not DATA_FILE.exists():
        return set()
    with open(DATA_FILE, newline='', encoding='utf-8') as f:
        return {row['date'] for row in csv.DictReader(f)}


def merge_and_save(new_rows):
    existing = []
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            existing = list(csv.DictReader(f))

    existing_dates = {r['date'] for r in existing}
    added = [r for r in new_rows if r['date'] not in existing_dates]

    all_rows = sorted(existing + added, key=lambda r: r['date'])

    with open(DATA_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for row in all_rows:
            w.writerow({k: row.get(k, '') for k in CSV_COLS})

    return len(added)


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    write_mode = '--write' in sys.argv

    print('=== PLA Tracker 歷史資料補抓 ===')
    if not write_mode:
        print('[預覽模式] 加上 --write 參數才會實際寫入 records.csv\n')

    # 1. 收集所有文章 URL
    articles = collect_articles(max_pages=15)
    print(f'\n共找到 {len(articles)} 篇文章（{articles[0][0]} → {articles[-1][0]}）\n')

    # 2. 過濾已有的日期
    existing_dates = load_existing_dates()
    missing = [(d, u) for d, u in articles if d not in existing_dates]
    print(f'records.csv 已有 {len(existing_dates)} 筆，需補抓 {len(missing)} 筆\n')

    if not missing:
        print('沒有需要補抓的資料。')
        return

    # 3. 逐篇解析
    new_rows = []
    for i, (ad_date, url) in enumerate(missing, 1):
        print(f'[{i:3d}/{len(missing)}] {ad_date}  {url}', end='  ')
        row = parse_article(url, ad_date)
        if row:
            print(f"ac={row['aircraft_total']} cross={row['median_line_cross']} "
                  f"sh={row['ships_total']} type={row['aircraft_type']}")
            new_rows.append(row)
        else:
            print('SKIP (parse failed)')

    print(f'\n解析完成，{len(new_rows)} 筆新資料')

    # 4. 寫入或預覽
    if write_mode:
        added = merge_and_save(new_rows)
        print(f'[OK] 已寫入 {added} 筆到 {DATA_FILE}')
    else:
        print('\n[預覽] 前 10 筆：')
        for r in new_rows[:10]:
            print(f"  {r['date']}  ac={r['aircraft_total']:2d} "
                  f"cross={r['median_line_cross']:2d}  sh={r['ships_total']:2d}  "
                  f"type={r['aircraft_type']:10s}  {r['special_event']}")
        print('\n加上 --write 寫入 CSV。')


if __name__ == '__main__':
    main()
