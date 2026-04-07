"""
build_site.py — 讀取 records.csv，產出靜態網站三頁
"""
import json
import shutil
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA_FILE  = ROOT / 'data' / 'records.csv'
CHARTS_DIR = ROOT / 'output' / 'charts'
SITE_DIR   = ROOT          # GitHub Pages 從 repo 根目錄 / (root) 提供
SITE_DIR.mkdir(exist_ok=True)

# 把 charts 複製到 repo 根目錄下的 charts/
SITE_CHARTS = SITE_DIR / 'charts'
SITE_CHARTS.mkdir(exist_ok=True)

def load_df():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df = df.sort_values('date').reset_index(drop=True)
    return df


def sync_charts():
    for f in CHARTS_DIR.glob('*.png'):
        dest = SITE_CHARTS / f.name
        if not dest.exists() or f.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(f, dest)


def df_to_json(df):
    return json.dumps(df.fillna('').to_dict(orient='records'), ensure_ascii=False)


COMMON_HEAD = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PLA Taiwan Strait Tracker</title>
<link rel="stylesheet" href="style.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
</head>"""

NAV = """<nav>
  <a href="index.html">Dashboard</a>
  <a href="records.html">Daily Records</a>
  <a href="monthly.html">Monthly Analysis</a>
</nav>"""


def build_index(df):
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    # 近30天
    df30 = df.tail(30)
    labels_js  = json.dumps(list(df30['date']))
    ac_data_js = json.dumps(list(df30['aircraft_total'].astype(int)))
    sh_data_js = json.dumps(list(df30['ships_total'].astype(int)))
    cross_js   = json.dumps([float(x) if x != '' else None
                              for x in df30['cross_rate'].fillna('').tolist()])

    # 最新圖表
    latest_split  = f"charts/split_{latest['date']}.png"
    latest_streak = f"charts/streak_{latest['date']}.png"
    split_exists  = (SITE_CHARTS / f"split_{latest['date']}.png").exists()
    streak_exists = (SITE_CHARTS / f"streak_{latest['date']}.png").exists()

    def delta(val, prev_val, unit='', fmt='{:+.0f}'):
        try:
            d = float(val) - float(prev_val)
            arrow = '▲' if d > 0 else ('▼' if d < 0 else '—')
            cls   = 'up' if d > 0 else ('down' if d < 0 else 'flat')
            return f'<span class="delta {cls}">{arrow} {abs(d):.0f}{unit}</span>'
        except Exception:
            return ''

    ac_val   = int(latest['aircraft_total']) if pd.notna(latest['aircraft_total']) else 0
    cr_val   = f"{float(latest['cross_rate']):.1f}%" if str(latest['cross_rate']) not in ('', 'nan') else '—'
    sh_val   = int(latest['ships_total']) if pd.notna(latest['ships_total']) else 0
    ml_val   = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    atype    = latest['aircraft_type'] if pd.notna(latest['aircraft_type']) else '—'
    special  = latest['special_event'] if str(latest['special_event']) not in ('', 'nan') else ''

    html = f"""{COMMON_HEAD}
<body>
{NAV}
<main>
  <section class="hero">
    <h1>PLA Taiwan Strait Tracker</h1>
    <p class="subtitle">Latest: <strong>{latest['date']}</strong></p>
    {"<p class='special-event'>⚡ " + special + "</p>" if special else ""}
  </section>

  <section class="cards">
    <div class="card yellow">
      <div class="card-label">AIRCRAFT SORTIES</div>
      <div class="card-value">{ac_val}</div>
      {delta(latest['aircraft_total'], prev['aircraft_total'])}
    </div>
    <div class="card yellow-dim">
      <div class="card-label">MEDIAN LINE CROSS</div>
      <div class="card-value">{ml_val}</div>
      <div class="card-sub">{cr_val} cross rate</div>
    </div>
    <div class="card red">
      <div class="card-label">PLAN SHIPS</div>
      <div class="card-value">{sh_val}</div>
      {delta(latest['ships_total'], prev['ships_total'])}
    </div>
    <div class="card dim">
      <div class="card-label">AIRCRAFT TYPE</div>
      <div class="card-value type-badge {atype.lower()}">{atype}</div>
    </div>
  </section>

  <section class="chart-section">
    <h2>30-Day Trend</h2>
    <div class="chart-wrap">
      <canvas id="trendChart" height="120"></canvas>
    </div>
  </section>

  <section class="chart-section">
    <h2>Latest Chart</h2>
    <div class="chart-imgs">
      {"<img src='" + latest_split  + "' class='chart-img' alt='Split panel chart'>" if split_exists  else ""}
      {"<img src='" + latest_streak + "' class='chart-img' alt='Streak chart'>"      if streak_exists else ""}
      {"<p class='no-chart'>No charts generated yet. Run: python scripts/chart_daily.py</p>" if not split_exists and not streak_exists else ""}
    </div>
  </section>
</main>

<script>
const labels = {labels_js};
const acData  = {ac_data_js};
const shData  = {sh_data_js};
const crData  = {cross_js};

const ctx = document.getElementById('trendChart').getContext('2d');
new Chart(ctx, {{
  type: 'bar',
  data: {{
    labels,
    datasets: [
      {{
        label: 'Aircraft Sorties',
        data: acData,
        backgroundColor: acData.map((v,i) => i === acData.length-1 ? '#f5c842' : (v===0 ? '#3a4448' : '#8a7020')),
        yAxisID: 'yAc',
        order: 2,
      }},
      {{
        label: 'PLAN Ships',
        data: shData,
        type: 'line',
        borderColor: '#e05555',
        backgroundColor: '#e0555540',
        pointBackgroundColor: shData.map((v,i) => i === shData.length-1 ? '#e05555' : '#7a2a2a'),
        pointRadius: shData.map((v,i) => i === shData.length-1 ? 6 : 4),
        yAxisID: 'ySh',
        order: 1,
        tension: 0.3,
      }}
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ labels: {{ color: '#dce8ec', font: {{ size: 13 }} }} }},
      tooltip: {{ backgroundColor: '#111c20', titleColor: '#f5c842', bodyColor: '#dce8ec' }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#7a9298', maxRotation: 45, font: {{ size: 11 }} }}, grid: {{ color: '#2a3336' }} }},
      yAc: {{
        type: 'linear', position: 'left',
        ticks: {{ color: '#f5c842' }}, grid: {{ color: '#2a3336' }},
        title: {{ display: true, text: 'Aircraft Sorties', color: '#f5c842' }}
      }},
      ySh: {{
        type: 'linear', position: 'right',
        ticks: {{ color: '#e05555' }}, grid: {{ drawOnChartArea: false }},
        title: {{ display: true, text: 'Ships', color: '#e05555' }}
      }}
    }}
  }}
}});
</script>
</body></html>"""
    (SITE_DIR / 'index.html').write_text(html, encoding='utf-8')
    print('[OK] index.html')


def build_records(df):
    rows_html = ''
    for _, row in df.sort_values('date', ascending=False).iterrows():
        cr    = f"{float(row['cross_rate']):.1f}%" if str(row['cross_rate']) not in ('', 'nan') else '—'
        atype = row['aircraft_type'] if pd.notna(row['aircraft_type']) else '—'
        spec  = row['special_event'] if str(row['special_event']) not in ('', 'nan') else ''
        ac    = int(row['aircraft_total']) if pd.notna(row['aircraft_total']) else 0
        sh    = int(row['ships_total']) if pd.notna(row['ships_total']) else 0
        ml    = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
        split_img = f"charts/split_{row['date']}.png"
        has_img   = (SITE_CHARTS / f"split_{row['date']}.png").exists()
        rows_html += f"""
    <tr class="{'has-img' if has_img else ''}">
      <td>{row['date']}</td>
      <td class="num yellow">{ac}</td>
      <td class="num">{ml}</td>
      <td class="num">{cr}</td>
      <td><span class="type-badge {atype.lower()}">{atype}</span></td>
      <td class="num red">{sh}</td>
      <td>{row.get('activity_start','') or ''}</td>
      <td>{row.get('activity_end','') or ''}</td>
      <td class="special">{spec}</td>
      <td>{"<a href='" + split_img + "' target='_blank'>📊</a>" if has_img else ''}</td>
    </tr>"""

    html = f"""{COMMON_HEAD}
<body>
{NAV}
<main>
  <section class="hero">
    <h1>Daily Records</h1>
    <p class="subtitle">{len(df)} records total</p>
  </section>
  <section class="table-section">
    <div class="table-wrap">
    <table id="recordsTable">
      <thead>
        <tr>
          <th>Date</th>
          <th>Aircraft</th>
          <th>Cross Line</th>
          <th>Cross Rate</th>
          <th>Type</th>
          <th>Ships</th>
          <th>Start</th>
          <th>End</th>
          <th>Special Event</th>
          <th>Chart</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>
    </div>
  </section>
</main>
</body></html>"""
    (SITE_DIR / 'records.html').write_text(html, encoding='utf-8')
    print('[OK] records.html')


def build_monthly(df):
    months = sorted(df['date'].str[:7].unique(), reverse=True)

    month_sections = ''
    for m in months:
        mdf = df[df['date'].str.startswith(m)].copy()
        avg_ac  = mdf['aircraft_total'].mean()
        max_ac  = mdf['aircraft_total'].max()
        avg_sh  = mdf['ships_total'].mean()
        cr_vals = pd.to_numeric(mdf['cross_rate'], errors='coerce')
        avg_cr  = cr_vals.mean()
        days_ac = (mdf['aircraft_total'] > 0).sum()

        # 縮圖列表
        imgs = ''
        for _, row in mdf.sort_values('date').iterrows():
            p = SITE_CHARTS / f"streak_{row['date']}.png"
            if p.exists():
                ac_v = int(row['aircraft_total']) if pd.notna(row['aircraft_total']) else 0
                imgs += f"""<div class="thumb">
  <img src="charts/streak_{row['date']}.png" alt="{row['date']}">
  <div class="thumb-label">{row['date']}<br>{ac_v} sorties</div>
</div>"""

        month_sections += f"""
<section class="month-section">
  <h2>{m}</h2>
  <div class="month-stats">
    <div class="stat"><span class="stat-label">Avg Sorties/Day</span><span class="stat-val yellow">{avg_ac:.1f}</span></div>
    <div class="stat"><span class="stat-label">Peak Day</span><span class="stat-val yellow">{int(max_ac)}</span></div>
    <div class="stat"><span class="stat-label">Active Days</span><span class="stat-val">{days_ac}/{len(mdf)}</span></div>
    <div class="stat"><span class="stat-label">Avg Ships</span><span class="stat-val red">{avg_sh:.1f}</span></div>
    <div class="stat"><span class="stat-label">Avg Cross Rate</span><span class="stat-val">{avg_cr:.1f}%</span></div>
  </div>
  <div class="thumbs">{imgs or '<p class=no-chart>No charts yet.</p>'}</div>
</section>"""

    html = f"""{COMMON_HEAD}
<body>
{NAV}
<main>
  <section class="hero">
    <h1>Monthly Analysis</h1>
  </section>
  {month_sections}
</main>
</body></html>"""
    (SITE_DIR / 'monthly.html').write_text(html, encoding='utf-8')
    print('[OK] monthly.html')


def build_css():
    css = """
:root {
  --bg:        #1e2224;
  --bg-sub:    #111c20;
  --divider:   #2a3336;
  --yellow:    #f5c842;
  --yellow-dim:#8a7020;
  --red:       #e05555;
  --red-dim:   #7a2a2a;
  --text:      #dce8ec;
  --text-sub:  #7a9298;
  --text-fade: #3e5258;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }

nav { background: var(--bg-sub); border-bottom: 1px solid var(--divider); padding: .8rem 2rem; display: flex; gap: 2rem; }
nav a { color: var(--text-sub); text-decoration: none; font-size: .95rem; transition: color .2s; }
nav a:hover { color: var(--text); }

main { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }

.hero { margin-bottom: 2rem; }
.hero h1 { font-size: 2rem; font-weight: 700; color: var(--text); }
.subtitle { color: var(--text-sub); margin-top: .3rem; }
.special-event { margin-top: .5rem; color: var(--yellow); font-weight: 600; }

/* Cards */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }
.card { background: var(--bg-sub); border: 1px solid var(--divider); border-radius: 8px; padding: 1.2rem; }
.card-label { font-size: .75rem; color: var(--text-sub); text-transform: uppercase; letter-spacing: .06em; margin-bottom: .4rem; }
.card-value { font-size: 2.4rem; font-weight: 700; line-height: 1; }
.card-sub { font-size: .85rem; color: var(--text-sub); margin-top: .3rem; }
.card.yellow .card-value { color: var(--yellow); }
.card.yellow-dim .card-value { color: var(--yellow-dim); }
.card.red .card-value { color: var(--red); }
.card.dim .card-value { color: var(--text-sub); }

.delta { font-size: .85rem; margin-top: .3rem; display: block; }
.delta.up   { color: #ff6b6b; }
.delta.down { color: #51cf66; }
.delta.flat { color: var(--text-fade); }

/* Type badges */
.type-badge { display: inline-block; padding: .2em .6em; border-radius: 4px; font-size: .85rem; font-weight: 600; }
.type-badge.manned { background: #2a3f1f; color: #8de06a; }
.type-badge.uav    { background: #1f2f3f; color: #6ab0e0; }
.type-badge.mixed  { background: #3a2f10; color: var(--yellow); }
.type-badge.zero   { background: var(--bg); color: var(--text-fade); border: 1px solid var(--divider); }

h2 { font-size: 1.1rem; color: var(--text-sub); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 1rem; }

.chart-section { margin-bottom: 2.5rem; }
.chart-wrap { background: var(--bg-sub); border: 1px solid var(--divider); border-radius: 8px; padding: 1rem; }
.chart-imgs { display: flex; flex-wrap: wrap; gap: 1rem; }
.chart-img { max-width: 100%; border-radius: 8px; border: 1px solid var(--divider); }
.no-chart { color: var(--text-fade); font-size: .9rem; }

/* Table */
.table-section { overflow-x: auto; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
th { background: var(--bg-sub); color: var(--text-sub); padding: .7rem .8rem; text-align: left; border-bottom: 1px solid var(--divider); font-weight: 600; font-size: .75rem; text-transform: uppercase; white-space: nowrap; }
td { padding: .6rem .8rem; border-bottom: 1px solid var(--divider); color: var(--text); vertical-align: middle; }
tr:hover td { background: #232a2d; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.yellow { color: var(--yellow); }
.red    { color: var(--red); }
.special { color: var(--text-sub); font-size: .82rem; max-width: 200px; }

/* Monthly */
.month-section { margin-bottom: 3rem; border-top: 1px solid var(--divider); padding-top: 1.5rem; }
.month-section h2 { color: var(--yellow); font-size: 1.3rem; margin-bottom: 1rem; }
.month-stats { display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1.5rem; }
.stat { display: flex; flex-direction: column; gap: .2rem; }
.stat-label { font-size: .75rem; color: var(--text-sub); text-transform: uppercase; }
.stat-val { font-size: 1.6rem; font-weight: 700; color: var(--text); }
.stat-val.yellow { color: var(--yellow); }
.stat-val.red    { color: var(--red); }
.thumbs { display: flex; flex-wrap: wrap; gap: .8rem; }
.thumb { text-align: center; }
.thumb img { width: 280px; border-radius: 6px; border: 1px solid var(--divider); display: block; }
.thumb-label { font-size: .75rem; color: var(--text-fade); margin-top: .3rem; }

@media (max-width: 600px) {
  .cards { grid-template-columns: 1fr 1fr; }
  .thumb img { width: 160px; }
}
"""
    (SITE_DIR / 'style.css').write_text(css, encoding='utf-8')
    print('[OK] style.css')


if __name__ == '__main__':
    df = load_df()
    sync_charts()
    build_css()
    build_index(df)
    build_records(df)
    build_monthly(df)
    print('[DONE] Site built at', SITE_DIR)
