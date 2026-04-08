"""
fetch_and_update.py — PLA Tracker 每日自動更新

流程：
1. 從 MND 網站抓最新共機動態公告圖片
2. 用 Claude API 解讀圖片，提取結構化數據
3. 追加到 records.csv（若當日已有紀錄則跳過）
4. 產出圖表 PNG（chart_daily.py）
5. 重建網站（build_site.py）
"""

import os
import sys
import json
import base64
import hashlib
import subprocess
from datetime import date, timedelta
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup
import pandas as pd

ROOT       = Path(__file__).parent.parent
DATA_FILE  = ROOT / 'data' / 'records.csv'
CACHE_DIR  = ROOT / 'data' / '.cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MND_LIST_URL = 'https://www.mnd.gov.tw/news/plaactlist'
MND_BASE_URL = 'https://www.mnd.gov.tw'

# 欄位順序與 records.csv 一致
CSV_COLS = [
    'date', 'aircraft_total', 'median_line_cross', 'cross_rate',
    'aircraft_type', 'ships_total', 'activity_start', 'activity_end',
    'special_event'
]

EXTRACT_PROMPT = """你是軍事數據分析員。請仔細閱讀這張中華民國國防部每日共機動態公告圖片，提取以下資訊並以 JSON 格式回答。

注意：
- 「報告日期」是圖片上標示的結束日期（例如圖片標注「3月20日」，date 就是 2026-03-20）
- aircraft_total：共機架次總數（整數）
- median_line_cross：逾越海峽中線的架次數（整數，若無則 0）
- cross_rate：越線率百分比（數字，不含%符號；若無共機則留空字串）
- aircraft_type：機型分類，只能是以下之一：Manned / UAV / Mixed / Zero / Helicopter
  - Manned = 只有有人戰機/轟炸機/輔戰機
  - UAV = 只有無人機
  - Mixed = 有人機＋無人機混合，或有人機＋直升機
  - Zero = 零架次
  - Helicopter = 只有直升機（無戰機）
- ships_total：解放軍軍艦＋公務船總艘數（整數）
- activity_start：共機活動最早時間（HH:MM 格式，無則空字串）
- activity_end：共機活動最晚時間（HH:MM 格式，無則空字串）
- special_event：特殊事件簡述（繁體中文，無則空字串）

請只回傳 JSON，不要任何說明文字：
{
  "date": "YYYY-MM-DD",
  "aircraft_total": 0,
  "median_line_cross": 0,
  "cross_rate": "",
  "aircraft_type": "Zero",
  "ships_total": 0,
  "activity_start": "",
  "activity_end": "",
  "special_event": ""
}"""


def log(msg):
    print(f'[fetch] {msg}', flush=True)


def get_mnd_latest_image_url():
    """從 MND 共機動態列表頁取得最新公告的圖片 URL"""
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; PLA-Tracker/1.0)'}
    resp = requests.get(MND_LIST_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')

    def abs_url(href):
        if href.startswith('http'):
            return href
        if not href.startswith('/'):
            href = '/' + href
        return MND_BASE_URL + href

    # 找第一筆公告連結
    article_link = None
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/news/plaact/' in href or '/plaact/' in href.lower():
            article_link = abs_url(href)
            break

    if not article_link:
        # 備用：找列表中任何含 plaact 的連結
        for a in soup.find_all('a', href=True):
            if 'plaact' in a['href'].lower():
                article_link = abs_url(a['href'])
                break

    if not article_link:
        raise RuntimeError('找不到共機動態公告連結')

    log(f'公告頁面：{article_link}')

    # 進入公告頁面，找圖片
    resp2 = requests.get(article_link, headers=headers, timeout=30)
    resp2.raise_for_status()
    soup2 = BeautifulSoup(resp2.text, 'html.parser')

    img_url = None
    for img in soup2.find_all('img', src=True):
        src = img['src']
        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            if 'plaact' in src.lower() or 'military' in src.lower() or '/upload' in src.lower():
                img_url = abs_url(src)
                break

    # 備用：找最大的圖片
    if not img_url:
        for img in soup2.find_all('img', src=True):
            src = img['src']
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png']):
                if not any(x in src.lower() for x in ['logo', 'icon', 'banner', 'header']):
                    img_url = abs_url(src)
                    break

    if not img_url:
        raise RuntimeError('找不到公告圖片')

    log(f'圖片 URL：{img_url}')
    return img_url


def download_image(url):
    """下載圖片，回傳 (bytes, cache_path)，若已快取則直接讀快取"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    ext = url.split('?')[0].rsplit('.', 1)[-1].lower() or 'jpg'
    cache_path = CACHE_DIR / f'{url_hash}.{ext}'

    if cache_path.exists():
        log(f'使用快取：{cache_path.name}')
        return cache_path.read_bytes(), cache_path

    headers = {'User-Agent': 'Mozilla/5.0 (compatible; PLA-Tracker/1.0)'}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    cache_path.write_bytes(resp.content)
    log(f'已下載：{cache_path.name} ({len(resp.content)//1024} KB)')
    return resp.content, cache_path


def extract_data_from_image(img_bytes, img_url):
    """用 Claude API 解讀圖片，回傳 dict"""
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    ext = img_url.split('?')[0].rsplit('.', 1)[-1].lower()
    media_type_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                      'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
    media_type = media_type_map.get(ext, 'image/jpeg')

    img_b64 = base64.standard_b64encode(img_bytes).decode()

    log('呼叫 Claude API 解讀圖片…')
    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=512,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64',
                                             'media_type': media_type,
                                             'data': img_b64}},
                {'type': 'text', 'text': EXTRACT_PROMPT}
            ]
        }]
    )

    raw = resp.content[0].text.strip()
    # 去除可能的 markdown code block
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    log(f'提取結果：{data}')
    return data


def append_to_csv(data):
    """把新數據追加到 records.csv，若當日已存在則跳過，回傳 True=新增 False=已存在"""
    df = pd.read_csv(DATA_FILE) if DATA_FILE.exists() else pd.DataFrame(columns=CSV_COLS)

    record_date = data.get('date', '')
    if not record_date:
        raise ValueError('提取的數據缺少日期')

    if record_date in df['date'].values:
        log(f'日期 {record_date} 已存在，跳過寫入')
        return False

    new_row = {col: data.get(col, '') for col in CSV_COLS}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df = df.sort_values('date').reset_index(drop=True)
    df.to_csv(DATA_FILE, index=False)
    log(f'已寫入 {record_date} 到 records.csv')
    return True


def run_script(script_name):
    script_path = ROOT / 'scripts' / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.returncode != 0:
        log(f'[ERROR] {script_name}:\n{result.stderr}')
        raise RuntimeError(f'{script_name} 失敗')
    log(f'{script_name} 完成')
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            log(f'  {line}')


def main():
    log('=== PLA Tracker 自動更新開始 ===')

    # 1. 抓最新圖片
    img_url = get_mnd_latest_image_url()
    img_bytes, _ = download_image(img_url)

    # 2. 用 Claude 解讀
    data = extract_data_from_image(img_bytes, img_url)

    # 3. 寫入 CSV
    is_new = append_to_csv(data)

    if not is_new:
        log('今日數據已是最新，無需重新產圖')
        # 仍重建網站（以防手動改過 CSS 等）
        run_script('build_site.py')
        log('=== 完成（無新數據）===')
        return

    # 4. 產圖表 PNG
    run_script('chart_daily.py')

    # 5. 重建網站
    run_script('build_site.py')

    log(f'=== 完成：{data["date"]} 數據已更新 ===')


if __name__ == '__main__':
    main()
