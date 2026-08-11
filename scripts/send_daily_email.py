"""
send_daily_email.py — 每日更新後產生文字分析報告並寄送 Email
"""

import os
import re
import smtplib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from pathlib import Path

import anthropic
import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'

GMAIL_FROM = os.environ['GMAIL_FROM']
GMAIL_TO   = os.environ['GMAIL_TO']
GMAIL_PASS = os.environ['GMAIL_APP_PASSWORD']

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; PLA-Tracker/1.0)'}

# 新聞區塊標籤顏色
TAG_COLORS = {
    '台灣': '#5bc8af',
    '美日官方': '#7ec8e8',
    '智庫': '#b89af0',
}

# 中央社國防相關關鍵字
CNA_KEYWORDS = [
    '解放軍', '共機', '共艦', '台海', '軍演', '擾台', 'ADIZ',
    '國防', '軍事', '飛彈', '航母', '東部戰區', '共軍',
    # 國內國防治理／預算爭議（用於「國防內耗並置」貼文角度的素材來源）。
    # 注意：不用「刪減」「凍結」等泛用詞單獨當關鍵字，會撈進大量無關新聞。
    '無人機', '軍購', '潛艦', '洩密', '情資', '中科院',
]


# ── 工具函式 ──────────────────────────────────────────────

def _roc_to_datetime(text: str):
    """解析民國日期，支援兩種格式：
    '115.05.25'（國防部）、'115年05月26日'（總統府）
    """
    m = re.search(r'(\d{2,3})\.(\d{1,2})\.(\d{1,2})', text)
    if m:
        try:
            return datetime(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            pass
    m = re.search(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日', text)
    if m:
        try:
            return datetime(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _western_date(text: str):
    """解析西元日期，支援 '2026/05/26' 和 '2026/5/26'（外交部無補零格式）"""
    m = re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _google_rss(query: str, days: int, hl='en-US', gl='US', ceid='US:en') -> list[dict]:
    """Google News RSS 通用抓取，回傳近 days 天的結果"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={query.replace(' ', '+')}&hl={hl}&gl={gl}&ceid={ceid}"
    )
    results = []
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        for item in root.findall('.//item')[:12]:
            raw_title = item.findtext('title', '').strip()
            pub_str   = item.findtext('pubDate', '')
            link      = item.findtext('link', '')
            src_el    = item.find('source')
            source    = src_el.text.strip() if src_el is not None else ''
            title     = (raw_title[: -len(f' - {source}')]
                         if source and raw_title.endswith(f' - {source}')
                         else raw_title)
            try:
                pub_dt = parsedate_to_datetime(pub_str)
            except Exception:
                continue  # 日期解析失敗，跳過
            if pub_dt < cutoff:
                continue
            results.append({'title': title, 'source': source,
                             'pub': pub_dt.strftime('%Y/%m/%d'), 'link': link})
    except Exception as e:
        print(f'[email] Google RSS 失敗 ({query[:40]}…): {e}')
    return results


# ── 台灣官方來源爬蟲 ──────────────────────────────────────

def _scrape_cna(days: int) -> list[dict]:
    """中央社：全文搜尋後以關鍵字過濾國防相關新聞"""
    cutoff  = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    try:
        resp = requests.get('https://www.cna.com.tw/list/aall.aspx',
                            timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for li in soup.find_all('li'):
            a = li.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title or not any(kw in title for kw in CNA_KEYWORDS):
                continue
            date_span = li.find('span', class_='date')
            pub_dt    = _western_date(date_span.get_text() if date_span else '')
            if not pub_dt or pub_dt < cutoff:
                continue
            href = a['href']
            link = f"https://www.cna.com.tw{href}" if href.startswith('/') else href
            results.append({
                'title': title, 'source': '中央社',
                'pub':   pub_dt.strftime('%Y/%m/%d') if pub_dt else '',
                'link':  link, 'tag': '台灣',
            })
    except Exception as e:
        print(f'[email] 中央社爬取失敗: {e}')
    return results


def _scrape_mnd(days: int) -> list[dict]:
    """國防部新聞稿（民國日期 115.05.25）"""
    cutoff  = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    try:
        resp = requests.get('https://www.mnd.gov.tw/news/mndlist',
                            timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/news/mnd/' not in a['href']:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            parent_text = a.parent.get_text(' ') if a.parent else ''
            pub_dt = _roc_to_datetime(parent_text)
            if not pub_dt or pub_dt < cutoff:
                continue
            href = a['href']
            link = f"https://www.mnd.gov.tw{href}" if href.startswith('/') else href
            results.append({
                'title': title, 'source': '國防部',
                'pub':   pub_dt.strftime('%Y/%m/%d') if pub_dt else '',
                'link':  link, 'tag': '台灣',
            })
    except Exception as e:
        print(f'[email] 國防部新聞爬取失敗: {e}')
    return results


def _scrape_mofa(days: int) -> list[dict]:
    """外交部新聞（西元日期 2026/5/23，無補零）"""
    cutoff  = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    try:
        resp = requests.get('https://www.mofa.gov.tw/News.aspx',
                            timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if 'News_Content.aspx' not in a['href']:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            # 在同層或父層找 span.date
            container = a.parent or a
            date_span = (container.find('span', class_='date')
                         or (container.parent.find('span', class_='date')
                             if container.parent else None))
            pub_dt = _western_date(date_span.get_text() if date_span else '')
            if not pub_dt or pub_dt < cutoff:
                continue
            href = a['href']
            link = (f"https://www.mofa.gov.tw/{href.lstrip('/')}"
                    if not href.startswith('http') else href)
            results.append({
                'title': title, 'source': '外交部',
                'pub':   pub_dt.strftime('%Y/%m/%d') if pub_dt else '',
                'link':  link, 'tag': '台灣',
            })
    except Exception as e:
        print(f'[email] 外交部新聞爬取失敗: {e}')
    return results


def _scrape_president(days: int) -> list[dict]:
    """總統府新聞（民國日期 115年05月26日，標題在 <strong>）"""
    cutoff  = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    try:
        resp = requests.get('https://www.president.gov.tw/NEWS/index',
                            timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/News/' not in a['href']:
                continue
            strong = a.find('strong')
            if not strong:
                continue
            title = strong.get_text(strip=True)
            if not title:
                continue
            pub_dt = _roc_to_datetime(a.get_text(' '))
            if not pub_dt or pub_dt < cutoff:
                continue
            href = a['href']
            link = (f"https://www.president.gov.tw{href}"
                    if href.startswith('/') else href)
            results.append({
                'title': title, 'source': '總統府',
                'pub':   pub_dt.strftime('%Y/%m/%d') if pub_dt else '',
                'link':  link, 'tag': '台灣',
            })
    except Exception as e:
        print(f'[email] 總統府新聞爬取失敗: {e}')
    return results


def _fetch_tw_news(days: int) -> list[dict]:
    """整合四個台灣官方來源"""
    results = []
    results += _scrape_cna(days)
    results += _scrape_mnd(days)
    results += _scrape_mofa(days)
    results += _scrape_president(days)
    return results


# ── 英文來源（Google News RSS）────────────────────────────

def _fetch_intl_official(days: int) -> list[dict]:
    """美日官方 / 軍方聲明"""
    results = []
    for q in ['USINDOPACOM Pentagon China Taiwan military statement',
              'Japan Ministry Defense JSDF China military threat response',
              'US Navy Air Force China Taiwan Indo-Pacific']:
        for r in _google_rss(q, days):
            r['tag'] = '美日官方'
            results.append(r)
    return results


def _fetch_think_tanks(days: int) -> list[dict]:
    """美國智庫研究報告"""
    results = []
    for q in ['"CSIS" OR "RAND Corporation" China Taiwan military',
              '"CFR" OR "Stimson Center" OR "Brookings" China military Taiwan threat',
              '"IISS" OR "Atlantic Council" China Taiwan military PLA']:
        for r in _google_rss(q, days):
            r['tag'] = '智庫'
            results.append(r)
    return results


def fetch_defense_news(days: int = 2) -> list[dict]:
    """整合所有來源，去重後回傳（最多 20 則）"""
    all_news = _fetch_tw_news(days) + _fetch_intl_official(days) + _fetch_think_tanks(days)
    seen, results = set(), []
    for n in all_news:
        if n['title'] not in seen:
            seen.add(n['title'])
            results.append(n)
    return results[:20]


# ── 純 Python 對比（不依賴 LLM，數字保證準確）──────────────

def compute_comparison(df: pd.DataFrame) -> list[dict]:
    """計算今日 vs 昨日的軍機／越線／越線率／艦艇數字與增減。
    昨日無資料（例如歷史回填缺口）時，delta 顯示「—」。
    """
    today = df.iloc[-1]
    has_yesterday = len(df) >= 2
    yesterday = df.iloc[-2] if has_yesterday else None

    fields = [
        ('aircraft_total',    '軍機',   False),
        ('median_line_cross', '越線',   False),
        ('cross_rate',        '越線率', True),
        ('ships_total',       '艦艇',   False),
    ]
    rows = []
    for col, label, is_rate in fields:
        cur = today[col]
        if not has_yesterday or pd.isna(yesterday[col]) or pd.isna(cur):
            rows.append({'label': label,
                         'value': f'{cur:.1f}%' if is_rate else str(int(cur)),
                         'delta': '—'})
            continue
        prev = yesterday[col]
        d = cur - prev
        if is_rate:
            value = f'{cur:.1f}%'
            delta = f'+{d:.1f}%' if d > 0 else (f'{d:.1f}%' if d < 0 else '±0%')
        else:
            cur_i, d_i = int(cur), int(d)
            value = str(cur_i)
            delta = f'+{d_i}' if d_i > 0 else (str(d_i) if d_i < 0 else '±0')
        rows.append({'label': label, 'value': value, 'delta': delta})
    return rows


# ── Claude 分析 ───────────────────────────────────────────

def build_analysis(df: pd.DataFrame, news: list[dict]) -> str:
    today     = df.iloc[-1]
    yesterday = df.iloc[-2]
    last7     = df.tail(7)
    this_mon  = df[df['date'].dt.month == today['date'].month]
    prev_mon  = df[df['date'].dt.month == (today['date'].month - 1)]

    zero_cross_streak = int((last7['median_line_cross'] == 0)[::-1].cumprod().sum())

    summary = {
        "today": {
            "date":         str(today['date'].date()),
            "aircraft":     int(today['aircraft_total']),
            "median_cross": int(today['median_line_cross']),
            "ships":        int(today['ships_total']),
            "type":         today['aircraft_type'],
            "zone":         str(today['special_event']) if pd.notna(today['special_event']) else "無特殊",
        },
        "yesterday": {
            "aircraft": int(yesterday['aircraft_total']),
            "ships":    int(yesterday['ships_total']),
        },
        "last7_avg_aircraft":     round(last7['aircraft_total'].mean(), 1),
        "zero_cross_streak_days": zero_cross_streak,
        "this_month": {
            "days":           len(this_mon),
            "total_aircraft": int(this_mon['aircraft_total'].sum()),
            "total_cross":    int(this_mon['median_line_cross'].sum()),
            "avg_ships":      round(this_mon['ships_total'].mean(), 1),
            "active_days":    int((this_mon['aircraft_total'] > 0).sum()),
            "cross_days":     int((this_mon['median_line_cross'] > 0).sum()),
        },
        "prev_month": {
            "total_aircraft": int(prev_mon['aircraft_total'].sum()),
            "total_cross":    int(prev_mon['median_line_cross'].sum()),
            "avg_ships":      round(prev_mon['ships_total'].mean(), 1),
            "days":           len(prev_mon),
        },
    }

    tw_news   = [n for n in news if n.get('tag') == '台灣']
    intl_news = [n for n in news if n.get('tag') == '美日官方']
    tank_news = [n for n in news if n.get('tag') == '智庫']

    def fmt(items, limit=8):
        return '\n'.join(
            f'[{i+1}] {n["title"]} ——{n["source"]}，{n["pub"]}'
            for i, n in enumerate(items[:limit])
        )

    news_block = ''
    if tw_news:
        news_block += f'\n\n【台灣官方】\n{fmt(tw_news)}'
    if intl_news:
        news_block += f'\n\n【美日官方/軍方】\n{fmt(intl_news)}'
    if tank_news:
        news_block += f'\n\n【美國智庫】\n{fmt(tank_news)}'

    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-5",
            # Sonnet 5 省略 thinking 參數＝預設 adaptive，會吃輸出額度，明確關閉；
            # 新 tokenizer 同樣文字多約三成 token，額度從 2000 提高避免報告被截斷
            max_tokens=3000,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": f"""你是台海情報分析官。你的任務是把今日 PLA 數據與各方新聞整合成一份情報簡報，找出因果關係並做事實查核，並草擬社群貼文。

## 輸入資料

**PLA 數據（來源：中華民國國防部每日公告，為本報告的唯一數據基礎）**
{summary}

**近48小時新聞標題（括號內為來源與日期）**{news_block}

## 輸出要求

用繁體中文，依序寫出以下五節。前四節每個陳述後面必須用「〔來源〕」標注依據（數據請寫「國防部數據」，新聞請寫「[編號] 來源名稱」）；第五節（Threads 貼文建議）不需要標註來源。

---

**情勢摘要**
今日 PLA 動態的客觀描述（2-3句），包含架次、越線、艦艇數字，與昨日及近7日均值比較。

**因果鏈**
找出新聞與數據之間值得並置觀察的事件連結，每條屬於以下兩類之一：
• 因果類：[行為方] 做了什麼〔來源〕 → [回應方] 如何回應〔來源〕（僅在新聞標題可支持明確行動—回應關係時使用）
• 🔗關聯類：🔗關聯：[事件A]〔來源〕與[事件B]〔來源／國防部數據〕時間相近或主題相關，值得並置觀察（不主張因果，只指出關聯）

規則：因果類只寫能在新聞標題中找到依據的行動—回應；只要時間相近或主題相關但無法確認因果，一律改用「🔗關聯」類，不要勉強套用因果語氣（不再使用「⚠️推論」標記於此節，該標記移至下方事實查核）。只有完全找不到任何可並置觀察的新聞事件時，此節才寫「本日無明確可並置事件」。

**美日智庫動向**
美國、日本官方及智庫對當前局勢的立場與動作（2-3條），每條標注新聞來源編號。若新聞中無相關內容，此節省略。

**事實查核**
針對「因果鏈」節中每條陳述，逐一標記：
✅ 確認：因果類陳述，有新聞標題或數據直接支持行動—回應關係
⚠️ 推論：因果類陳述，僅基於時間相關性或情境推斷，無直接聲明
🔗 關聯：關聯類陳述，不主張因果，但引用的新聞標題或數據須確實存在於輸入資料中
（❌ 無法確認者不得出現在分析中；🔗 關聯類條目一律不得虛構未出現在輸入新聞列表中的事件）

**Threads 貼文建議**
草擬 2 則 Threads 貼文草稿（一主一備，語氣或切入角度要不同），供使用者挑選、修改後自行發文。每則內容骨架固定為兩段式並置：

第(1)段——今日共軍「用什麼形式」擾台：不只列數字，要描述形式（例如主力機種、越線架次集中在哪個空域、艦艇規模與活動型態、有無特殊事件），數字一律以上方「情勢摘要」的國防部數據為準，不得與之不符。

第(2)段——台灣國內國防新聞並置：特別是在野黨延宕國防的動態（例如刪減/凍結國防或無人機預算、洩漏軍事情資、阻礙軍工程序如炸藥許可延宕等），事件敘述只能取自輸入新聞標題，不得虛構或寫死沒有來源的具體情節（人名、金額、日期）。若當日輸入新聞中沒有這類國內國防新聞，此段可省略，或改用一句泛稱帶過（例如「國防預算爭議仍在立法院拉鋸」這類不指涉具體情節的說法），不得杜撰事件細節。

通用要求：
- 繁體中文，口語但克制，不要誇張聳動或情緒化用詞
- 不要引入美製武器戰果或武器歷史相關內容（使用者明確要求排除）
- 每則不超過500字（含標點），語氣像資訊帳號分享觀察，不是新聞稿
- 每則結尾另起一行附上：https://pla-tracker.skyfaring.net
- 兩則草稿之間用單獨一行「---」分隔，前後不要加其他文字
- 人名、金額、日期等具體細節，輸入資料中沒有來源就不要寫死"""}],
        )
        # 不寫死 content[0]：模型預設開啟 thinking 時 content[0] 會是 thinking 區塊。
        for block in msg.content:
            if getattr(block, 'type', None) == 'text':
                return block.text
        raise ValueError('Claude 回應中沒有文字區塊')
    except Exception as e:
        print(f'[email] Claude API 分析生成失敗: {e}')
        return '（今日情勢分析與 Threads 貼文草稿產生失敗，請查看 GitHub Actions 執行紀錄）'


# ── 寄信 ──────────────────────────────────────────────────

def comparison_html(rows: list[dict]) -> str:
    """今日 vs 昨日對比列（純 Python 計算結果，與 LLM 分析內容獨立，確保數字可靠）。"""
    if not rows:
        return ''
    items = ''.join(
        f'<span style="margin-right:18px;white-space:nowrap">{r["label"]} '
        f'<b>{r["value"]}</b> '
        f'<span style="color:#8aa0b0;font-size:.85em">（{r["delta"]}）</span></span>'
        for r in rows
    )
    return (
        f'<div style="margin-bottom:14px;padding-bottom:12px;'
        f'border-bottom:1px solid #1a3040;font-size:.92em;line-height:2">'
        f'<span style="color:#8aa0b0;font-size:.78em;display:block;margin-bottom:4px">'
        f'今日 vs 昨日</span>{items}</div>'
    )


def send_email(analysis: str, today_str: str, news: list[dict], comparison: list[dict] | None = None):
    # 標準分隔線 "---"（獨立成行）轉為 <hr>，用於 Threads 貼文草稿之間的視覺分隔。
    analysis_html = re.sub(r'(?m)^\s*---\s*$', '\0HR\0', analysis)
    analysis_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', analysis_html)
    analysis_html = re.sub(r'〔(.+?)〕', r'<span style="color:#556a7a;font-size:.85em">〔\1〕</span>', analysis_html)
    analysis_html = analysis_html.replace(' → ', ' <span style="color:#f5c842">→</span> ')
    analysis_html = analysis_html.replace('✅', '<span style="color:#5bc8af">✅</span>')
    analysis_html = analysis_html.replace('⚠️', '<span style="color:#f5c842">⚠️</span>')
    analysis_html = analysis_html.replace('\n', '<br>').replace('• ', '&bull;&nbsp;')
    analysis_html = analysis_html.replace(
        '\0HR\0', '<hr style="border:none;border-top:1px dashed #234a5a;margin:14px 0">'
    )

    comp_html = comparison_html(comparison or [])

    def news_group_html(tag: str, items: list[dict]) -> str:
        if not items:
            return ''
        color = TAG_COLORS.get(tag, '#aaa')
        rows  = ''.join(
            f'<div style="margin:6px 0;line-height:1.5">'
            f'<a href="{n["link"]}" style="color:#c8d8e8;text-decoration:none">{n["title"]}</a>'
            f'<span style="color:#4a6a7a;font-size:.76em"> &nbsp;{n["source"]} · {n["pub"]}</span>'
            f'</div>'
            for n in items
        )
        return (
            f'<div style="margin-bottom:14px">'
            f'<span style="color:{color};font-size:.75em;font-weight:bold;'
            f'border:1px solid {color};border-radius:3px;padding:1px 6px;'
            f'margin-bottom:6px;display:inline-block">{tag}</span>'
            f'<div style="font-size:.8em;margin-top:4px">{rows}</div>'
            f'</div>'
        )

    tw_news   = [n for n in news if n.get('tag') == '台灣']
    intl_news = [n for n in news if n.get('tag') == '美日官方']
    tank_news = [n for n in news if n.get('tag') == '智庫']

    news_html = ''
    if tw_news or intl_news or tank_news:
        body = (
            news_group_html('台灣', tw_news)
            + news_group_html('美日官方', intl_news)
            + news_group_html('智庫', tank_news)
        )
        news_html = f"""
  <div style="margin-top:20px;border-top:1px solid #1a3040;padding-top:14px">
    <div style="color:#f5c842;font-size:.82em;font-weight:bold;margin-bottom:12px;letter-spacing:.04em">
      近48小時國防相關新聞
    </div>
    {body}
  </div>"""

    html = f"""<html><body style="background:#0a1520;color:#c8d8e8;font-family:'Microsoft JhengHei',Arial,sans-serif;padding:24px 20px;max-width:640px;margin:auto">
  <div style="border-bottom:2px solid #f5c842;padding-bottom:10px;margin-bottom:20px">
    <span style="color:#f5c842;font-size:1.15em;font-weight:bold">PLA 擾台動態 日報</span>
    <span style="color:#8aa0b0;font-size:.85em;margin-left:12px">{today_str}</span>
  </div>
  <div style="background:#0d1b2a;border-left:3px solid #f5c842;padding:16px 20px;border-radius:4px;line-height:1.9;font-size:.95em">
    {comp_html}{analysis_html}
  </div>{news_html}
  <div style="margin-top:16px;font-size:.72em;color:#3a6070;text-align:center">
    資料來源：中華民國國防部 &nbsp;·&nbsp; pla-tracker
  </div>
</body></html>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'PLA 擾台日報 · {today_str}'
    msg['From']    = GMAIL_FROM
    msg['To']      = GMAIL_TO
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_FROM, GMAIL_PASS)
        server.sendmail(GMAIL_FROM, GMAIL_TO, msg.as_string())
    print(f'[email] 已寄送至 {GMAIL_TO}')


# ── 失敗 / 異常通知信 ─────────────────────────────────────

def send_failure_email(reason: str, run_url: str = ''):
    """晚間最終檢查時，若今日仍無資料，寄出說明原因的提醒信（一天最多一封）。"""
    today_str = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')

    run_link = (
        f'<div style="margin-top:14px">'
        f'<a href="{run_url}" style="color:#7ec8e8;text-decoration:none">'
        f'查看 GitHub Actions 執行紀錄 →</a></div>'
        if run_url else ''
    )

    html = f"""<html><body style="background:#0a1520;color:#c8d8e8;font-family:'Microsoft JhengHei',Arial,sans-serif;padding:24px 20px;max-width:640px;margin:auto">
  <div style="border-bottom:2px solid #e05555;padding-bottom:10px;margin-bottom:20px">
    <span style="color:#e05555;font-size:1.15em;font-weight:bold">⚠️ PLA 日報今日未更新</span>
    <span style="color:#8aa0b0;font-size:.85em;margin-left:12px">{today_str} 晚間檢查</span>
  </div>
  <div style="background:#0d1b2a;border-left:3px solid #e05555;padding:16px 20px;border-radius:4px;line-height:1.9;font-size:.95em">
    今日（{today_str}）截至晚間最終檢查仍未取得當日數據。<br><br>
    <b style="color:#e05555">原因：</b>{reason}<br><br>
    若國防部稍後補發布，明日班次會自動補上；若連續多日收到此通知，請手動檢查國防部公告頁面或爬蟲設定。
    {run_link}
  </div>
  <div style="margin-top:16px;font-size:.72em;color:#3a6070;text-align:center">
    pla-tracker 自動通知 · 每日最多一封
  </div>
</body></html>"""

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'⚠️ PLA 日報今日未更新 · {today_str}'
    msg['From']    = GMAIL_FROM
    msg['To']      = GMAIL_TO
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_FROM, GMAIL_PASS)
        server.sendmail(GMAIL_FROM, GMAIL_TO, msg.as_string())
    print(f'[email] 已寄送今日未更新提醒至 {GMAIL_TO}')


# ── 主流程 ────────────────────────────────────────────────

def main():
    # 失敗通知模式：由 workflow 在更新失敗時以 EMAIL_MODE=failure 觸發。
    if os.environ.get('EMAIL_MODE', 'report').lower() == 'failure':
        reason  = os.environ.get('FAILURE_REASON', '未知錯誤，請查看執行紀錄')
        run_url = os.environ.get('RUN_URL', '')
        print('[email] 寄送失敗通知...')
        send_failure_email(reason, run_url)
        return

    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date'])

    today_str = str(df.iloc[-1]['date'].date())
    print(f'[email] 生成 {today_str} 分析報告...')

    print('[email] 抓取國防相關新聞...')
    news  = fetch_defense_news(days=2)
    tw    = sum(1 for n in news if n.get('tag') == '台灣')
    intl  = sum(1 for n in news if n.get('tag') == '美日官方')
    tanks = sum(1 for n in news if n.get('tag') == '智庫')
    print(f'[email] 新聞：台灣 {tw} 則 / 美日官方 {intl} 則 / 智庫 {tanks} 則')

    comparison = compute_comparison(df)
    analysis   = build_analysis(df, news)
    send_email(analysis, today_str, news, comparison)


if __name__ == '__main__':
    main()
