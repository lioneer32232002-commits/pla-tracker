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
            ('class="sitrep',      'SITREP 區塊'),
            ('class="stat"',       '統計數字區塊'),
            ('class="stats-row"',  '統計列'),
            ('至今',               '月份至今區塊'),
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
