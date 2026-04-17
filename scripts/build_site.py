"""
build_site.py — 讀取 records.csv，產出靜態網站
圖表使用 Chart.js 瀏覽器端渲染，不需要 matplotlib 或字型安裝。
"""
import json
from pathlib import Path
import pandas as pd

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
SITE_DIR  = ROOT
SITE_DIR.mkdir(exist_ok=True)


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def load_df():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def fmt_date(date_str):
    """YYYY-MM-DD → M/D"""
    dt = pd.to_datetime(date_str)
    return f"{dt.month}/{dt.day}"


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
  --tx:#c4d4dc; --sub:#8a9faa; --grn:#4dba6a;
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
.sitrep{margin-bottom:1.2rem}
.sitrep-label{font-size:1rem;text-transform:uppercase;letter-spacing:.16em;
  color:var(--sub);margin-bottom:.75rem;display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
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
.stat-l{font-size:.98rem;text-transform:uppercase;letter-spacing:.11em;
  color:var(--sub);margin-top:.45rem;white-space:nowrap}
.stat-detail{font-size:1.1rem;color:var(--sub);margin-top:.2rem;white-space:nowrap}
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

/* ── Chart.js split panels ── */
.split-panels{background:#1e2224;border-radius:var(--rad);padding:12px 12px 8px}
.panel-wrap-ac{position:relative;height:200px}
.panel-wrap-sh{position:relative;height:130px;margin-top:8px}

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

/* ── Activity Map ── */
.map-wrap{background:#070b0d;border-radius:var(--rad);overflow:hidden;border:1px solid var(--bdr)}
#activity-map{height:380px}
.leaflet-container{font-family:'Noto Sans TC','Microsoft JhengHei',sans-serif}
.leaflet-control-attribution{
  background:rgba(7,11,13,0.82)!important;color:#3a5060!important;
  font-size:.52rem!important;border-top:1px solid #1a2830!important;padding:2px 6px!important}
.leaflet-control-attribution a{color:#3a5060!important}
.leaflet-control-zoom a{
  background:#0e1618!important;color:var(--sub)!important;
  border:1px solid var(--bdr)!important;font-size:14px!important;line-height:24px!important}
.leaflet-control-zoom a:hover{background:#152028!important;color:var(--tx)!important}
.leaflet-bar{border:1px solid var(--bdr)!important;box-shadow:none!important}
.map-lbl{color:#c4d4dc;font-size:.75rem;font-weight:700;
  font-family:'Noto Sans TC',sans-serif;
  text-shadow:0 1px 4px #000,0 0 8px rgba(0,0,0,.9);
  white-space:nowrap;pointer-events:none;line-height:1}
.map-lbl-sm{color:#4a6070;font-size:.58rem;font-weight:600;
  font-family:'Noto Sans TC',sans-serif;
  text-shadow:0 1px 3px #000,0 0 6px #000;
  white-space:nowrap;pointer-events:none;line-height:1}
.map-info{
  background:rgba(7,11,13,0.9);border:1px solid var(--bdr);border-radius:4px;
  padding:.5rem .7rem;font-size:.7rem;font-family:'Noto Sans TC',sans-serif;
  pointer-events:none;min-width:100px}
.map-info-row{display:flex;align-items:center;gap:.4rem;line-height:1.85;color:var(--sub)}
.map-ml-label{
  font-size:.58rem;font-weight:700;letter-spacing:.08em;
  color:#2a4050;text-transform:uppercase;margin-top:.3rem;line-height:1.4}

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
  #activity-map{height:260px}
}
@media(max-width:380px){.stat-n{font-size:1.9rem}}
"""
    (SITE_DIR / 'style.css').write_text(css, encoding='utf-8')
    print('[OK] style.css')


# ── Chart.js 圖表產生 ─────────────────────────────────────────────────────────

# ── 10日觀察：飛機面積圖 + 艦艇階梯折線 ──────────────────────────────────────
_CHART_JS_RECENT = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
var xA={grid:{display:false},ticks:{color:'#96b0b8',font:{size:10},maxRotation:0},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?'#3a4448':'transparent';}},ticks:{color:'#96b0b8',font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var baseOpts={animation:false,responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'line',data:AC,borderColor:'#f5c842',backgroundColor:'rgba(245,200,66,0.18)',fill:true,tension:0.3,pointRadius:3,pointBackgroundColor:ACbg,pointBorderColor:ACbg,order:2},
  {type:'line',data:CR,borderColor:'#ff9933',borderDash:[4,3],pointBackgroundColor:'#ff9933',pointRadius:3,tension:0,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'line',data:SH,borderColor:'#e05555',backgroundColor:'rgba(224,85,85,0.12)',fill:true,stepped:true,pointRadius:3,pointBackgroundColor:SHbg,pointBorderColor:SHbg}
]},options:baseOpts});
})();"""

# ── 2026至今：飛機＋艦艇長條，X軸只顯示每月1號 ───────────────────────────────
_CHART_JS_YTD = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
var xA={grid:{display:false},ticks:{color:'#96b0b8',font:{size:10},maxRotation:0,autoSkip:false,callback:function(v,i){return L[i]&&L[i].endsWith('/1')?L[i]:''}},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?'#3a4448':'transparent';}},ticks:{color:'#96b0b8',font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var baseOpts={animation:false,responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'bar',data:AC,backgroundColor:ACbg,borderRadius:2,order:2},
  {type:'line',data:CR,borderColor:'#ff9933',borderDash:[4,3],pointBackgroundColor:'#ff9933',pointRadius:2,tension:0,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'bar',data:SH,backgroundColor:SHbg,borderRadius:2}
]},options:baseOpts});
})();"""


def _build_panels(uid, df_slice, today_date, template):
    """共用：準備資料並套用 JS 模板，回傳 HTML 字串。"""
    data = df_slice.reset_index(drop=True)
    today_idx = next(
        (i for i, (_, r) in enumerate(data.iterrows()) if r['date'] == today_date),
        len(data) - 1
    )
    n = len(data)

    labels   = [fmt_date(r['date']) for _, r in data.iterrows()]
    aircraft = [int(r['aircraft_total'])    if pd.notna(r['aircraft_total'])    else 0 for _, r in data.iterrows()]
    crosses  = [int(r['median_line_cross']) if pd.notna(r['median_line_cross']) else 0 for _, r in data.iterrows()]
    ships    = [int(r['ships_total'])       if pd.notna(r['ships_total'])       else 0 for _, r in data.iterrows()]

    ac_bg = ['#f5c842' if i == today_idx else '#8a7020' for i in range(n)]
    sh_bg = ['#e05555' if i == today_idx else '#7a2a2a' for i in range(n)]

    js = (template
          .replace('__L__',    json.dumps(labels))
          .replace('__AC__',   json.dumps(aircraft))
          .replace('__CR__',   json.dumps(crosses))
          .replace('__SH__',   json.dumps(ships))
          .replace('__ACbg__', json.dumps(ac_bg))
          .replace('__SHbg__', json.dumps(sh_bg))
          .replace('__UID__',  uid))

    return (f'<div class="split-panels">'
            f'<div class="panel-wrap-ac"><canvas id="{uid}-ac"></canvas></div>'
            f'<div class="panel-wrap-sh"><canvas id="{uid}-sh"></canvas></div>'
            f'</div>'
            f'<script>{js}</script>')


def chart_section_html(title, chart_html, obs_ac='', obs_sh=''):
    ac_tag = f'<span class="chart-obs">{obs_ac}</span>' if obs_ac else ''
    sh_tag = f'<span class="chart-obs" style="color:var(--r)">{obs_sh}</span>' if obs_sh else ''
    return (f'<section class="chart-section">'
            f'<div class="chart-header">'
            f'<span class="chart-title">{title}</span>{ac_tag}{sh_tag}'
            f'</div>'
            f'{chart_html}'
            f'</section>')


# ── 活動區域地圖 ──────────────────────────────────────────────────────────────

_MAP_JS = """\
(function(){
var ML=__ML__,AC=__AC__,SH=__SH__,ZONES=__ZONES__;

var map=L.map('activity-map',{
  center:[23.8,120.5],zoom:6,
  scrollWheelZoom:false,
  zoomControl:true,
  attributionControl:true,
  maxBounds:[[18,113],[30,129]],
  maxBoundsViscosity:0.85
});

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{
  attribution:'\\u00a9 <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> \\u00a9 <a href="https://carto.com/">CARTO</a>',
  subdomains:'abcd',maxZoom:10,minZoom:5
}).addTo(map);

// No custom Taiwan polygon — CartoDB tiles already render Taiwan accurately.
// Only add annotation layers on top.

// Taiwan Strait Median Line 中線
// True position: midpoint between Fujian coast (~118-119.5°E) and Taiwan W coast (~120°E)
// Runs approx 119.0-120.1°E depending on latitude
var mlColor=ML>0?'#e05555':'#3a6070';
var mlDash=ML>0?'7,4':'6,5';
var mlW=ML>0?2:1.5;
L.polyline([
  [26.5,120.1],[26.0,120.0],[25.5,119.9],
  [25.0,119.7],[24.5,119.5],[24.0,119.3],
  [23.5,119.1],[23.0,119.0],[22.5,119.0]
],{color:mlColor,weight:mlW,dashArray:mlDash,opacity:0.85}).addTo(map);

// Activity zone overlays — styled to match MND bulletin areas
var zS={fillColor:'#f5c842',fillOpacity:0.13,color:'#f5c842',weight:1.2,opacity:0.55,dashArray:'4,3'};
function zoneLabel(ll,txt){
  L.marker(ll,{icon:L.divIcon({className:'',html:'<div style="color:#f5c842;font-size:.58rem;font-weight:700;font-family:Noto Sans TC,sans-serif;text-shadow:0 1px 4px #000,0 0 8px #000;white-space:nowrap;pointer-events:none">'+txt+'</div>',iconAnchor:[0,0]}),interactive:false,keyboard:false}).addTo(map);
}
// 北部空域 — north of Taiwan, spans both strait and Pacific flanks
if(ZONES.n){
  L.polygon([[24.8,120.8],[26.5,120.5],[26.5,122.8],[24.8,122.8]],zS).addTo(map);
  zoneLabel([25.8,121.2],'北部空域');
}
// 西南部空域 — SW quadrant, towards Dongsha
if(ZONES.sw){
  L.polygon([[20.5,117.5],[22.5,117.5],[22.5,120.5],[20.5,120.5]],zS).addTo(map);
  zoneLabel([21.2,118.2],'西南部空域');
}
// 東部空域 — east of Taiwan, Pacific side
if(ZONES.e){
  L.polygon([[22.0,121.8],[24.5,121.8],[24.5,123.8],[22.0,123.8]],zS).addTo(map);
  zoneLabel([22.8,122.3],'東部空域');
}
// 東北部空域 — NE Taiwan, near Miyako Strait
if(ZONES.ne){
  L.polygon([[24.5,122.0],[26.2,122.0],[26.2,124.0],[24.5,124.0]],zS).addTo(map);
  zoneLabel([25.2,122.5],'東北部空域');
}
// 南部空域
if(ZONES.s){
  L.polygon([[21.0,120.2],[22.2,120.2],[22.2,122.0],[21.0,122.0]],zS).addTo(map);
  zoneLabel([21.3,120.8],'南部空域');
}

// Island labels via DivIcon
function lbl(ll,txt,sm){
  return L.marker(ll,{icon:L.divIcon({className:'',html:'<div class="'+(sm?'map-lbl-sm':'map-lbl')+'">'+txt+'</div>',iconAnchor:[0,0]}),interactive:false,keyboard:false});
}
lbl([24.58,121.0],'台灣').addTo(map);
lbl([24.47,118.44],'金門',true).addTo(map);
lbl([26.20,119.98],'馬祖',true).addTo(map);
lbl([20.68,116.68],'東沙',true).addTo(map);
lbl([24.97,119.42],'烏坵',true).addTo(map);

// Info panel (bottom-right)
var info=L.control({position:'bottomright'});
info.onAdd=function(){
  var d=L.DomUtil.create('div','map-info');
  var mlRow=ML>0
    ?'<div class="map-info-row"><span style="color:#e05555">\\u2715 \\u9032 '+ML+'</span>&thinsp;逾中線</div>'
    :'<div class="map-info-row"><span style="color:#2a4a60">\\u2500 未逾中線</span></div>';
  d.innerHTML=
    '<div class="map-info-row"><span style="color:#f5c842">&#9992;&thinsp;'+AC+'</span>&thinsp;架次</div>'+
    '<div class="map-info-row"><span style="color:#e05555">&#9875;&thinsp;'+SH+'</span>&thinsp;艘艦艇</div>'+
    mlRow;
  return d;
};
info.addTo(map);

// Legend (top-left)
var leg=L.control({position:'topleft'});
leg.onAdd=function(){
  var d=L.DomUtil.create('div','map-info');
  d.style.cssText='padding:.35rem .55rem;font-size:.56rem;min-width:0';
  var hasZone=ZONES.n||ZONES.sw||ZONES.e||ZONES.ne||ZONES.s;
  d.innerHTML=
    '<div style="display:flex;align-items:center;gap:5px;color:'+mlColor+';line-height:1.9">'+
    '<svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3" stroke="'+mlColor+'" stroke-width="'+(ML>0?2:1.5)+'" stroke-dasharray="'+(ML>0?'7,3':'6,4')+'"/></svg>中線</div>'+
    (hasZone?'<div style="display:flex;align-items:center;gap:5px;color:#f5c842;line-height:1.9">'+
    '<svg width="10" height="10"><rect x="1" y="1" width="8" height="8" fill="#f5c842" fill-opacity="0.25" stroke="#f5c842" stroke-width="1"/></svg>活動區域</div>':'');
  return d;
};
leg.addTo(map);

})();"""


def map_section_html(ac_val, ml_val, sh_val, special):
    """Generate tactical map section HTML with Leaflet."""
    special_str = special or ''
    zones = {
        'n':  ('北部' in special_str or '北方' in special_str) and '東北' not in special_str,
        'sw': '西南' in special_str,
        'e':  '東部' in special_str and '東北' not in special_str,
        'ne': '東北' in special_str,
        's':  '南部' in special_str,
    }
    # 若同時提到北部與東北部，兩者都顯示
    if '東北' in special_str and '北部' in special_str:
        zones['n'] = True
        zones['ne'] = True
    js = (_MAP_JS
          .replace('__ML__',    str(ml_val))
          .replace('__AC__',    str(ac_val))
          .replace('__SH__',    str(sh_val))
          .replace('__ZONES__', json.dumps(zones)))
    return (
        '<section class="chart-section">'
        '<div class="chart-header">'
        '<span class="chart-title">活動區域示意</span>'
        '<span class="chart-obs" style="color:var(--sub);font-size:.75rem">台海周邊 · 示意圖</span>'
        '</div>'
        '<div class="map-wrap">'
        '<div id="activity-map"></div>'
        '</div>'
        f'<script>{js}</script>'
        '</section>'
    )


# ── HTML 共用片段 ─────────────────────────────────────────────────────────────

HEAD = """\
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中國擾台趨勢數據分析</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
</head>"""


def nav_html(active='index'):
    links = [('index.html', '總覽'), ('records.html', '每日紀錄')]
    items = ''.join(
        f'<a href="{h}"{"" if active != h.split(".")[0] else " class=active"}>{t}</a>'
        for h, t in links
    )
    return f'<nav>{items}</nav>'


def footer_html(update_label):
    return (f'<footer>'
            f'<span>資料來源：<a href="https://www.mnd.gov.tw/news/plaactlist" target="_blank">中華民國國防部</a></span>'
            f'<span>製作：Adam Pan</span>'
            f'<span>更新：{update_label}</span>'
            f'</footer>')


def monthly_stats_html(df, today_date):
    month_prefix = today_date[:7]
    df_mo = df[df['date'].str.startswith(month_prefix)].copy()
    if df_mo.empty:
        return ''
    mo_ac     = int(df_mo['aircraft_total'].fillna(0).sum())
    mo_cr     = int(df_mo['median_line_cross'].fillna(0).sum())
    mo_sh_avg = df_mo['ships_total'].fillna(0).mean()
    days      = len(df_mo)
    mo_label  = f"{pd.to_datetime(today_date).month}月"
    cr_rate   = f"{mo_cr/mo_ac*100:.0f}%" if mo_ac > 0 else '—'

    return (f'<div class="sitrep" style="margin-top:2.5rem">'
            f'<div class="sitrep-label">{mo_label}至今 &nbsp;·&nbsp; {days} 天</div>'
            f'<div class="stats-row">'
            f'<div class="stat"><div class="stat-n y">{mo_ac}</div><div class="stat-l">中共軍機架次</div></div>'
            f'<div class="stat"><div class="stat-n y">{mo_cr}</div><div class="stat-l">越中線&nbsp;<span class="stat-detail">{cr_rate}</span></div></div>'
            f'<div class="stat"><div class="stat-n r">{mo_sh_avg:.1f}</div><div class="stat-l">艦艇日均（艘）</div></div>'
            f'</div></div>')


# ── index.html ────────────────────────────────────────────────────────────────

def build_index(df):
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    today_date  = latest['date']
    today_label = fmt_date(today_date)

    ac_val  = int(latest['aircraft_total'])    if pd.notna(latest['aircraft_total'])    else 0
    ml_val  = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    sh_val  = int(latest['ships_total'])       if pd.notna(latest['ships_total'])       else 0
    cr_str  = (f"{float(latest['cross_rate']):.0f}%"
               if str(latest['cross_rate']) not in ('', 'nan') else '—')
    atype   = latest['aircraft_type'] if pd.notna(latest['aircraft_type']) else '—'
    _BOILERPLATE = ['航跡圖', '故無提供', '未偵獲共機']
    _raw_special = latest['special_event'] if str(latest['special_event']) not in ('', 'nan') else ''
    special = '' if any(kw in _raw_special for kw in _BOILERPLATE) else _raw_special

    ac_delta = delta_span(latest['aircraft_total'], prev['aircraft_total'])
    sh_delta = delta_span(latest['ships_total'],    prev['ships_total'])

    type_lower = atype.lower() if atype != '—' else 'zero'
    type_label = {'zero': '零架次', 'manned': '有人機', 'uav': 'UAV',
                  'mixed': '混合', 'helicopter': '直升機'}.get(type_lower, atype)

    # 近10日：飛機面積圖＋艦艇散點
    recent_html = _build_panels('rc',  df.tail(10), today_date, _CHART_JS_RECENT)
    # 2026至今：飛機＋艦艇長條，X軸只顯示每月1號
    year_prefix = today_date[:4]
    ytd_html    = _build_panels('ytd', df[df['date'] >= year_prefix], today_date, _CHART_JS_YTD)

    df_mo    = df[df['date'].str.startswith(today_date[:7])]
    mo_max   = int(df_mo['aircraft_total'].max()) if len(df_mo) else 0
    mo_max_d = fmt_date(df_mo.loc[df_mo['aircraft_total'].idxmax(), 'date']) if mo_max > 0 else ''
    sh_lo    = int(df['ships_total'].min())
    sh_hi    = int(df['ships_total'].max())

    split_ac  = f"今日 {ac_val} 架次"
    split_sh  = f"{sh_val} 艘艦艇"
    streak_ac = f"本月峰值 {mo_max} 架次（{mo_max_d}）" if mo_max > 0 else ''
    streak_sh = f"艦艇 {sh_lo}–{sh_hi} 艘"

    alert_html   = f'<div class="alert">⚡ {special}</div>' if special else ''
    monthly_html = monthly_stats_html(df, today_date)
    map_html     = map_section_html(ac_val, ml_val, sh_val, _raw_special)

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
  {alert_html}

  <div class="sitrep">
    <div class="sitrep-label">SITREP &nbsp;·&nbsp; {today_label} &nbsp;·&nbsp; <span class="badge {type_lower}">{type_label}</span></div>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-n y">{ac_val}</div>
        <div class="stat-l">中共軍機架次</div>
        {ac_delta}
      </div>
      <div class="stat">
        <div class="stat-n y">{ml_val}</div>
        <div class="stat-l">逾越中線&nbsp;<span class="stat-detail">{cr_str}</span></div>
      </div>
      <div class="stat">
        <div class="stat-n r">{sh_val}</div>
        <div class="stat-l">中共艦艇</div>
        {sh_delta}
      </div>
    </div>
  </div>

  {monthly_html}

  {map_html}

  {chart_section_html("10日觀察", recent_html, split_ac, split_sh)}
  {chart_section_html("2026 至今", ytd_html, streak_ac, streak_sh)}

</main>

{footer_html(today_label)}
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
        ac    = int(row['aircraft_total'])    if pd.notna(row['aircraft_total'])    else 0
        sh    = int(row['ships_total'])       if pd.notna(row['ships_total'])       else 0
        ml    = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
        label = fmt_date(row['date'])
        tl    = atype.lower() if atype != '—' else 'zero'
        type_zh = {'zero': '零', 'manned': '有人機', 'uav': 'UAV',
                   'mixed': '混合', 'helicopter': '直升機'}.get(tl, atype)
        rows += (f'<tr>'
                 f'<td>{label}</td>'
                 f'<td class="num yellow">{ac}</td>'
                 f'<td class="num">{ml}</td>'
                 f'<td class="num">{cr}</td>'
                 f'<td><span class="badge {tl}">{type_zh}</span></td>'
                 f'<td class="num red">{sh}</td>'
                 f'<td class="special-cell">{spec}</td>'
                 f'</tr>')

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
    build_css()
    build_index(df)
    build_records(df)
    print('[DONE] Site built →', SITE_DIR)
