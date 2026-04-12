"""
build_site.py — 讀取 records.csv，產出靜態網站
"""
import json
import shutil
from pathlib import Path
import pandas as pd

ROOT       = Path(__file__).parent.parent
DATA_FILE  = ROOT / 'data' / 'records.csv'
CHARTS_DIR = ROOT / 'output' / 'charts'
SITE_DIR   = ROOT          # GitHub Pages 從 repo 根目錄 / (root) 提供
SITE_DIR.mkdir(exist_ok=True)
SITE_CHARTS = SITE_DIR / 'charts'
SITE_CHARTS.mkdir(exist_ok=True)


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def load_df():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def fmt_date(date_str):
    """YYYY-MM-DD → M/D（無年份）"""
    dt = pd.to_datetime(date_str)
    return f"{dt.month}/{dt.day}"


def sync_charts():
    for f in CHARTS_DIR.glob('*.png'):
        dest = SITE_CHARTS / f.name
        if not dest.exists() or f.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(f, dest)


def section_data(df, today_date):
    """回傳 (labels, ac_vals, sh_vals, today_idx)"""
    labels   = [fmt_date(r['date']) for _, r in df.iterrows()]
    ac_vals  = [int(r['aircraft_total'])  if pd.notna(r['aircraft_total'])  else 0 for _, r in df.iterrows()]
    sh_vals  = [int(r['ships_total'])     if pd.notna(r['ships_total'])     else 0 for _, r in df.iterrows()]
    idx_list = df[df['date'] == today_date].index.tolist()
    today_idx = int(idx_list[0]) if idx_list else -1
    return labels, ac_vals, sh_vals, today_idx


def delta_span(cur, prev_val):
    try:
        d = float(cur) - float(prev_val)
        if d == 0: return ''
        arrow = '▲' if d > 0 else '▼'
        cls   = 'delta-up' if d > 0 else 'delta-dn'
        return f'<span class="{cls}">{arrow}{abs(d):.0f}</span>'
    except Exception:
        return ''


# ── CSS ───────────────────────────────────────────────────────────────────────

def build_css():
    css = """\
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap');

:root{
  --bg:#090d0f; --sur:#0e1618; --bdr:#1a2830;
  --y:#f5c842;  --r:#e05555;
  --tx:#c4d4dc; --sub:#4a6070; --grn:#4dba6a;
  --rad:6px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px}
body{background:var(--bg);color:var(--tx);
  font-family:'Noto Sans TC','Microsoft JhengHei',system-ui,-apple-system,sans-serif;
  font-weight:500;min-height:100vh}

/* ── Top bar ── */
.top-bar{background:#04070a;border-bottom:1px solid var(--bdr);
  padding:.3rem 1.5rem;display:flex;justify-content:space-between;
  font-size:.6rem;letter-spacing:.13em;text-transform:uppercase;color:var(--sub)}

/* ── Header ── */
.site-header{border-bottom:1px solid var(--bdr);padding:.85rem 1.5rem}
.header-inner{max-width:900px;margin:0 auto;display:flex;
  align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.site-title{font-size:1.15rem;font-weight:800;letter-spacing:-.01em}
.site-sub{font-size:.65rem;color:var(--sub);letter-spacing:.05em;margin-top:.1rem}
nav{display:flex;gap:1.5rem}
nav a{color:var(--sub);text-decoration:none;font-size:.72rem;
  font-weight:700;letter-spacing:.09em;text-transform:uppercase}
nav a.active,nav a:hover{color:var(--tx)}

/* ── Main ── */
main{max-width:900px;margin:0 auto;padding:1.5rem}

/* ── Alert ── */
.alert{background:#140f00;border:1px solid #2e2100;
  border-left:3px solid var(--y);color:var(--y);
  padding:.6rem 1rem;border-radius:var(--rad);
  font-size:.83rem;font-weight:700;margin-bottom:2rem;letter-spacing:.02em}

/* ── SITREP ── */
.sitrep{margin-bottom:2.5rem}
.sitrep-label{font-size:.6rem;text-transform:uppercase;letter-spacing:.16em;
  color:var(--sub);margin-bottom:1.5rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.sitrep-label::after{content:'';flex:1;min-width:30px;height:1px;background:var(--bdr)}

/* ── Stats ── */
.stats-row{display:grid;grid-template-columns:repeat(3,1fr)}
.stat{padding:0 1.5rem}
.stat:first-child{padding-left:0}
.stat:last-child{padding-right:0}
.stat+.stat{border-left:1px solid var(--bdr)}
.stat-n{font-size:3.2rem;font-weight:800;line-height:1;
  letter-spacing:-.04em;font-variant-numeric:tabular-nums}
.y{color:var(--y)}
.r{color:var(--r)}
.stat-l{font-size:.58rem;text-transform:uppercase;letter-spacing:.11em;
  color:var(--sub);margin-top:.45rem}
.stat-detail{font-size:.75rem;color:var(--sub);margin-top:.2rem}
.delta-up{display:block;font-size:.7rem;color:var(--r);margin-top:.28rem;font-weight:700}
.delta-dn{display:block;font-size:.7rem;color:var(--grn);margin-top:.28rem;font-weight:700}

/* ── Badge ── */
.badge{display:inline-block;padding:.18em .6em;border-radius:3px;font-size:.78rem;font-weight:700}
.badge.manned    {background:#152b0c;color:#7ed46a}
.badge.uav       {background:#0d1d2e;color:#6aaee0}
.badge.mixed     {background:#272008;color:var(--y)}
.badge.zero      {background:var(--sur);color:var(--sub);border:1px solid var(--bdr)}
.badge.helicopter{background:#20143a;color:#b898dc}

/* ── Chart sections ── */
.chart-section{margin-bottom:2rem}
.chart-header{display:flex;align-items:baseline;flex-wrap:wrap;
  gap:.5rem 1rem;margin-bottom:.75rem;
  padding-bottom:.5rem;border-bottom:1px solid var(--bdr)}
.chart-title{font-size:.72rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.15em;color:var(--sub);white-space:nowrap}
.chart-obs{font-size:.95rem;color:var(--y);font-weight:600}
.chart-img{display:block;width:100%;height:auto;border-radius:var(--rad)}
.chart-missing{background:var(--sur);border:1px dashed var(--bdr);
  border-radius:var(--rad);padding:2rem;text-align:center;
  color:var(--sub);font-size:.78rem}

/* ── Records table ── */
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.8rem;white-space:nowrap}
th{background:var(--sur);color:var(--sub);padding:.55rem .8rem;text-align:left;
   border-bottom:1px solid var(--bdr);font-size:.6rem;text-transform:uppercase;letter-spacing:.08em}
td{padding:.5rem .8rem;border-bottom:1px solid var(--bdr);color:var(--tx);vertical-align:middle}
tr:hover td{background:#0e1a20}
.num{text-align:right;font-variant-numeric:tabular-nums}
.special-cell{color:var(--sub);font-size:.74rem;max-width:200px;white-space:normal}

/* ── Footer ── */
footer{border-top:1px solid var(--bdr);padding:1rem 1.5rem;margin-top:1rem;
  display:flex;flex-wrap:wrap;gap:.5rem 2rem;
  font-size:.65rem;color:var(--sub);letter-spacing:.05em}
footer a{color:var(--sub);text-decoration:none}
footer a:hover{color:var(--tx)}

/* ── Mobile ── */
@media(max-width:640px){
  .top-bar{display:none}
  .site-header{padding:.7rem 1rem}
  main{padding:1rem}
  .stats-row{grid-template-columns:repeat(3,1fr);gap:0}
  .stat{padding:0 .75rem}
  .stat:first-child{border-left:none;padding-left:0}
  .stat-n{font-size:2.3rem}
  footer{padding:.75rem 1rem}
}
@media(max-width:380px){.stat-n{font-size:1.9rem}}
"""
    (SITE_DIR / 'style.css').write_text(css, encoding='utf-8')
    print('[OK] style.css')


HEAD = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中國擾台趨勢數據分析</title>
<link rel="stylesheet" href="style.css">
</head>"""


def find_latest_chart(prefix):
    """找 charts/ 下最新的 {prefix}_YYYY-MM-DD.png，回傳相對路徑或 None"""
    matches = sorted(SITE_CHARTS.glob(f'{prefix}_????-??-??.png'), reverse=True)
    if matches:
        return f'charts/{matches[0].name}'
    # fallback: output/charts
    matches = sorted(CHARTS_DIR.glob(f'{prefix}_????-??-??.png'), reverse=True)
    if matches:
        return f'charts/{matches[0].name}'
    return None


def nav_html(active='index'):
    links = [('index.html','總覽'), ('records.html','每日紀錄')]
    items = ''.join(f'<a href="{h}"{"" if active!=h.split(".")[0] else " class=active"}>{t}</a>'
                    for h,t in links)
    return f'<nav>{items}</nav>'


def footer_html(update_label):
    return f"""<footer>
  <span>資料來源：<a href="https://www.mnd.gov.tw/news/plaactlist" target="_blank">中華民國國防部</a></span>
  <span>製作：Adam Pan</span>
  <span>更新：{update_label}</span>
</footer>"""


def chart_section(title, img_path, obs=''):
    inner = (f'<img class="chart-img" src="{img_path}" alt="{title}">'
             if img_path else '<div class="chart-missing">（圖表尚未產生）</div>')
    return f"""  <section class="chart-section">
    <div class="chart-header">
      <span class="chart-title">{title}</span>
    </div>
    {inner}
  </section>"""


def monthly_stats_html(df, today_date):
    """本月至今統計區塊"""
    month_prefix = today_date[:7]
    df_mo = df[df['date'].str.startswith(month_prefix)].copy()
    if df_mo.empty:
        return ''
    mo_ac  = int(df_mo['aircraft_total'].fillna(0).sum())
    mo_cr  = int(df_mo['median_line_cross'].fillna(0).sum())
    mo_sh_avg = df_mo['ships_total'].fillna(0).mean()
    days   = len(df_mo)
    mo_label = f"{pd.to_datetime(today_date).month}月"

    cr_rate = f"{mo_cr/mo_ac*100:.0f}%" if mo_ac > 0 else '—'

    return f"""<div class="sitrep" style="margin-top:2.5rem">
    <div class="sitrep-label">{mo_label}至今 &nbsp;·&nbsp; {days} 天</div>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-n y">{mo_ac}</div>
        <div class="stat-l">共機架次</div>
      </div>
      <div class="stat">
        <div class="stat-n y">{mo_cr}</div>
        <div class="stat-l">越中線</div>
        <div class="stat-detail">{cr_rate}</div>
      </div>
      <div class="stat">
        <div class="stat-n r">{mo_sh_avg:.1f}</div>
        <div class="stat-l">艦艇日均</div>
        <div class="stat-detail">艘</div>
      </div>
    </div>
  </div>"""


# ── index.html ────────────────────────────────────────────────────────────────

def build_index(df):
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    today_date   = latest['date']
    today_label  = fmt_date(today_date)
    update_label = today_label

    ac_val  = int(latest['aircraft_total'])    if pd.notna(latest['aircraft_total'])    else 0
    ml_val  = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    sh_val  = int(latest['ships_total'])       if pd.notna(latest['ships_total'])       else 0
    cr_str  = (f"{float(latest['cross_rate']):.0f}%"
               if str(latest['cross_rate']) not in ('', 'nan') else '—')
    atype   = latest['aircraft_type'] if pd.notna(latest['aircraft_type']) else '—'
    special = latest['special_event'] if str(latest['special_event']) not in ('', 'nan') else ''

    ac_delta = delta_span(latest['aircraft_total'], prev['aircraft_total'])
    sh_delta = delta_span(latest['ships_total'], prev['ships_total'])

    type_lower = atype.lower() if atype != '—' else 'zero'
    type_label = {'zero':'零架次','manned':'有人機','uav':'UAV',
                  'mixed':'混合','helicopter':'直升機'}.get(type_lower, atype)

    split_img  = find_latest_chart('split')
    streak_img = find_latest_chart('streak')

    df_mo = df[df['date'].str.startswith(today_date[:7])].reset_index(drop=True)
    mo_max = int(df_mo['aircraft_total'].max()) if len(df_mo) else 0
    mo_max_d = fmt_date(df_mo.loc[df_mo['aircraft_total'].idxmax(), 'date']) if mo_max > 0 else ''
    sh_lo = int(df['ships_total'].min())
    sh_hi = int(df['ships_total'].max())

    split_obs  = f"今日 {ac_val} 架次　{sh_val} 艘艦艇" + (f"　{special}" if special else "")
    streak_obs = (f"本月峰值 {mo_max} 架次（{mo_max_d}）　艦艇 {sh_lo}–{sh_hi} 艘"
                  if mo_max > 0 else f"艦艇 {sh_lo}–{sh_hi} 艘")

    html = f"""{HEAD}
<body>
<div class="top-bar">
  <span>UNCLASSIFIED // OPEN SOURCE</span>
  <span>ROC MND · {today_label}</span>
</div>
<header class="site-header">
  <div class="header-inner">
    <div class="site-brand">
      <div class="site-title">中國擾台趨勢數據分析</div>
      <div class="site-sub">PLA Activity Around Taiwan</div>
    </div>
    {nav_html('index')}
  </div>
</header>

<main>
  {"<div class='alert'>⚡ " + special + "</div>" if special else ""}

  <div class="sitrep">
    <div class="sitrep-label">SITREP &nbsp;·&nbsp; {today_label} &nbsp;·&nbsp; <span class="badge {type_lower}">{type_label}</span></div>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-n y">{ac_val}</div>
        <div class="stat-l">共機架次</div>
        {ac_delta}
      </div>
      <div class="stat">
        <div class="stat-n y">{ml_val}</div>
        <div class="stat-l">逾越中線</div>
        <div class="stat-detail">{cr_str}</div>
      </div>
      <div class="stat">
        <div class="stat-n r">{sh_val}</div>
        <div class="stat-l">解放軍艦艇</div>
        {sh_delta}
      </div>
    </div>
  </div>

  {monthly_stats_html(df, today_date)}

  {chart_section("10日觀察", split_img)}
  {chart_section("近期趨勢", streak_img)}

</main>

<footer>
  <span>資料來源：<a href="https://www.mnd.gov.tw/news/plaactlist" target="_blank">中華民國國防部</a></span>
  <span>製作：Adam Pan</span>
  <span>更新：{update_label}</span>
</footer>
</body></html>"""

    (SITE_DIR / 'index.html').write_text(html, encoding='utf-8')
    print('[OK] index.html')


# ── records.html ──────────────────────────────────────────────────────────────

def build_records(df):
    rows = ''
    for _, row in df.sort_values('date', ascending=False).iterrows():
        cr    = (f"{float(row['cross_rate']):.0f}%"
                 if str(row['cross_rate']) not in ('', 'nan') else '—')
        atype = row['aircraft_type'] if pd.notna(row['aircraft_type']) else '—'
        spec  = row['special_event'] if str(row['special_event']) not in ('', 'nan') else ''
        ac    = int(row['aircraft_total']) if pd.notna(row['aircraft_total']) else 0
        sh    = int(row['ships_total'])    if pd.notna(row['ships_total'])    else 0
        ml    = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
        label = fmt_date(row['date'])
        tl    = atype.lower() if atype != '—' else 'zero'
        type_zh = {'zero':'零','manned':'有人機','uav':'UAV',
                   'mixed':'混合','helicopter':'直升機'}.get(tl, atype)
        rows += f"""<tr>
      <td>{label}</td>
      <td class="num yellow">{ac}</td>
      <td class="num">{ml}</td>
      <td class="num">{cr}</td>
      <td><span class="badge {tl}">{type_zh}</span></td>
      <td class="num red">{sh}</td>
      <td class="special-cell">{spec}</td>
    </tr>"""

    today_label = fmt_date(df.iloc[-1]['date'])
    html = f"""{HEAD}
<body>
<header class="site-header">
  <div class="header-inner">
    <div>
      <h1 class="site-title">中國擾台趨勢數據分析</h1>
      <p class="site-meta">每日紀錄　共 {len(df)} 筆</p>
    </div>
    {nav_html('records')}
  </div>
</header>

<main>
  <div class="tbl-wrap">
  <table>
    <thead><tr>
      <th>日期</th><th>架次</th><th>越線</th><th>越線率</th>
      <th>機型</th><th>艦艇</th><th>備註</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</main>

{footer_html(today_label)}
</body></html>"""

    (SITE_DIR / 'records.html').write_text(html, encoding='utf-8')
    print('[OK] records.html')


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    df = load_df()
    sync_charts()
    build_index(df)
    build_records(df)
    print('[DONE] Site built →', SITE_DIR)
