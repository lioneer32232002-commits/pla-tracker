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
import re
import sys
import json
import time
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

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PLA-Tracker/1.0)'}

# 重試設定：MND 伺服器偶有暫時性 5xx / 連線錯誤，需重試而非直接失敗
HTTP_RETRIES = 4          # 最多嘗試次數
HTTP_BACKOFF = 3          # 退避基數秒數（3, 6, 12, …）

# 欄位順序與 records.csv 一致
CSV_COLS = [
    'date', 'aircraft_total', 'median_line_cross', 'cross_rate',
    'aircraft_type', 'ships_total', 'activity_start', 'activity_end',
    'special_event'
]

# 欄位提取規格：圖片與文字兩種來源共用同一份規則，確保兩條路徑結果一致。
_EXTRACT_SPEC = """提取以下資訊並以 JSON 格式回答。

注意：
- 「報告日期」是公告標示的統計結束日期。日期欄常寫成「民國X年A月B日…時至民國X年C月D日…0600時止」，date 取「結束日」（例：「…至115年6月18日…0600時止」→ 2026-06-18；圖片若僅標注「3月20日」→ 2026-03-20）
- aircraft_total：共機架次總數（整數；公告稱「未偵獲共機」則為 0）
- median_line_cross：逾越海峽中線的架次數（整數，若無則 0）
- cross_rate：越線率百分比（數字，不含%符號；若無共機則留空字串）
- aircraft_type：機型分類，只能是以下之一：Manned / UAV / Mixed / Zero / Helicopter
  - Manned = 只有有人戰機/轟炸機/輔戰機
  - UAV = 只有無人機
  - Mixed = 有人機＋無人機混合，或有人機＋直升機
  - Zero = 零架次
  - Helicopter = 只有直升機（無戰機）
- ships_total：公告中標示的解放軍軍艦（含海警公務船）總艘數（整數）。
  請仔細查看「軍艦」「共艦」「海警」「艦艇」等相關數字，將所有類型艦艇合計。
  此欄位必填，若公告明確有標示艦艇數字請務必填入；真的完全無法辨識才填 0。
- activity_start：共機活動最早時間（HH:MM 格式，無則空字串）
- activity_end：共機活動最晚時間（HH:MM 格式，無則空字串）
- special_event：活動區域與機型詳情，格式「區域名(①機型N架次) 區域名(②機型N架次)」，
  例：「西南部空域(①無人機2架) 東北部空域(②輔戰機3架次)」。
  若無共機活動或無法判斷區域，填空字串。
  注意：「上述期間未偵獲共機，故無提供航跡圖」等例行說明文字請填空字串。

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

# 圖片來源（有航跡圖的日子）
EXTRACT_PROMPT = (
    '你是軍事數據分析員。請仔細閱讀這張中華民國國防部每日共機動態公告圖片，' + _EXTRACT_SPEC
)

# 文字來源（零架次等無航跡圖的日子，改讀公告內文）
EXTRACT_PROMPT_TEXT = (
    '你是軍事數據分析員。以下提供中華民國國防部每日共機動態公告的內文文字，請仔細閱讀並' + _EXTRACT_SPEC
)


def log(msg):
    print(f'[fetch] {msg}', flush=True)


def set_output(key, value):
    """寫入 GitHub Actions step output，供 workflow 後續步驟判斷本次結果。

    本機（無 GITHUB_OUTPUT 環境變數）執行時靜默略過。同一 key 多次寫入時，
    GitHub 以最後一筆為準。
    """
    out_file = os.environ.get('GITHUB_OUTPUT')
    if not out_file:
        return
    safe = str(value).replace('\n', ' ').strip()
    with open(out_file, 'a', encoding='utf-8') as f:
        f.write(f'{key}={safe}\n')


def http_get(url, *, retries=HTTP_RETRIES, backoff=HTTP_BACKOFF, **kwargs):
    """帶重試與退避的 GET。

    對暫時性錯誤（連線/逾時例外、HTTP 5xx、429）重試，因為 MND 的圖片伺服器
    偶爾會回 500。最後一次仍失敗才把例外往上拋。
    """
    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 30)
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, **kwargs)
            if resp.status_code >= 500 or resp.status_code == 429:
                raise requests.exceptions.HTTPError(
                    f'{resp.status_code} Server Error for url: {url}', response=resp)
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                wait = backoff * (2 ** (attempt - 1))
                log(f'下載失敗（第 {attempt}/{retries} 次）：{exc}；{wait}s 後重試')
                time.sleep(wait)
            else:
                log(f'下載失敗（已達最大重試 {retries} 次）：{exc}')
    raise last_exc


def abs_url(href):
    """把相對連結補成絕對網址。"""
    if href.startswith('http'):
        return href
    if not href.startswith('/'):
        href = '/' + href
    return MND_BASE_URL + href


def get_mnd_latest_article():
    """從 MND 共機動態列表頁取得最新一筆公告，回傳 (article_url, soup)。"""
    resp = http_get(MND_LIST_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 找最新一筆公告連結。
    # MND 共機動態公告網址為 /news/plaact/<id>，id 隨發布時間遞增，故「id 最大者 = 最新」。
    # 不能只取 DOM 中第一個連結——版面可能把較舊的精選/相關公告排在前面，
    # 導致抓到舊資料（例如最新是 06-07，卻抓成 06-06）。
    plaact_links = {}  # id -> 絕對網址
    for a in soup.find_all('a', href=True):
        m = re.search(r'plaact/(\d+)', a['href'], re.IGNORECASE)
        if m:
            plaact_links[int(m.group(1))] = abs_url(a['href'])

    if not plaact_links:
        raise RuntimeError('找不到共機動態公告連結')

    latest_id = max(plaact_links)
    article_link = plaact_links[latest_id]
    log(f'公告頁面（最新 id={latest_id}）：{article_link}')

    resp2 = http_get(article_link)
    soup2 = BeautifulSoup(resp2.text, 'html.parser')
    return article_link, soup2


def find_image_url(soup2):
    """從公告頁 soup 找航跡圖 URL。無航跡圖（如零架次日）時回傳 None。"""

    def is_image_src(src):
        """判斷 src 是否可能是圖片（有副檔名或是 /File/ 路徑）"""
        has_ext = any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
        is_file_path = re.search(r'/[Ff]ile/\d+', src)
        return has_ext or bool(is_file_path)

    def check_image_size(url, min_bytes=50_000):
        """確認圖片大小 > min_bytes，支援 HEAD 405 時改用 GET Range"""
        try:
            r = requests.head(url, headers=HEADERS, timeout=10)
            if r.status_code == 405:
                # 伺服器不支援 HEAD，改用 GET 只取前幾 bytes
                r = requests.get(url, headers={**HEADERS, 'Range': 'bytes=0-1023'}, timeout=10)
                cl = r.headers.get('content-range', '')
                # Content-Range: bytes 0-1023/TOTAL
                m = re.search(r'/(\d+)$', cl)
                if m:
                    return int(m.group(1)) > min_bytes
                # 無法確認大小，假設夠大（/File/ 路徑通常是正式圖片）
                return True
            return int(r.headers.get('content-length', 0)) > min_bytes
        except Exception:
            return False

    img_url = None

    # 優先：找 <a href="File/N"> 下載連結（MND 新版頁面格式）
    for a in soup2.find_all('a', href=True):
        href = a['href']
        if re.search(r'[Ff]ile/\d+', href):
            img_url = abs_url(href)
            break

    # 次選：<img src> 含 /File/ 或 /upload/ 等路徑
    if not img_url:
        for img in soup2.find_all('img', src=True):
            src = img['src']
            if is_image_src(src):
                if ('plaact' in src.lower() or 'military' in src.lower()
                        or '/upload' in src.lower() or re.search(r'/[Ff]ile/\d+', src)):
                    img_url = abs_url(src)
                    break

    # 備用：找最大的圖片（排除 icon/logo/無障礙標章等小圖）
    EXCLUDE_PATTERNS = ['logo', 'icon', 'banner', 'header', 'AA2', 'AA1', 'wcag', 'accessib']
    if not img_url:
        for img in soup2.find_all('img', src=True):
            src = img['src']
            if is_image_src(src):
                if not any(x in src for x in EXCLUDE_PATTERNS):
                    candidate_url = abs_url(src)
                    if check_image_size(candidate_url):
                        img_url = candidate_url
                        break

    if not img_url:
        return None

    log(f'圖片 URL：{img_url}')
    return img_url


def extract_article_text(soup2):
    """擷取公告內文純文字（div.maincontent）。抓不到回傳空字串。"""
    node = soup2.select_one('div.maincontent') or soup2.select_one('main')
    return node.get_text('\n', strip=True) if node else ''


def looks_like_bulletin(text):
    """判斷內文是否為一則正式的共機動態公告（用來區分「零架次無圖公告」與「尚未發布」）。"""
    if not text:
        return False
    return '時止' in text and ('共機' in text or '共艦' in text)


def download_image(url):
    """下載圖片，回傳 (bytes, cache_path)，若已快取則直接讀快取"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    raw_ext = url.split('?')[0].rsplit('.', 1)[-1].lower()
    # 確保 ext 是合法副檔名（不含斜線、長度合理），否則預設 jpg
    ext = raw_ext if raw_ext and '/' not in raw_ext and len(raw_ext) <= 5 else 'jpg'
    cache_path = CACHE_DIR / f'{url_hash}.{ext}'

    if cache_path.exists():
        log(f'使用快取：{cache_path.name}')
        return cache_path.read_bytes(), cache_path

    resp = http_get(url)
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

    return _parse_claude_json(resp)


def extract_data_from_text(article_text):
    """用 Claude API 解讀公告內文文字，回傳 dict（零架次等無航跡圖的日子使用）"""
    client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    log('呼叫 Claude API 解讀公告內文…')
    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=512,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'text',
                 'text': f'{EXTRACT_PROMPT_TEXT}\n\n公告內文：\n{article_text}'}
            ]
        }]
    )
    return _parse_claude_json(resp)


def _parse_claude_json(resp):
    """從 Claude 回應取出 JSON dict（去除可能的 markdown code block 包裝）。"""
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

    # 1. 取最新公告頁，再找航跡圖
    article_url, soup2 = get_mnd_latest_article()
    img_url = find_image_url(soup2)

    if img_url is None:
        # 無航跡圖。國防部在「未偵獲共機（零架次）」的日子不附航跡圖，
        # 但內文仍載有共艦等數據——改讀內文文字，不要誤判為尚未發布。
        article_text = extract_article_text(soup2)
        if not looks_like_bulletin(article_text):
            # 內文也不是有效公告 → 才視為今日尚未發布，交由後續班次重試，不寄通知信。
            log('找不到航跡圖，且內文非有效公告，今日公告可能尚未發布')
            log('=== 今日公告尚未發布，結束 ===')
            set_output('outcome', 'unpublished')
            return
        log('公告無航跡圖（多為零架次），改用內文文字解讀')
        data = extract_data_from_text(article_text)
    else:
        # 圖片下載已內建重試；若 MND 伺服器持續回 5xx（暫時性故障），
        # 不讓整個流程崩潰退出——視為「稍後再試」，交由下一個排程班次重跑，
        # 並回報 source_error 讓 workflow 寄出失敗通知信。
        try:
            img_bytes, _ = download_image(img_url)
        except requests.exceptions.RequestException as exc:
            log(f'圖片下載最終失敗（MND 伺服器暫時性錯誤）：{exc}')
            log('=== 今日圖片暫時無法取得，留待下一班次重試，結束 ===')
            set_output('outcome', 'source_error')
            set_output('error_detail', f'國防部圖片伺服器無法下載：{exc}')
            return

        # 2. 用 Claude 解讀圖片
        data = extract_data_from_image(img_bytes, img_url)

    # 3. 寫入 CSV
    is_new = append_to_csv(data)

    if not is_new:
        # 當日資料已存在（典型為備援班次）→ 不再寄信，避免重複通知。
        set_output('outcome', 'exists')
        if os.environ.get('FORCE_REBUILD', 'false').lower() != 'true':
            log('今日數據已是最新，無需重建')
            run_script('build_site.py')
            log('=== 完成（無新數據）===')
            return
        log('FORCE_REBUILD=true，強制重建網站')

    # 4. 重建網站（Chart.js，不需產 PNG）
    run_script('build_site.py')

    if is_new:
        # 唯一會觸發每日報告信的路徑：確實新增了當日資料。
        set_output('outcome', 'new')
        set_output('record_date', str(data.get('date', '')))
    log(f'=== 完成：{data["date"]} 數據已更新 ===')


if __name__ == '__main__':
    # 任何未預期的例外都記錄成 outcome=error 並附原因，讓 workflow 寄出失敗通知，
    # 同時以非零退出碼讓該班次標記為失敗。
    try:
        main()
    except Exception as exc:
        set_output('outcome', 'error')
        set_output('error_detail', f'{type(exc).__name__}: {exc}')
        raise
