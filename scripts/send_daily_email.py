"""
send_daily_email.py — 每日更新後產生分析報告並寄送 Email
"""

import os
import io
import smtplib
import base64
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path

import anthropic
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'

GMAIL_FROM = os.environ['GMAIL_FROM']
GMAIL_TO   = os.environ['GMAIL_TO']
GMAIL_PASS = os.environ['GMAIL_APP_PASSWORD']


# ── 分析文字（Claude API）─────────────────────────────────────────────────────

def build_analysis(df: pd.DataFrame) -> str:
    today_row = df.iloc[-1]
    last7     = df.tail(7)
    apr       = df[df['date'].dt.month == today_row['date'].month]
    prev_mon  = df[df['date'].dt.month == (today_row['date'].month - 1)]

    summary = {
        "today": {
            "date": str(today_row['date'].date()),
            "aircraft": int(today_row['aircraft_total']),
            "median_cross": int(today_row['median_line_cross']),
            "ships": int(today_row['ships_total']),
            "type": today_row['aircraft_type'],
            "zone": str(today_row['special_event']) if pd.notna(today_row['special_event']) else "無特殊",
        },
        "last7_avg_aircraft": round(last7['aircraft_total'].mean(), 1),
        "last7_zero_cross_streak": int((last7['median_line_cross'] == 0).sum()),
        "this_month": {
            "days": len(apr),
            "total_aircraft": int(apr['aircraft_total'].sum()),
            "total_cross": int(apr['median_line_cross'].sum()),
            "avg_ships": round(apr['ships_total'].mean(), 1),
            "active_days": int((apr['aircraft_total'] > 0).sum()),
        },
        "prev_month": {
            "total_aircraft": int(prev_mon['aircraft_total'].sum()),
            "total_cross": int(prev_mon['median_line_cross'].sum()),
            "avg_ships": round(prev_mon['ships_total'].mean(), 1),
        },
    }

    client = anthropic.Anthropic()
    prompt = f"""你是台海軍事動態分析師。根據以下數據，用繁體中文寫出：
1. 「今日觀察」（2-3句，精準描述今日動態與昨日差異）
2. 「趨勢觀察」（3-4條重點，比較本月 vs 上月，近7日走勢，值得關注的模式）

語氣：客觀、精練、有洞察力。不要廢話，直接給重點。

數據：
{summary}

格式：
**今日觀察**
（內容）

**趨勢觀察**
• （重點1）
• （重點2）
• （重點3）
"""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ── 圖表生成 ──────────────────────────────────────────────────────────────────

def build_chart(df: pd.DataFrame) -> bytes:
    plt.rcParams.update({
        'font.family': ['Microsoft JhengHei', 'Noto Sans CJK TC', 'DejaVu Sans'],
        'axes.facecolor': '#0d1b2a', 'figure.facecolor': '#0a1520',
        'text.color': '#c8d8e8', 'axes.labelcolor': '#8aa0b0',
        'xtick.color': '#8aa0b0', 'ytick.color': '#8aa0b0',
        'axes.edgecolor': '#2a4a60',
    })

    last30 = df.tail(30).copy()
    labels = [d.strftime('%m/%d') for d in last30['date']]
    ac = last30['aircraft_total'].values
    cr = last30['median_line_cross'].values
    sh = last30['ships_total'].values
    x  = np.arange(len(labels))

    months   = df.groupby(df['date'].dt.to_period('M'))['aircraft_total'].mean()
    ships_m  = df.groupby(df['date'].dt.to_period('M'))['ships_total'].mean()
    cross_pct = df.groupby(df['date'].dt.to_period('M')).apply(
        lambda d: (d['median_line_cross'] > 0).sum() / len(d) * 100
    )
    m_short = [f"{str(m).split('-')[1]}月" for m in months.index]

    fig = plt.figure(figsize=(14, 10), facecolor='#0a1520')
    gs  = GridSpec(3, 2, figure=fig, hspace=0.5, wspace=0.35)

    def clean(ax):
        for s in ['top', 'right']:
            ax.spines[s].set_visible(False)

    today_str = str(df.iloc[-1]['date'].date())

    # 近30日架次
    ax1 = fig.add_subplot(gs[0, :])
    ax1.bar(x, ac, color='#f5c842', alpha=0.85, width=0.7)
    ax1.bar(x, cr, color='#e05555', alpha=0.9, width=0.7)
    ax1.set_xticks(x[::3]); ax1.set_xticklabels(labels[::3], fontsize=7.5)
    ax1.set_title('近30日 軍機架次', fontsize=11, color='#c8d8e8', pad=8)
    ax1.axhline(ac.mean(), color='#f5c842', linestyle='--', alpha=0.35, linewidth=1)
    ax1.legend(handles=[
        mpatches.Patch(color='#f5c842', alpha=0.85, label='總架次'),
        mpatches.Patch(color='#e05555', alpha=0.9,  label='越中線'),
    ], fontsize=8, framealpha=0.15, labelcolor='white', loc='upper right')
    clean(ax1)

    # 月均架次
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(range(len(months)), months.values, color='#f5c842', lw=2, marker='o', ms=5)
    ax2.fill_between(range(len(months)), months.values, alpha=0.15, color='#f5c842')
    ax2.set_xticks(range(len(months))); ax2.set_xticklabels(m_short, fontsize=9)
    ax2.set_title('月均軍機架次', fontsize=10, color='#c8d8e8', pad=6)
    clean(ax2)

    # 月均艦艇
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(range(len(ships_m)), ships_m.values, color='#e05555', lw=2, marker='s', ms=5)
    ax3.fill_between(range(len(ships_m)), ships_m.values, alpha=0.15, color='#e05555')
    ax3.set_xticks(range(len(ships_m))); ax3.set_xticklabels(m_short, fontsize=9)
    ax3.set_title('月均艦艇（艘）', fontsize=10, color='#c8d8e8', pad=6)
    clean(ax3)

    # 月越線比例
    ax4 = fig.add_subplot(gs[2, 0])
    colors_b = ['#4a7a9b'] * (len(cross_pct) - 1) + ['#f5c842']
    ax4.bar(range(len(cross_pct)), cross_pct.values, color=colors_b, alpha=0.85)
    ax4.set_xticks(range(len(cross_pct))); ax4.set_xticklabels(m_short, fontsize=9)
    ax4.set_title('月越線天數比例（%）', fontsize=10, color='#c8d8e8', pad=6)
    ax4.set_ylim(0, 100)
    clean(ax4)

    # 近30日艦艇
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.fill_between(range(len(sh)), sh, alpha=0.3, color='#e05555')
    ax5.plot(range(len(sh)), sh, color='#e05555', lw=1.5)
    ax5.set_xticks(range(0, len(sh), 3)); ax5.set_xticklabels(labels[::3], fontsize=7.5)
    ax5.set_title('近30日 艦艇數量', fontsize=10, color='#c8d8e8', pad=6)
    ax5.set_ylim(0, max(sh) + 3)
    clean(ax5)

    fig.suptitle(f'PLA 擾台動態 日報  {today_str}', fontsize=14,
                 color='#f5c842', y=0.98, fontweight='bold')
    fig.text(0.5, 0.005, 'Data: ROC MND  ·  pla-tracker',
             ha='center', fontsize=7, color='#3a6070')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor='#0a1520')
    plt.close()
    buf.seek(0)
    return buf.read()


# ── 組裝並寄送 Email ──────────────────────────────────────────────────────────

def send_email(analysis: str, chart_bytes: bytes, today_str: str):
    msg = MIMEMultipart('related')
    msg['Subject'] = f'PLA 擾台日報 · {today_str}'
    msg['From']    = GMAIL_FROM
    msg['To']      = GMAIL_TO

    analysis_html = analysis.replace('\n', '<br>').replace('**', '<b>', 1)
    # simple bold replacement
    import re
    analysis_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', analysis)
    analysis_html = analysis_html.replace('\n', '<br>').replace('• ', '&bull; ')

    html = f"""
<html><body style="background:#0a1520;color:#c8d8e8;font-family:'Microsoft JhengHei',sans-serif;padding:24px;max-width:700px;margin:auto">
  <div style="border-bottom:2px solid #f5c842;padding-bottom:8px;margin-bottom:20px">
    <span style="color:#f5c842;font-size:1.1em;font-weight:bold">PLA 擾台動態 日報</span>
    <span style="color:#8aa0b0;font-size:.85em;margin-left:12px">{today_str}</span>
    <span style="background:#1a2a3a;color:#8aa0b0;font-size:.65em;padding:2px 8px;border-radius:3px;margin-left:8px">UNCLASSIFIED // OPEN SOURCE</span>
  </div>

  <div style="background:#0d1b2a;border-left:3px solid #f5c842;padding:14px 18px;border-radius:4px;margin-bottom:20px;line-height:1.8">
    {analysis_html}
  </div>

  <img src="cid:chart" style="width:100%;border-radius:6px;display:block">

  <div style="margin-top:14px;font-size:.72em;color:#3a6070;text-align:center">
    資料來源：中華民國國防部 &nbsp;·&nbsp; pla-tracker
  </div>
</body></html>
"""

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(html, 'html', 'utf-8'))
    msg.attach(alt)

    img = MIMEImage(chart_bytes, name='chart.png')
    img.add_header('Content-ID', '<chart>')
    img.add_header('Content-Disposition', 'inline', filename='chart.png')
    msg.attach(img)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_FROM, GMAIL_PASS)
        server.sendmail(GMAIL_FROM, GMAIL_TO, msg.as_string())
    print(f'[email] 已寄送至 {GMAIL_TO}')


# ── 主程式 ───────────────────────────────────────────────────────────────────

def main():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date'])

    today_str = str(df.iloc[-1]['date'].date())
    print(f'[email] 生成 {today_str} 分析報告...')

    analysis   = build_analysis(df)
    chart_bytes = build_chart(df)
    send_email(analysis, chart_bytes, today_str)


if __name__ == '__main__':
    main()
