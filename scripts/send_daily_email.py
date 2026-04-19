"""
send_daily_email.py — 每日更新後產生文字分析報告並寄送 Email
"""

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
import pandas as pd

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'

GMAIL_FROM = os.environ['GMAIL_FROM']
GMAIL_TO   = os.environ['GMAIL_TO']
GMAIL_PASS = os.environ['GMAIL_APP_PASSWORD']


def build_analysis(df: pd.DataFrame) -> str:
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

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": f"""你是台海軍事動態分析師。根據以下數據，用繁體中文寫出：
1.「今日觀察」（2-3句，描述今日動態、與昨日相比的變化）
2.「趨勢觀察」（3-4條重點，比較本月 vs 上月，近7日走勢，值得關注的模式）

語氣：客觀、精練、有洞察力。直接給重點，不要廢話。

數據：
{summary}

格式：
**今日觀察**
（內容）

**趨勢觀察**
• （重點）
• （重點）
• （重點）"""}],
    )
    return msg.content[0].text


def send_email(analysis: str, today_str: str):
    analysis_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', analysis)
    analysis_html = analysis_html.replace('\n', '<br>').replace('• ', '&bull;&nbsp;')

    html = f"""<html><body style="background:#0a1520;color:#c8d8e8;font-family:'Microsoft JhengHei',Arial,sans-serif;padding:24px 20px;max-width:640px;margin:auto">
  <div style="border-bottom:2px solid #f5c842;padding-bottom:10px;margin-bottom:20px">
    <span style="color:#f5c842;font-size:1.15em;font-weight:bold">PLA 擾台動態 日報</span>
    <span style="color:#8aa0b0;font-size:.85em;margin-left:12px">{today_str}</span>
  </div>
  <div style="background:#0d1b2a;border-left:3px solid #f5c842;padding:16px 20px;border-radius:4px;line-height:1.9;font-size:.95em">
    {analysis_html}
  </div>
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

    analysis = build_analysis(df)
    send_email(analysis, today_str)


if __name__ == '__main__':
    main()
