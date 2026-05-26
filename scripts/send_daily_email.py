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

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'

GMAIL_FROM = os.environ['GMAIL_FROM']
GMAIL_TO   = os.environ['GMAIL_TO']
GMAIL_PASS = os.environ['GMAIL_APP_PASSWORD']

# Google News RSS 搜尋關鍵字組合
NEWS_QUERIES = [
    "PLA China military Taiwan strait",
    "US Japan official China military threat response",
    "USINDOPACOM Pentagon China Taiwan",
    "Japan SDF JSDF China military",
]


def fetch_defense_news(days: int = 2) -> list[dict]:
    """從 Google News RSS 抓取近 days 天的國防相關新聞"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    results = []
    seen = set()

    for q in NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search"
            f"?q={q.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
        )
        try:
            resp = requests.get(
                url, timeout=15,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; PLA-Tracker/1.0)'}
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)

            for item in root.findall('.//item')[:12]:
                raw_title = item.findtext('title', '').strip()
                pub_str   = item.findtext('pubDate', '')
                link      = item.findtext('link', '')
                src_el    = item.find('source')
                source    = src_el.text.strip() if src_el is not None else ''

                # 去掉 Google News 標題結尾的 " - Publisher"
                if source and raw_title.endswith(f' - {source}'):
                    title = raw_title[: -len(f' - {source}')]
                else:
                    title = raw_title

                if not title or title in seen:
                    continue

                try:
                    pub_dt    = parsedate_to_datetime(pub_str)
                    if pub_dt < cutoff:
                        continue
                    pub_label = pub_dt.strftime('%m/%d %H:%M')
                except Exception:
                    pub_label = ''

                seen.add(title)
                results.append({
                    'title':  title,
                    'source': source,
                    'pub':    pub_label,
                    'link':   link,
                })

        except Exception as e:
            print(f'[email] 新聞抓取失敗 ({q[:40]}): {e}')

    return results[:15]


def build_analysis(df: pd.DataFrame, news: list[dict]) -> str:
    today     = df.iloc[-1]
    yesterday = df.iloc[-2]
    last7     = df.tail(7)
    this_mon  = df[df['date'].dt.month == today['date'].month]
    prev_mon  = df[df['date'].dt.month == (today['date'].month - 1)]

    zero_cross_streak = int((last7['median_line_cross'] == 0)[::-1].cumprod().sum())

    summary = {
        "today": {
            "date": str(today['date'].date()),
            "aircraft": int(today['aircraft_total']),
            "median_cross": int(today['median_line_cross']),
            "ships": int(today['ships_total']),
            "type": today['aircraft_type'],
            "zone": str(today['special_event']) if pd.notna(today['special_event']) else "無特殊",
        },
        "yesterday": {
            "aircraft": int(yesterday['aircraft_total']),
            "ships": int(yesterday['ships_total']),
        },
        "last7_avg_aircraft": round(last7['aircraft_total'].mean(), 1),
        "zero_cross_streak_days": zero_cross_streak,
        "this_month": {
            "days": len(this_mon),
            "total_aircraft": int(this_mon['aircraft_total'].sum()),
            "total_cross": int(this_mon['median_line_cross'].sum()),
            "avg_ships": round(this_mon['ships_total'].mean(), 1),
            "active_days": int((this_mon['aircraft_total'] > 0).sum()),
            "cross_days": int((this_mon['median_line_cross'] > 0).sum()),
        },
        "prev_month": {
            "total_aircraft": int(prev_mon['aircraft_total'].sum()),
            "total_cross": int(prev_mon['median_line_cross'].sum()),
            "avg_ships": round(prev_mon['ships_total'].mean(), 1),
            "days": len(prev_mon),
        },
    }

    news_context = ''
    if news:
        items = '\n'.join(
            f'- {n["title"]} ({n["source"]}, {n["pub"]})' for n in news[:12]
        )
        news_context = f"\n\n近48小時國際國防新聞標題（參考用）：\n{items}"

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        messages=[{"role": "user", "content": f"""你是台海軍事動態分析師。根據以下數據，用繁體中文寫出：
1.「今日觀察」（2-3句，描述今日動態、與昨日相比的變化）
2.「趨勢觀察」（3-4條重點，比較本月 vs 上月，近7日走勢，值得關注的模式）
3.「國際反應」（從提供的新聞標題中，找出美國或日本官方/軍方對中國軍事威脅的評論或動作，摘要2-3句；若無相關新聞則省略此節，不要捏造）

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

**國際反應**（若有相關新聞才寫）
（內容）"""}],
    )
    return msg.content[0].text


def send_email(analysis: str, today_str: str, news: list[dict]):
    analysis_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', analysis)
    analysis_html = analysis_html.replace('\n', '<br>').replace('• ', '&bull;&nbsp;')

    news_html = ''
    if news:
        items_html = ''.join(
            f'<div style="margin:7px 0;line-height:1.5">'
            f'<a href="{n["link"]}" style="color:#7ec8e8;text-decoration:none">{n["title"]}</a>'
            f'<span style="color:#4a6a7a;font-size:.78em">'
            f' &nbsp;{n["source"]} · {n["pub"]}'
            f'</span></div>'
            for n in news
        )
        news_html = f"""
  <div style="margin-top:20px;border-top:1px solid #1a3040;padding-top:14px">
    <div style="color:#f5c842;font-size:.82em;font-weight:bold;margin-bottom:10px;letter-spacing:.04em">
      近48小時國防相關新聞
    </div>
    <div style="font-size:.8em">{items_html}</div>
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


def main():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date'])

    today_str = str(df.iloc[-1]['date'].date())
    print(f'[email] 生成 {today_str} 分析報告...')

    print('[email] 抓取國防相關新聞...')
    news = fetch_defense_news(days=2)
    print(f'[email] 取得 {len(news)} 則新聞')

    analysis = build_analysis(df, news)
    send_email(analysis, today_str, news)


if __name__ == '__main__':
    main()
