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
    css = """
:root{
  --bg:#1e2224; --bg-card:#111c20; --border:#2a3336;
  --yellow:#f5c842; --yellow-dim:#8a7020; --yellow-zero:#3a4448;
  --red:#e05555; --red-dim:#7a2a2a;
  --text:#dce8ec; --sub:#7a9298; --fade:#3e5258;
  --radius:8px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px}
body{
  background:var(--bg);color:var(--text);
  font-family:system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;
  font-weight:600;line-height:1.5;min-height:100vh
}

/* ── Header ── */
.site-header{background:var(--bg-card);border-bottom:1px solid var(--border);padding:.9rem 1.25rem}
.header-inner{max-width:860px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
.site-title{font-size:1.15rem;font-weight:800;letter-spacing:-.01em}
.site-meta{font-size:.78rem;color:var(--sub);margin-top:.15rem}
nav{display:flex;gap:1.25rem}
nav a{color:var(--sub);text-decoration:none;font-size:.82rem;font-weight:700}
nav a:hover{color:var(--text)}

/* ── Main ── */
main{max-width:860px;margin:0 auto;padding:1.25rem}

/* ── Special event ── */
.special-banner{
  background:#222216;border:1px solid #4a4010;
  color:var(--yellow);padding:.55rem .9rem;border-radius:var(--radius);
  font-size:.85rem;font-weight:700;margin-bottom:1.1rem
}

/* ── Stats cards ── */
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.65rem;margin-bottom:1.75rem}
.stat-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:.85rem .95rem}
.stat-label{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--sub);margin-bottom:.35rem}
.stat-val{font-size:2rem;font-weight:800;line-height:1}
.stat-sub{font-size:.75rem;color:var(--sub);margin-top:.25rem}
.stat-type{margin-top:.35rem}
.yellow{color:var(--yellow)}
.red{color:var(--red)}
.delta-up{display:block;font-size:.72rem;color:#ff7070;margin-top:.2rem}
.delta-dn{display:block;font-size:.72rem;color:#6fd96f;margin-top:.2rem}

/* ── Type badge ── */
.badge{display:inline-block;padding:.18em .6em;border-radius:4px;font-size:.82rem;font-weight:700}
.badge.manned    {background:#1e3a14;color:#80d96a}
.badge.uav       {background:#14293d;color:#6ab0e0}
.badge.mixed     {background:#382e10;color:var(--yellow)}
.badge.zero      {background:var(--bg);color:var(--fade);border:1px solid var(--border)}
.badge.helicopter{background:#2a1a40;color:#c09adc}

/* ── Sections ── */
.section{margin-bottom:1.75rem}
.section-title{
  font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;
  color:var(--sub);margin-bottom:.75rem;padding-bottom:.45rem;border-bottom:1px solid var(--border)
}
.chart-block{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:.85rem .95rem .75rem;margin-bottom:.55rem
}
.chart-lbl{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem}
.chart-lbl.ac{color:var(--yellow)}
.chart-lbl.sh{color:var(--red)}
.chart-wrap{position:relative;height:148px}

/* ── Footer ── */
footer{
  background:var(--bg-card);border-top:1px solid var(--border);
  padding:.9rem 1.25rem;font-size:.75rem;color:var(--fade);
  display:flex;flex-wrap:wrap;gap:.3rem 1.25rem;align-items:center
}
footer a{color:var(--sub);text-decoration:none}
footer a:hover{color:var(--text)}

/* ── Records table ── */
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{width:100%;border-collapse:collapse;font-size:.82rem;white-space:nowrap}
th{background:var(--bg-card);color:var(--sub);padding:.6rem .75rem;text-align:left;
   border-bottom:1px solid var(--border);font-size:.65rem;text-transform:uppercase;letter-spacing:.06em}
td{padding:.55rem .75rem;border-bottom:1px solid var(--border);color:var(--text);vertical-align:middle}
tr:hover td{background:#1c2628}
.num{text-align:right;font-variant-numeric:tabular-nums}
.special-cell{color:var(--sub);font-size:.76rem;max-width:200px;white-space:normal}

/* ── Mobile ── */
@media(max-width:640px){
  .stats-grid{grid-template-columns:repeat(2,1fr)}
  .stat-val{font-size:1.75rem}
  .site-title{font-size:1rem}
  .chart-wrap{height:120px}
  main{padding:1rem}
  .site-header{padding:.75rem 1rem}
  footer{padding:.75rem 1rem}
}
@media(max-width:360px){
  .stats-grid{grid-template-columns:repeat(2,1fr)}
  .stat-val{font-size:1.5rem}
}
"""
    (SITE_DIR / 'style.css').write_text(css, encoding='utf-8')
    print('[OK] style.css')


# ── Chart.js 共用 JS ──────────────────────────────────────────────────────────

CHART_JS = """
const Y  = '#f5c842', Yd = '#8a7020', Yz = '#3a4448';
const R  = '#e05555', Rd = '#7a2a2a';
const GR = '#2a3336', TX = '#dce8ec', TS = '#7a9298';

function acR(v, mx){ return v===0?4:Math.max(4,Math.min(18,4+(Math.log1p(v)/Math.log1p(mx||1))*14)); }
function shR(v, mn, mx){ return mx===mn?8:5+((v-mn)/(mx-mn))*10; }

function makeAC(id, labels, vals, ti){
  const mx=Math.max(...vals,1);
  new Chart(document.getElementById(id),{
    type:'line',
    data:{labels,datasets:[{
      data:vals, showLine:false,
      pointStyle:'circle',
      pointRadius:vals.map(v=>acR(v,mx)),
      pointHoverRadius:vals.map(v=>acR(v,mx)+3),
      pointBackgroundColor:vals.map((v,i)=>i===ti?Y:(v===0?Yz:Yd)),
      pointBorderWidth:0
    }]},
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:400},
      plugins:{
        legend:{display:false},
        tooltip:{backgroundColor:'#111c20',titleColor:Y,bodyColor:TX,
          callbacks:{label:it=>it.parsed.y+' 架次'}}
      },
      scales:{
        x:{grid:{color:GR},ticks:{
          color:ctx=>ctx.index===ti?TX:TS,
          font:{size:10,weight:'700'},maxRotation:0,autoSkip:true,maxTicksLimit:16
        }},
        y:{min:0,suggestedMax:mx*1.35,grid:{color:GR},ticks:{
          color:Y,font:{size:10,weight:'600'},maxTicksLimit:4
        }}
      }
    }
  });
}

function makeSH(id, labels, vals, ti){
  const mx=Math.max(...vals,1), mn=Math.min(...vals);
  new Chart(document.getElementById(id),{
    type:'line',
    data:{labels,datasets:[{
      data:vals, showLine:false,
      pointStyle:'rectRot',
      pointRadius:vals.map(v=>shR(v,mn,mx)),
      pointHoverRadius:vals.map(v=>shR(v,mn,mx)+3),
      pointBackgroundColor:vals.map((v,i)=>i===ti?R:Rd),
      pointBorderWidth:0
    }]},
    options:{
      responsive:true, maintainAspectRatio:false,
      animation:{duration:400},
      plugins:{
        legend:{display:false},
        tooltip:{backgroundColor:'#111c20',titleColor:R,bodyColor:TX,
          callbacks:{label:it=>it.parsed.y+' 艘'}}
      },
      scales:{
        x:{grid:{color:GR},ticks:{
          color:ctx=>ctx.index===ti?TX:TS,
          font:{size:10,weight:'700'},maxRotation:0,autoSkip:true,maxTicksLimit:16
        }},
        y:{min:0,suggestedMax:mx*1.35,grid:{color:GR},ticks:{
          color:R,font:{size:10,weight:'600'},maxTicksLimit:4
        }}
      }
    }
  });
}
"""

HEAD = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中國擾台趨勢數據分析</title>
<link rel="stylesheet" href="style.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
</head>"""


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


def chart_section(title, ac_id, sh_id):
    return f"""
  <section class="section">
    <div class="section-title">{title}</div>
    <div class="chart-block">
      <div class="chart-lbl ac">● 共機架次</div>
      <div class="chart-wrap"><canvas id="{ac_id}"></canvas></div>
    </div>
    <div class="chart-block">
      <div class="chart-lbl sh">◆ 解放軍艦艇</div>
      <div class="chart-wrap"><canvas id="{sh_id}"></canvas></div>
    </div>
  </section>"""


# ── index.html ────────────────────────────────────────────────────────────────

def build_index(df):
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    today_date  = latest['date']
    today_label = fmt_date(today_date)
    update_dt   = pd.to_datetime(today_date)
    update_label = f"{update_dt.month}/{update_dt.day}"

    # 今日數字
    ac_val  = int(latest['aircraft_total'])  if pd.notna(latest['aircraft_total'])  else 0
    ml_val  = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    sh_val  = int(latest['ships_total'])     if pd.notna(latest['ships_total'])     else 0
    cr_str  = (f"{float(latest['cross_rate']):.0f}%"
               if str(latest['cross_rate']) not in ('', 'nan') else '—')
    atype   = latest['aircraft_type'] if pd.notna(latest['aircraft_type']) else '—'
    special = latest['special_event'] if str(latest['special_event']) not in ('', 'nan') else ''

    ac_delta = delta_span(latest['aircraft_total'], prev['aircraft_total'])
    sh_delta = delta_span(latest['ships_total'], prev['ships_total'])

    type_lower = atype.lower() if atype != '—' else 'zero'
    type_label = {'zero':'零架次','manned':'有人機','uav':'UAV',
                  'mixed':'混合','helicopter':'直升機'}.get(type_lower, atype)

    # 三段資料
    df_apr = df[df['date'].str.startswith('2026-04')].reset_index(drop=True)
    df_mar = df[df['date'].str.startswith('2026-03')].reset_index(drop=True)
    df_ytd = df.reset_index(drop=True)

    al, aa, as_, ai = section_data(df_apr, today_date)
    ml, ma, ms, mi  = section_data(df_mar, today_date)
    yl, ya, ys, yi  = section_data(df_ytd, today_date)

    js_calls = f"""
makeAC('aprAC',{json.dumps(al)},{json.dumps(aa)},{ai});
makeSH('aprSH',{json.dumps(al)},{json.dumps(as_)},{ai});
makeAC('marAC',{json.dumps(ml)},{json.dumps(ma)},{mi});
makeSH('marSH',{json.dumps(ml)},{json.dumps(ms)},{mi});
makeAC('ytdAC',{json.dumps(yl)},{json.dumps(ya)},{yi});
makeSH('ytdSH',{json.dumps(yl)},{json.dumps(ys)},{yi});
"""

    html = f"""{HEAD}
<body>
<header class="site-header">
  <div class="header-inner">
    <div>
      <h1 class="site-title">中國擾台趨勢數據分析</h1>
      <p class="site-meta">最新資料：{today_label}　<span class="badge {type_lower}">{type_label}</span></p>
    </div>
    {nav_html('index')}
  </div>
</header>

<main>
  {"<div class='special-banner'>⚡ " + special + "</div>" if special else ""}

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">共機架次</div>
      <div class="stat-val yellow">{ac_val}</div>
      {ac_delta}
    </div>
    <div class="stat-card">
      <div class="stat-label">逾越中線</div>
      <div class="stat-val yellow">{ml_val}</div>
      <div class="stat-sub">{cr_str}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">解放軍艦艇</div>
      <div class="stat-val red">{sh_val}</div>
      {sh_delta}
    </div>
    <div class="stat-card">
      <div class="stat-label">機型</div>
      <div class="stat-type"><span class="badge {type_lower}">{type_label}</span></div>
    </div>
  </div>

  {chart_section("四月至今", "aprAC", "aprSH")}
  {chart_section("三月趨勢", "marAC", "marSH")}
  {chart_section("2026 年至今", "ytdAC", "ytdSH")}

</main>

{footer_html(update_label)}

<script>
{CHART_JS}
{js_calls}
</script>
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
    build_css()
    build_index(df)
    build_records(df)
    print('[DONE] Site built →', SITE_DIR)
