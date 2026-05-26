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
                pub_dt    = parsedate_to_datetime(pub_str)
                if pub_dt < cutoff:
                    continue
                pub_label = pub_dt.strftime('%m/%d %H:%M')
            except Exception:
                pub_label = ''
            results.append({'title': title, 'source': source,
                             'pub': pub_label, 'link': link})
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
            if pub_dt and pub_dt < cutoff:
                continue
            href = a['href']
            link = f"https://www.cna.com.tw{href}" if href.startswith('/') else href
            results.append({
                'title': title, 'source': '中央社',
                'pub':   pub_dt.strftime('%m/%d') if pub_dt else '',
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
            if pub_dt and pub_dt < cutoff:
                continue
            href = a['href']
            link = f"https://www.mnd.gov.tw{href}" if href.startswith('/') else href
            results.append({
                'title': title, 'source': '國防部',
                'pub':   pub_dt.strftime('%m/%d') if pub_dt else '',
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
            if pub_dt and pub_dt < cutoff:
                continue
            href = a['href']
            link = (f"https://www.mofa.gov.tw/{href.lstrip('/')}"
                    if not href.startswith('http') else href)
            results.append({
                'title': title, 'source': '外交部',
                'pub':   pub_dt.strftime('%m/%d') if pub_dt else '',
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
            if pub_dt and pub_dt < cutoff:
                continue
            href = a['href']
            link = (f"https://www.president.gov.tw{href}"
                    if href.startswith('/') else href)
            results.append({
                'title': title, 'source': '總統府',
                'pub':   pub_dt.strftime('%m/%d') if pub_dt else '',
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

    def fmt(items):
        return '\n'.join(f'- {n["title"]} ({n["source"]}, {n["pub"]})' for n in items[:6])

    news_context = ''
    if tw_news or intl_news or tank_news:
        news_context = '\n\n近48小時新聞（參考用）：'
        if tw_news:
            news_context += f'\n[台灣官方]\n{fmt(tw_news)}'
        if intl_news:
            news_context += f'\n[美日官方/軍方]\n{fmt(intl_news)}'
        if tank_news:
            news_context += f'\n[美國智庫]\n{fmt(tank_news)}'

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": f"""你是台海軍事動態分析師。根據以下數據，用繁體中文寫出：
1.「今日觀察」（2-3句，描述今日動態、與昨日相比的變化）
2.「趨勢觀察」（3-4條重點，比較本月 vs 上月，近7日走勢，值得關注的模式）
3.「國際反應」（從新聞中找出美日官方/軍方聲明、智庫報告對中國軍事威脅的評論，摘要2-3句；若無相關內容則省略此節，不可捏造）

語氣：客觀、精練、有洞察力。直接給重點，不要廢話。

數據：
{summary}{news_context}

格式：
**今日觀察**
（內容）

**趨勢觀察**
• （重點）
• （重點）
• （重點）

**國際反應**（有相關新聞才寫）
（內容）"""}],
    )
    return msg.content[0].text


# ── 寄信 ──────────────────────────────────────────────────

def send_email(analysis: str, today_str: str, news: list[dict]):
    analysis_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', analysis)
    analysis_html = analysis_html.replace('\n', '<br>').replace('• ', '&bull;&nbsp;')

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
    {analysis_html}
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


# ── 主流程 ────────────────────────────────────────────────

def main():
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

    analysis = build_analysis(df, news)
    send_email(analysis, today_str, news)


if __name__ == '__main__':
    main()
