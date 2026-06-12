"""
build_site.py — 讀取 records.csv，產出靜態網站（中英雙語）
圖表使用 Chart.js 瀏覽器端渲染，不需要 matplotlib 或字型安裝。
en/ 子目錄由本腳本自動產生，禁止手動修改。
"""
import json
import re
import sys
from datetime import date
from pathlib import Path
import pandas as pd

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
SITE_DIR  = ROOT
SITE_DIR.mkdir(exist_ok=True)


# ── 字串對照表（UI 文字全部抽在這裡）────────────────────────────────────────────

STRINGS = {
    'zh': {
        'html_lang': 'zh-Hant',
        'page_titles': {
            'index':   '中國擾台趨勢數據分析',
            'records': '每日紀錄 — 中國擾台趨勢數據分析',
            'monthly': '月統計 — 中國擾台趨勢數據分析',
        },
        'site_title': '中國擾台趨勢數據分析',
        'site_sub': 'PLA Activity Around Taiwan',
        'nav_index': '總覽',
        'nav_records': '每日紀錄',
        'nav_monthly': '月統計',
        'nav_toggle': 'EN',
        'unclassified': 'UNCLASSIFIED // OPEN SOURCE',
        'sitrep_label': 'SITREP',
        'stat_aircraft': '中共軍機架次',
        'stat_median': '逾越中線',
        'stat_ships': '中共艦艇',
        'mo_prefix': '{m}月至今',
        'mo_days': '天',
        'mo_aircraft': '中共軍機架次',
        'mo_cross': '逾越中線',
        'mo_ships_avg': '艦艇日均（艘）',
        'chart_recent': '10日觀察',
        'chart_ytd': '2026 至今',
        'obs_ac': '今日 {n} 架次',
        'obs_sh': '{n} 艘艦艇',
        'peak_ac': '本月峰值 {n} 架次（{d}）',
        'ships_range': '艦艇 {lo}–{hi} 艘',
        'map_title': '活動區域示意',
        'map_sub': '台海周邊 · 示意圖',
        'map_note': (
            '<strong>12海里領海界線（綠色虛線）</strong>為實質法律邊界。'
            '解放軍機艦越過中線不觸發自衛權；'
            '一旦進入此界線內的領海或領空，'
            '依國際法及《國防法》，台灣方面可採取防衛行動。'
        ),
        'map_zone_n':    '北部空域',
        'map_zone_sw':   '西南部空域',
        'map_zone_e':    '東部空域',
        'map_zone_ne':   '東北部空域',
        'map_leg_ml':    '中線',
        'map_leg_12nm':  '12海里領海',
        'map_leg_zone':  '活動區域',
        'map_lbl_tw':    '台灣',
        'map_lbl_ph':    '澎湖',
        'map_lbl_km':    '金門',
        'map_lbl_mz':    '馬祖',
        'map_lbl_ds':    '東沙',
        'map_lbl_wq':    '烏坵',
        'footer_src_label': '資料來源：',
        'footer_src_name':  '中華民國國防部',
        'footer_src_url':   'https://www.mnd.gov.tw/news/plaactlist',
        'footer_credit': '製作：Adam Pan',
        'footer_update': '更新：',
        'tbl_date':   '日期',
        'tbl_ac':     '架次',
        'tbl_cross':  '越線',
        'tbl_rate':   '越線率',
        'tbl_type':   '機型',
        'tbl_ships':  '艦艇',
        'tbl_note':   '備註',
        'records_page_sub':    '每日紀錄',
        'records_count_unit':  '筆',
        'type_manned':    '有人機',
        'type_uav':       '無人機',
        'type_mixed':     '混合',
        'type_zero':      '零架次',
        'type_helicopter':'直升機',
        'kw_uav':       ('無人機',   '無人機',   'uav'),
        'kw_heli':      ('直升機',   '直升機',   'helicopter'),
        'kw_support':   ('輔戰機',   '輔戰機',   'manned'),
        'kw_fighter':   ('殲擊機',   '殲擊機',   'manned'),
        'kw_bomber':    ('轟炸機',   '轟炸機',   'manned'),
        'kw_asw':       ('反潛機',   '反潛機',   'manned'),
        'kw_ew':        ('電子戰機', '電子戰機', 'manned'),
        'kw_aew':       ('預警機',   '預警機',   'manned'),
        'kw_transport': ('運輸機',   '運輸機',   'manned'),
        'kw_recon':     ('偵察機',   '偵察機',   'manned'),
        'generic_types': {'有人機', '混合', '零架次', '—'},
        'monthly_heading': '月統計',
        'monthly_col_month': '月份',
        'monthly_col_days':  '天數',
        'monthly_col_ac':    '總架次',
        'monthly_col_cross': '越線',
        'monthly_col_rate':  '越線率',
        'monthly_col_ships': '艦艇日均',
        'monthly_records_count': '共 {n} 筆',
    },
    'en': {
        'html_lang': 'en',
        'page_titles': {
            'index':   'PLA Activity Tracker — Taiwan Strait',
            'records': 'Daily Records — PLA Activity Tracker',
            'monthly': 'Monthly Stats — PLA Activity Tracker',
        },
        'site_title': 'PLA Activity Tracker — Taiwan Strait',
        'site_sub': 'Daily data from ROC MND public releases',
        'nav_index': 'Overview',
        'nav_records': 'Daily Records',
        'nav_monthly': 'Monthly',
        'nav_toggle': '中文',
        'unclassified': 'UNCLASSIFIED // OPEN SOURCE',
        'sitrep_label': 'SITREP',
        'stat_aircraft': 'PLA Sorties',
        'stat_median': 'Median Line Crossings',
        'stat_ships': 'PLA Vessels',
        'mo_prefix': '{m} MTD',
        'mo_days': 'days',
        'mo_aircraft': 'PLA Sorties',
        'mo_cross': 'Median Line Crossings',
        'mo_ships_avg': 'Avg Vessels/Day',
        'chart_recent': '10-Day Trend',
        'chart_ytd': '2026 YTD',
        'obs_ac': 'Today: {n} sorties',
        'obs_sh': '{n} vessels',
        'peak_ac': 'Month peak: {n} ({d})',
        'ships_range': 'Vessels {lo}–{hi}',
        'map_title': 'Activity Areas',
        'map_sub': 'Taiwan Strait · Indicative',
        'map_note': (
            '<strong>12 NM territorial sea (green)</strong> is the de facto legal boundary. '
            'PLA aircraft/vessels crossing the median line does not trigger the right of self-defense; '
            'entry into the territorial sea or airspace within this boundary would, '
            'under international law and the Defense Act, allow Taiwan to take defensive action.'
        ),
        'map_zone_n':    'Northern',
        'map_zone_sw':   'SW',
        'map_zone_e':    'Eastern',
        'map_zone_ne':   'NE',
        'map_leg_ml':    'Median line',
        'map_leg_12nm':  '12 NM territorial sea',
        'map_leg_zone':  'Activity zones',
        'map_lbl_tw':    'Taiwan',
        'map_lbl_ph':    'Penghu',
        'map_lbl_km':    'Kinmen',
        'map_lbl_mz':    'Matsu',
        'map_lbl_ds':    'Pratas',
        'map_lbl_wq':    'Wuqiu',
        'footer_src_label': 'Source: ',
        'footer_src_name':  'ROC Ministry of National Defense',
        'footer_src_url':   'https://www.mnd.gov.tw/news/plaactlist',
        'footer_credit': 'By Adam Pan',
        'footer_update': 'Updated: ',
        'tbl_date':   'Date',
        'tbl_ac':     'Sorties',
        'tbl_cross':  'Crossings',
        'tbl_rate':   'Cross Rate',
        'tbl_type':   'Type',
        'tbl_ships':  'Vessels',
        'tbl_note':   'Notes',
        'records_page_sub':    'Daily Records',
        'records_count_unit':  'entries',
        'type_manned':    'Manned aircraft',
        'type_uav':       'UAV',
        'type_mixed':     'Mixed',
        'type_zero':      'No activity',
        'type_helicopter':'Helicopter',
        'kw_uav':       ('無人機',   'UAV',             'uav'),
        'kw_heli':      ('直升機',   'Helicopter',      'helicopter'),
        'kw_support':   ('輔戰機',   'Support aircraft','manned'),
        'kw_fighter':   ('殲擊機',   'Fighter',         'manned'),
        'kw_bomber':    ('轟炸機',   'Bomber',          'manned'),
        'kw_asw':       ('反潛機',   'ASW aircraft',    'manned'),
        'kw_ew':        ('電子戰機', 'EW aircraft',     'manned'),
        'kw_aew':       ('預警機',   'AEW aircraft',    'manned'),
        'kw_transport': ('運輸機',   'Transport',       'manned'),
        'kw_recon':     ('偵察機',   'Reconnaissance',  'manned'),
        'generic_types': {'Manned aircraft', 'Mixed', 'No activity', '—'},
        'monthly_heading': 'Monthly Statistics',
        'monthly_col_month': 'Month',
        'monthly_col_days':  'Days',
        'monthly_col_ac':    'Total Sorties',
        'monthly_col_cross': 'Crossings',
        'monthly_col_rate':  'Cross Rate',
        'monthly_col_ships': 'Avg Vessels',
        'monthly_records_count': '{n} records',
    },
}


# ── 規則式翻譯：special_event 中文 → 英文 ────────────────────────────────────

_REGION_MAP = [
    ('東北', 'northeastern'),
    ('東南', 'southeastern'),
    ('西南', 'southwestern'),
    ('北部', 'northern'),
    ('北',   'northern'),
    ('中部', 'central'),
    ('中',   'central'),
    ('南部', 'southern'),
    ('南',   'southern'),
    ('東部', 'eastern'),
    ('東',   'eastern'),
]


def _map_region(zh):
    """Map a Chinese region fragment to English (longest match first).
    Returns original (Chinese) if unknown and prints WARN so the gap can be caught.
    """
    label = zh.replace('空域', '').replace('部', '').strip()
    for k, v in _REGION_MAP:
        if k in label:
            return v
    # Unknown region: warn if there is actual Chinese text so future vocab gaps surface
    if label and re.search(r'[一-鿿]', label):
        print(f'[WARN] Unknown airspace region "{label}" — add to _REGION_MAP',
              file=sys.stderr)
    return label  # fallback: return cleaned string (may be Chinese)


def _fmt_regions(regions):
    if not regions:
        return ''
    if len(regions) == 1:
        return regions[0]
    return ', '.join(regions[:-1]) + ' and ' + regions[-1]


def _translate_crossing_regions(regions_str):
    """'北部及西南空域' → 'northern and southwestern airspace'."""
    # Remove trailing 空域 before splitting
    regions_str = re.sub(r'空域$', '', regions_str.strip())
    parts = re.split(r'[、及，,\s]+', regions_str)
    en_regions = [_map_region(p) for p in parts if p.strip()]
    en_regions = [r for r in en_regions if r]
    if not en_regions:
        return f'Median line crossings: {regions_str} airspace'
    return f'Median line crossings: {_fmt_regions(en_regions)} airspace'


def _translate_airspace_block(part):
    """Handle new-format airspace text: '{regions}空域(N架次...)' blocks."""
    # Format A: single 空域 at end, regions listed before with 、及
    # e.g. "北部、中部、西南及東部空域(逾越中線18架次)"
    m = re.match(r'^([一-鿿、及，,\s]+?)(?:部)?空域[（(]([^）)]*)[）)]$', part.strip())
    if m:
        regions_zh = m.group(1)
        detail = m.group(2)
        parts = re.split(r'[、及，,\s]+', regions_zh)
        en_regions = [_map_region(p) for p in parts if p.strip()]
        en_regions = [r for r in en_regions if r]
        region_str = _fmt_regions(en_regions) + ' airspace'
        cross_m = re.search(r'逾越中線.*?(\d+)架次', detail)
        sort_m  = re.search(r'(\d+)架次', detail)
        if cross_m:
            return f'Median line crossings: {region_str} ({cross_m.group(1)} sorties)'
        elif '逾越中線' in detail:
            return f'Median line crossings: {region_str}'
        elif sort_m:
            return f'Activity: {region_str} ({sort_m.group(1)} sorties)'
        return f'Activity: {region_str}'

    # Format B: space-separated blocks "北部空域(逾越中線) 西南空域(7架次)"
    blocks = re.findall(r'([一-鿿]+?)空域[（(]([^）)]*)[）)]', part)
    if blocks:
        crossing = []
        activity = []
        for region_zh, detail in blocks:
            en_r = _map_region(region_zh)
            if '逾越中線' in detail:
                crossing.append(en_r)
            else:
                sort_m = re.search(r'(\d+)架次', detail)
                n = sort_m.group(1) if sort_m else ''
                activity.append(f'{en_r} airspace' + (f' ({n} sorties)' if n else ''))
        result = []
        if crossing:
            result.append(f'Median line crossings: {_fmt_regions(crossing)} airspace')
        result.extend(activity)
        return '; '.join(result) if result else None

    # Format C: "西南及東部空域（3架次）" – regions+及 before single 空域, count in parens
    m = re.match(r'^([一-鿿及、，,\s]+?)(?:部)?空域[（(](\d+)架次[）)]$', part.strip())
    if m:
        parts = re.split(r'[、及，,\s]+', m.group(1))
        en_regions = [_map_region(p) for p in parts if p.strip()]
        en_regions = [r for r in en_regions if r]
        return f'Activity: {_fmt_regions(en_regions)} airspace ({m.group(2)} sorties)'

    # Format D: just "西南部空域(①共機1架次)" – single region with circled number
    m = re.match(r'^([一-鿿]+?)空域[（(][^）)]*[）)]$', part.strip())
    if m:
        return f'Activity: {_map_region(m.group(1))} airspace'

    # Format E: multiple "{region}空域" before one paren block
    # e.g. "北部空域及西南空域(逾越中線進入北部及西南空域20架次)"
    m = re.match(r'^((?:[一-鿿]+空域[、及，,]?)+)\s*[（(](.+?)[）)]$', part.strip())
    if m:
        regions_str = m.group(1)
        detail = m.group(2)
        region_parts = re.findall(r'([一-鿿]+?)空域', regions_str)
        en_regions = [_map_region(r) for r in region_parts if r]
        en_regions = [r for r in en_regions if r]
        if en_regions:
            region_str = _fmt_regions(en_regions) + ' airspace'
            cross_m = re.search(r'逾越中線.*?(\d+)架次', detail)
            sort_m  = re.search(r'(\d+)架次', detail)
            if cross_m:
                return f'Median line crossings: {region_str} ({cross_m.group(1)} sorties)'
            elif '逾越中線' in detail:
                return f'Median line crossings: {region_str}'
            elif sort_m:
                return f'Activity: {region_str} ({sort_m.group(1)} sorties)'
            return f'Activity: {region_str}'

    return None


# Static lookup for known editorial notes (editor-added context, not from MND)
_STATIC_EN = {
    '火箭預告':                   'Rocket launch warning',
    '西昌火箭飛越ADIZ（06:33）':  'Xichang rocket transited ADIZ (06:33)',
    '直升機首現（1架）':          'Helicopter first appearance (1 unit)',
    '直升機2架':                  '2 helicopters',
    '純直升機日（首次）東部ADIZ': 'Helicopter-only day (first time), eastern ADIZ',
    '輔戰機+直升機':              'Support aircraft + helicopter',
    '急剎 輔戰機':                'Sudden halt; support aircraft',
    '四方位同時越線':             'Simultaneous crossings on all four vectors',
    '主輔戰機 西南空域':          'Main + support aircraft, southwestern airspace',
    '第一波升溫':                 'First wave escalation',
    '第一波峰值 四方位全覆蓋':    'First wave peak — coverage on all four vectors',
    '第二波起點':                 'Second wave beginning',
    '第二波峰值':                 'Second wave peak',
    '第二波新高 北中西南三方位':  'Second wave new high, N/Central/SW vectors',
    '上述期間未偵獲共機，故無提供航跡圖': '',  # No aircraft — omit in en
    '氣球越中線（基隆西北60浬14000呎）': 'PRC balloon crossed median line (60 nm NW of Keelung, 14,000 ft)',
}


def _extract_crossing_regions(text):
    """Extract region list from '...進入{regions}空域' or '...逾越中線進入{regions}空域'."""
    # Try to find "{regions}空域" pattern at the end
    m = re.search(r'(?:進入|入侵)?([一-鿿及、，,\s]+?)空域$', text.strip())
    if m:
        parts = re.split(r'[、及，,\s]+', m.group(1).strip())
        en_regions = [_map_region(p) for p in parts if p.strip()]
        return [r for r in en_regions if r]
    return []


def translate_special_event(text):
    """Rule-based zh→en translation of special_event field.
    Unmatched strings: return original Chinese and print warning.
    """
    if not text or str(text) in ('', 'nan'):
        return ''
    t = str(text).strip()
    if not t:
        return ''

    # Static lookup first (exact match after strip)
    if t in _STATIC_EN:
        return _STATIC_EN[t]

    # Strip MND item numbering (三、四、 etc.) and section header
    cleaned = re.sub(r'[一二三四五六七八九十]+[、．.]\s*', '', t)
    cleaned = re.sub(r'中共空飄氣球活動：?\s*', '', cleaned)
    cleaned = re.sub(r'[\r\n\x0b\v]+', ' ', cleaned).strip().rstrip('。').strip()

    # Static lookup again after cleaning
    if cleaned in _STATIC_EN:
        return _STATIC_EN[cleaned]

    # Split on semicolon (；or ;)
    parts = re.split(r'[；;]', cleaned)
    result = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Static per-part lookup
        if part in _STATIC_EN:
            v = _STATIC_EN[part]
            if v:
                result.append(v)
            continue

        # Pattern 1: balloon detection 中共空飄氣球計偵獲N顆
        m = re.search(r'中共空飄氣球計?偵獲(\d+)顆', part)
        if m:
            result.append(f'{m.group(1)} PRC surveillance balloon(s) detected')
            continue

        # Pattern 2: balloon crossed median line 氣球越中線（...）
        m = re.match(r'^氣球越中線[（(](.+?)[）)]$', part)
        if m:
            result.append(f'PRC balloon crossed median line ({m.group(1)})')
            continue

        # Pattern 3: simple 越線：{regions} format
        m = re.match(r'^越線[：:]\s*(.+?)$', part)
        if m:
            result.append(_translate_crossing_regions(m.group(1)))
            continue

        # Pattern 4: 逾越中線進入{regions}空域 (with optional leading description)
        if '逾越中線' in part and '空域' in part:
            # Extract everything after 逾越中線 (or 逾越海峽中線)
            m = re.search(r'逾越(?:海峽)?中線進入(.+?空域)$', part)
            if m:
                regions = _extract_crossing_regions(m.group(1))
                if regions:
                    result.append(f'Median line crossings: {_fmt_regions(regions)} airspace')
                    continue
            # Fallback: any 逾越中線 + 空域 combination
            regions = _extract_crossing_regions(part)
            if regions:
                result.append(f'Median line crossings: {_fmt_regions(regions)} airspace')
                continue

        # Pattern 5: 進入{regions}空域 (ADIZ entry without crossing)
        # Guard: skip if 逾越中線 is present — that's a crossing, handled by P4/P6
        if '進入' in part and '空域' in part and '逾越中線' not in part:
            m = re.search(r'進入([一-鿿及、，,\s]+?空域)', part)
            if m:
                regions = _extract_crossing_regions(m.group(1))
                if regions:
                    n_m = re.match(r'^(\d+)架次', part)
                    n_str = f' ({n_m.group(1)} sorties)' if n_m else ''
                    result.append(f'ADIZ entry: {_fmt_regions(regions)} airspace{n_str}')
                    continue

        # Pattern 6: airspace block format {regions}空域(N架次...)
        if '空域' in part:
            translated = _translate_airspace_block(part)
            if translated:
                result.append(translated)
                continue

        # No match – warn and keep original
        print(f'[WARN] translate_special_event: no rule for: {repr(part[:80])}',
              file=sys.stderr)
        result.append(part)

    return '; '.join(result)


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def load_df():
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    return df.sort_values('date').reset_index(drop=True)


def fmt_date(date_str):
    """YYYY-MM-DD → M/D (used for chart labels and zh UI)."""
    dt = pd.to_datetime(date_str)
    return f"{dt.month}/{dt.day}"


def fmt_date_en(date_str):
    """YYYY-MM-DD → 'Jan 15' (English format)."""
    dt = pd.to_datetime(date_str)
    return f"{dt.strftime('%b')} {dt.day}"


def fmt_date_display(date_str, lang):
    return fmt_date_en(date_str) if lang == 'en' else fmt_date(date_str)


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
nav{display:flex;gap:1.5rem;align-items:center}
nav a{color:var(--sub);text-decoration:none;font-size:.72rem;
  font-weight:700;letter-spacing:.09em;text-transform:uppercase}
nav a.active,nav a:hover{color:var(--tx)}
nav a.lang-toggle{border:1px solid var(--bdr);padding:.15em .55em;
  border-radius:3px;margin-left:.5rem;letter-spacing:.06em}

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
.delta-up{display:block;font-size:.7rem;color:#fff;margin-top:.28rem;font-weight:700}
.delta-dn{display:block;font-size:.7rem;color:#fff;margin-top:.28rem;font-weight:700}

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

/* ── Monthly stats table ── */
.monthly-section{margin-bottom:2.5rem}
.monthly-month-label{font-size:.72rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.15em;color:var(--sub);padding:.6rem 0 .4rem;
  border-bottom:1px solid var(--bdr);margin-bottom:.75rem}

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
.leaflet-tile-pane{filter:brightness(1.8) contrast(1.3) saturate(1.4)}
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
.map-note{
  margin-top:.75rem;padding:.55rem .9rem;
  border-left:2px solid #4dba6a;background:#050e09;
  font-size:.75rem;color:var(--sub);line-height:1.7;border-radius:0 var(--rad) var(--rad) 0}
.map-note strong{color:var(--tx)}

/* ── Scroll-triggered entrance animations ── */
.anim-ready{opacity:0;transform:translateY(14px);
  transition:opacity .5s ease,transform .5s ease}
.anim-ready.visible{opacity:1;transform:none}

/* ── zh-Hant 字型視覺校正（CJK 在相同 rem 下視覺較小，補齊至英文版水準）── */
html[lang="zh-Hant"] .site-title{font-size:1.4rem}
html[lang="zh-Hant"] .site-sub{font-size:.72rem}
html[lang="zh-Hant"] nav a{font-size:.82rem;letter-spacing:.06em}
html[lang="zh-Hant"] nav a.lang-toggle{font-size:.72rem;letter-spacing:.09em}

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

_CHART_JS_RECENT = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
var xA={grid:{display:false},ticks:{color:'#96b0b8',font:{size:10},maxRotation:0},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?'#3a4448':'transparent';}},ticks:{color:'#96b0b8',font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var animDelay=function(c){return c.type==='data'&&c.mode==='default'?c.dataIndex*40+c.datasetIndex*120:0;};
var baseOpts={animation:{delay:animDelay,duration:800,easing:'easeOutQuart'},transitions:{active:{animation:{duration:0}}},responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'line',data:AC,borderColor:'#f5c842',backgroundColor:'rgba(245,200,66,0.18)',fill:true,tension:0.3,pointRadius:3,pointBackgroundColor:ACbg,pointBorderColor:ACbg,order:2},
  {type:'line',data:CR,borderColor:'#ff9933',borderDash:[4,3],pointBackgroundColor:'#ff9933',pointRadius:3,tension:0,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'line',data:SH,borderColor:'#e05555',backgroundColor:'rgba(224,85,85,0.12)',fill:true,stepped:true,pointRadius:3,pointBackgroundColor:SHbg,pointBorderColor:SHbg}
]},options:baseOpts});
})();"""

_CHART_JS_YTD = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
var xA={grid:{display:false},ticks:{color:'#96b0b8',font:{size:10},maxRotation:0,autoSkip:false,callback:function(v,i){return L[i]&&L[i].endsWith('/1')?L[i]:''}},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?'#3a4448':'transparent';}},ticks:{color:'#96b0b8',font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var animDelay=function(c){return c.type==='data'&&c.mode==='default'?c.dataIndex*15+c.datasetIndex*60:0;};
var baseOpts={animation:{delay:animDelay,duration:600,easing:'easeOutExpo'},transitions:{active:{animation:{duration:0}}},responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'bar',data:AC,backgroundColor:ACbg,borderRadius:2,order:2},
  {type:'line',data:CR,borderColor:'#ff9933',borderDash:[4,3],pointBackgroundColor:'#ff9933',pointRadius:2,tension:0,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'bar',data:SH,backgroundColor:SHbg,borderRadius:2}
]},options:baseOpts});
})();"""


def _build_panels(uid, df_slice, today_date, template):
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
    return (f'<section class="chart-section anim-ready">'
            f'<div class="chart-header">'
            f'<span class="chart-title">{title}</span>{ac_tag}{sh_tag}'
            f'</div>'
            f'{chart_html}'
            f'</section>')


# ── 活動區域地圖（地圖標籤改用佔位符，由 map_section_html 填入）────────────────

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

var _aL=[];

var mlColor=ML>0?'#e05555':'#3a6070';
var mlDash=ML>0?'7,4':'6,5';
var mlW=ML>0?2:1.5;
L.polyline([
  [26.5,120.5],[26.0,120.3],[25.5,120.0],
  [25.0,119.8],[24.5,119.5],[24.0,119.2],
  [23.5,119.1],[23.0,119.0],[22.5,118.9]
],{color:mlColor,weight:mlW,dashArray:mlDash,opacity:0.85}).addTo(map);

function zoneLabel(ll,txt){
  L.marker(ll,{icon:L.divIcon({className:'',html:'<div style="color:#f5c842;font-size:.58rem;font-weight:700;font-family:Noto Sans TC,sans-serif;text-shadow:0 1px 4px #000,0 0 8px #000;white-space:nowrap;pointer-events:none">'+txt+'</div>',iconAnchor:[0,0]}),interactive:false,keyboard:false}).addTo(map);
}
function gradZone(coords,fp){
  var sc=[1.0,0.78,0.58,0.40,0.24];
  var fo=[0.04,0.07,0.10,0.14,0.19];
  for(var i=sc.length-1;i>=0;i--){
    var s=sc[i];
    var pts=coords.map(function(p){return[fp[0]+s*(p[0]-fp[0]),fp[1]+s*(p[1]-fp[1])];});
    var _l=L.polygon(pts,{fillColor:'#f5c842',fillOpacity:0,color:'none',weight:0}).addTo(map);
    _aL.push([_l,fo[i]]);
  }
}
function gradZone12(coords,fp){
  var sc=[0.82,0.87,0.92,0.97,1.0];
  var fo=[0.26,0.17,0.10,0.05];
  for(var i=0;i<sc.length-1;i++){
    var outer=coords.map(function(p){return[fp[0]+sc[i+1]*(p[0]-fp[0]),fp[1]+sc[i+1]*(p[1]-fp[1])];});
    var inner=coords.map(function(p){return[fp[0]+sc[i]*(p[0]-fp[0]),fp[1]+sc[i]*(p[1]-fp[1])];});
    var _l=L.polygon([outer,inner],{fillColor:'#4dba6a',fillOpacity:0,color:'none',weight:0}).addTo(map);
    _aL.push([_l,fo[i]]);
  }
}
if(ZONES.n){
  gradZone([[25.5,120.3],[26.5,120.3],[26.5,122.5],[25.5,122.0]],[25.6,121.2]);
  zoneLabel([26.1,120.8],'__ZN_N__');
}
if(ZONES.sw){
  gradZone([[23.0,117.0],[23.0,119.8],[21.0,121.0],[21.0,117.0]],[22.2,119.5]);
  zoneLabel([21.8,117.5],'__ZN_SW__');
}
if(ZONES.e){
  gradZone([[22.0,122.0],[24.5,122.0],[24.5,123.5],[22.0,123.5]],[23.0,122.1]);
  zoneLabel([22.8,122.5],'__ZN_E__');
}
if(ZONES.ne){
  gradZone([[26.5,120.7],[26.5,122.2],[25.4,121.8],[25.4,121.0]],[25.5,121.2]);
  zoneLabel([25.9,121.1],'__ZN_NE__');
}

function gradCircle(ll,r){
  var sc=[1.0,0.72,0.47,0.25],fo=[0.06,0.11,0.17,0.25];
  for(var i=sc.length-1;i>=0;i--){
    var _l=L.circle(ll,{radius:r*sc[i],fillColor:'#4dba6a',fillOpacity:0,color:'none',weight:0}).addTo(map);
    _aL.push([_l,fo[i]]);
  }
}
gradZone12([
  [25.50,121.54],[25.00,122.20],[23.95,121.82],
  [22.60,121.35],[21.70,120.85],[22.35,120.05],
  [22.93,119.80],[24.10,120.16],[24.87,120.65],
  [25.32,121.53]
],[23.5,121.0]);
gradCircle([23.57,119.62],38000);
gradCircle([22.67,121.47],22224);
gradCircle([22.05,121.55],22224);

function lbl(ll,txt,sm){
  return L.marker(ll,{icon:L.divIcon({className:'',html:'<div class="'+(sm?'map-lbl-sm':'map-lbl')+'">'+txt+'</div>',iconAnchor:[0,0]}),interactive:false,keyboard:false});
}
lbl([24.58,121.0],'__LBL_TW__').addTo(map);
lbl([23.57,119.62],'__LBL_PH__',true).addTo(map);
lbl([24.47,118.44],'__LBL_KM__',true).addTo(map);
lbl([26.20,119.98],'__LBL_MZ__',true).addTo(map);
lbl([20.68,116.68],'__LBL_DS__',true).addTo(map);
lbl([24.97,119.42],'__LBL_WQ__',true).addTo(map);

var leg=L.control({position:'topleft'});
leg.onAdd=function(){
  var d=L.DomUtil.create('div','map-info');
  d.style.cssText='padding:.35rem .55rem;font-size:.56rem;min-width:0';
  var hasZone=ZONES.n||ZONES.sw||ZONES.e||ZONES.ne||ZONES.s;
  var rw='display:flex;align-items:center;gap:5px;line-height:1.9';
  var iS='width:18px;height:8px;flex-shrink:0;display:block';
  d.innerHTML=
    '<div style="'+rw+';color:'+mlColor+'"><svg style="'+iS+'" viewBox="0 0 18 8">'+
    '<line x1="0" y1="4" x2="18" y2="4" stroke="'+mlColor+'" stroke-width="'+(ML>0?2:1.5)+'" stroke-dasharray="'+(ML>0?'7,3':'6,4')+'"/></svg>__LEG_ML__</div>'+
    '<div style="'+rw+';color:#4dba6a"><svg style="'+iS+'" viewBox="0 0 18 8">'+
    '<defs><linearGradient id="g12" x1="1" y1="0" x2="0" y2="0"><stop offset="0%" stop-color="#4dba6a" stop-opacity="0.08"/><stop offset="100%" stop-color="#4dba6a" stop-opacity="0.35"/></linearGradient></defs>'+
    '<rect width="18" height="8" fill="url(#g12)" rx="1"/></svg>__LEG_12NM__</div>'+
    (hasZone?'<div style="'+rw+';color:#f5c842"><svg style="'+iS+'" viewBox="0 0 18 8">'+
    '<defs><linearGradient id="gac" x1="1" y1="0" x2="0" y2="0"><stop offset="0%" stop-color="#f5c842" stop-opacity="0.06"/><stop offset="100%" stop-color="#f5c842" stop-opacity="0.25"/></linearGradient></defs>'+
    '<rect width="18" height="8" fill="url(#gac)" rx="1"/></svg>__LEG_ZONE__</div>':'');
  return d;
};
leg.addTo(map);

map.whenReady(function(){
  setTimeout(function(){
    _aL.forEach(function(item,i){
      var el=item[0].getElement();
      if(!el)return;
      el.style.transition='fill-opacity '+(0.7+i*0.012)+'s cubic-bezier(0.4,0,0.2,1) '+(150+i*22)+'ms';
      el.style.fillOpacity=item[1];
    });
  },250);
});

})();"""


def map_section_html(ac_val, ml_val, sh_val, special, s):
    special_str = special or ''
    has_n  = ('北部' in special_str and '東北部' not in special_str) or '北方' in special_str
    has_ne = '東北' in special_str
    zones = {
        'n':  has_n,
        'sw': '西南' in special_str,
        'e':  '東部' in special_str and not has_ne,
        'ne': has_ne,
        's':  '南部' in special_str and '西南部' not in special_str,
    }
    js = (_MAP_JS
          .replace('__ML__',      str(ml_val))
          .replace('__AC__',      str(ac_val))
          .replace('__SH__',      str(sh_val))
          .replace('__ZONES__',   json.dumps(zones))
          .replace('__ZN_N__',    s['map_zone_n'])
          .replace('__ZN_SW__',   s['map_zone_sw'])
          .replace('__ZN_E__',    s['map_zone_e'])
          .replace('__ZN_NE__',   s['map_zone_ne'])
          .replace('__LEG_ML__',  s['map_leg_ml'])
          .replace('__LEG_12NM__',s['map_leg_12nm'])
          .replace('__LEG_ZONE__',s['map_leg_zone'])
          .replace('__LBL_TW__',  s['map_lbl_tw'])
          .replace('__LBL_PH__',  s['map_lbl_ph'])
          .replace('__LBL_KM__',  s['map_lbl_km'])
          .replace('__LBL_MZ__',  s['map_lbl_mz'])
          .replace('__LBL_DS__',  s['map_lbl_ds'])
          .replace('__LBL_WQ__',  s['map_lbl_wq']))
    return (
        '<section class="chart-section anim-ready">'
        '<div class="chart-header">'
        f'<span class="chart-title">{s["map_title"]}</span>'
        f'<span class="chart-obs" style="color:var(--sub);font-size:.75rem">{s["map_sub"]}</span>'
        '</div>'
        '<div class="map-wrap">'
        '<div id="activity-map"></div>'
        '</div>'
        f'<div class="map-note">{s["map_note"]}</div>'
        f'<script>{js}</script>'
        '</section>'
    )


# ── HTML 共用片段 ─────────────────────────────────────────────────────────────

_VER = date.today().strftime('%Y%m%d')


def make_head(lang, page_name, s):
    """Build complete <head> block for the given lang and page."""
    title    = s['page_titles'][page_name]
    html_lng = s['html_lang']

    # Absolute canonical paths for hreflang
    canonical_zh = f'/{page_name}.html'
    canonical_en = f'/en/{page_name}.html'

    # Asset paths: en/ pages use absolute paths to avoid subdirectory issues
    if lang == 'en':
        css_href = f'/style.css?v={_VER}'
        fav_href = f'/favicon.svg?v={_VER}'
        ver_path = '/version.txt'
    else:
        css_href = f'style.css?v={_VER}'
        fav_href = f'favicon.svg?v={_VER}'
        ver_path = 'version.txt'

    return f"""\
<!DOCTYPE html>
<html lang="{html_lng}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="alternate" hreflang="zh-Hant" href="{canonical_zh}">
<link rel="alternate" hreflang="en" href="{canonical_en}">
<link rel="icon" type="image/svg+xml" href="{fav_href}">
<link rel="stylesheet" href="{css_href}">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script>fetch('{ver_path}?t='+Date.now(),{{cache:'no-store'}}).then(r=>r.text()).then(v=>{{if(v.trim()!=='{_VER}')location.reload(true);}});</script>
<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "8d6b79b3348642d981b992d2928e98ab"}}'></script>
</head>"""


def nav_html(active, lang, page_name, s):
    """Navigation bar with language toggle."""
    base   = '/en' if lang == 'en' else ''
    toggle = f'/{page_name}.html' if lang == 'en' else f'/en/{page_name}.html'

    pages = [
        ('index',   s['nav_index']),
        ('records', s['nav_records']),
        ('monthly', s['nav_monthly']),
    ]
    items = ''.join(
        f'<a href="{base}/{p}.html"{"" if active != p else " class=active"}>{label}</a>'
        for p, label in pages
    )
    lang_link = f'<a href="{toggle}" class="lang-toggle">{s["nav_toggle"]}</a>'
    return f'<nav>{items}{lang_link}</nav>'


def footer_html(update_label, s):
    return (
        f'<footer>'
        f'<span>{s["footer_src_label"]}<a href="{s["footer_src_url"]}" target="_blank">'
        f'{s["footer_src_name"]}</a></span>'
        f'<span>{s["footer_credit"]}</span>'
        f'<span>{s["footer_update"]}{update_label}</span>'
        f'</footer>'
    )


def monthly_stats_html(df, today_date, s):
    month_prefix = today_date[:7]
    df_mo = df[df['date'].str.startswith(month_prefix)].copy()
    if df_mo.empty:
        return ''
    mo_ac     = int(df_mo['aircraft_total'].fillna(0).sum())
    mo_cr     = int(df_mo['median_line_cross'].fillna(0).sum())
    mo_sh_avg = df_mo['ships_total'].fillna(0).mean()
    days      = len(df_mo)
    dt        = pd.to_datetime(today_date)
    if s['html_lang'] == 'en':
        mo_label = s['mo_prefix'].format(m=dt.strftime('%B'))
    else:
        mo_label = s['mo_prefix'].format(m=dt.month)
    cr_rate   = f"{mo_cr/mo_ac*100:.0f}%" if mo_ac > 0 else '—'

    return (
        f'<div class="sitrep anim-ready" style="margin-top:2.5rem">'
        f'<div class="sitrep-label">{mo_label} &nbsp;·&nbsp; {days} {s["mo_days"]}</div>'
        f'<div class="stats-row">'
        f'<div class="stat"><div class="stat-n y" data-count="{mo_ac}">0</div>'
        f'<div class="stat-l">{s["mo_aircraft"]}</div></div>'
        f'<div class="stat"><div class="stat-n y" data-count="{mo_cr}">0</div>'
        f'<div class="stat-l">{s["mo_cross"]}&nbsp;<span class="stat-detail">{cr_rate}</span></div></div>'
        f'<div class="stat"><div class="stat-n r">{mo_sh_avg:.1f}</div>'
        f'<div class="stat-l">{s["mo_ships_avg"]}</div></div>'
        f'</div></div>'
    )


# ── Aircraft type badge helper ────────────────────────────────────────────────

_KW_KEYS = ['kw_uav', 'kw_heli', 'kw_support', 'kw_fighter', 'kw_bomber',
            'kw_asw', 'kw_ew', 'kw_aew', 'kw_transport', 'kw_recon']

_FALLBACK_CSS = {'manned': 'type_manned', 'uav': 'type_uav', 'mixed': 'type_mixed',
                 'helicopter': 'type_helicopter', 'zero': 'type_zero'}


def type_info(atype_raw, special_str, s):
    """Return (css_class, display_label) for badge, localized via s (STRINGS[lang])."""
    text = special_str or ''
    found_labels, found_classes = [], set()
    for kw_key in _KW_KEYS:
        zh_kw, display, css = s[kw_key]
        if zh_kw in text:
            found_labels.append(display)
            found_classes.add(css)

    if found_labels:
        css = 'mixed' if len(found_classes) > 1 else found_classes.pop()
        sep = '、' if s['html_lang'] == 'zh-Hant' else ' / '
        return css, sep.join(found_labels)

    tl = (atype_raw or '').lower()
    css = tl if tl in _FALLBACK_CSS else 'zero'
    return css, s.get(_FALLBACK_CSS.get(css, 'type_zero'), atype_raw or '—')


# ── index.html ────────────────────────────────────────────────────────────────

_ANIM_JS = """\
<script>(function(){
function animCount(el,t,d){
var s=performance.now();
function step(n){
var p=Math.min((n-s)/d,1);
var e=1-Math.pow(1-p,4);
el.textContent=Math.round(e*t);
if(p<1)requestAnimationFrame(step);}
requestAnimationFrame(step);}
var io=new IntersectionObserver(function(entries){
entries.forEach(function(e){
if(!e.isIntersecting)return;
var el=e.target;
el.classList.add('visible');
io.unobserve(el);
el.querySelectorAll('canvas').forEach(function(c){
var ch=typeof Chart!=='undefined'&&Chart.getChart(c);
if(ch){ch.reset();ch.update();}});
el.querySelectorAll('[data-count]').forEach(function(s,i){
var t=+s.dataset.count;
if(!t)return;
setTimeout(function(){animCount(s,t,900);},i*100);});});},{threshold:0.15});
document.querySelectorAll('.anim-ready').forEach(function(el){io.observe(el);});
})();</script>"""


def build_index(df, lang, out_dir, s):
    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    today_date  = latest['date']
    today_label = fmt_date_display(today_date, lang)

    ac_val  = int(latest['aircraft_total'])    if pd.notna(latest['aircraft_total'])    else 0
    ml_val  = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    sh_val  = int(latest['ships_total'])       if pd.notna(latest['ships_total'])       else 0
    cr_str  = (f"{float(latest['cross_rate']):.0f}%"
               if str(latest['cross_rate']) not in ('', 'nan') else '—')
    atype   = latest['aircraft_type'] if pd.notna(latest['aircraft_type']) else '—'

    _BOILERPLATE = ['航跡圖', '故無提供', '未偵獲共機']
    _raw_special = latest['special_event'] if str(latest['special_event']) not in ('', 'nan') else ''
    special_zh = '' if any(kw in _raw_special for kw in _BOILERPLATE) else _raw_special

    if lang == 'en':
        special_display = translate_special_event(special_zh) if special_zh else ''
    else:
        special_display = special_zh

    ac_delta = delta_span(latest['aircraft_total'], prev['aircraft_total'])
    sh_delta = delta_span(latest['ships_total'],    prev['ships_total'])

    type_lower, type_label = type_info(atype, special_zh, s)
    sitrep_badge = (f'&nbsp;·&nbsp; {type_label}'
                    if type_label not in s['generic_types'] else '')

    recent_html = _build_panels('rc',  df.tail(10), today_date, _CHART_JS_RECENT)
    year_prefix = today_date[:4]
    ytd_html    = _build_panels('ytd', df[df['date'] >= year_prefix], today_date, _CHART_JS_YTD)

    df_mo    = df[df['date'].str.startswith(today_date[:7])]
    mo_max   = int(df_mo['aircraft_total'].max()) if len(df_mo) else 0
    mo_max_d = fmt_date_display(
        df_mo.loc[df_mo['aircraft_total'].idxmax(), 'date'], lang
    ) if mo_max > 0 else ''
    sh_lo    = int(df['ships_total'].min())
    sh_hi    = int(df['ships_total'].max())

    split_ac  = s['obs_ac'].format(n=ac_val)
    split_sh  = s['obs_sh'].format(n=sh_val)
    streak_ac = s['peak_ac'].format(n=mo_max, d=mo_max_d) if mo_max > 0 else ''
    streak_sh = s['ships_range'].format(lo=sh_lo, hi=sh_hi)

    alert_html   = f'<div class="alert">⚡ {special_display}</div>' if special_display else ''
    monthly_html = monthly_stats_html(df, today_date, s)
    map_html     = map_section_html(ac_val, ml_val, sh_val, _raw_special, s)

    head = make_head(lang, 'index', s)
    html = f"""{head}
<body>
<div class="top-bar">
  <span>{s['unclassified']}</span>
  <span>ROC MND · {today_label}</span>
</div>
<header class="site-header">
  <div class="header-inner">
    <div class="site-brand">
      <div class="site-title">{s['site_title']}</div>
      <div class="site-sub">{s['site_sub']}</div>
    </div>
    {nav_html('index', lang, 'index', s)}
  </div>
</header>

<main>
  {alert_html}

  <div class="sitrep anim-ready">
    <div class="sitrep-label">{s['sitrep_label']} &nbsp;·&nbsp; {today_label}{sitrep_badge}</div>
    <div class="stats-row">
      <div class="stat">
        <div class="stat-n y" data-count="{ac_val}">0</div>
        <div class="stat-l">{s['stat_aircraft']}</div>
        {ac_delta}
      </div>
      <div class="stat">
        <div class="stat-n y" data-count="{ml_val}">0</div>
        <div class="stat-l">{s['stat_median']}&nbsp;<span class="stat-detail">{cr_str}</span></div>
      </div>
      <div class="stat">
        <div class="stat-n r" data-count="{sh_val}">0</div>
        <div class="stat-l">{s['stat_ships']}</div>
        {sh_delta}
      </div>
    </div>
  </div>

  {monthly_html}

  {map_html}

  {chart_section_html(s['chart_recent'], recent_html, split_ac, split_sh)}
  {chart_section_html(s['chart_ytd'], ytd_html, streak_ac, streak_sh)}

</main>

{_ANIM_JS}
{footer_html(today_label, s)}
</body></html>"""

    (out_dir / 'index.html').write_text(html, encoding='utf-8')
    print(f'[OK] {out_dir.name}/index.html' if out_dir != SITE_DIR else '[OK] index.html')


# ── records.html ──────────────────────────────────────────────────────────────

def build_records(df, lang, out_dir, s):
    rows = ''
    for _, row in df.sort_values('date', ascending=False).iterrows():
        cr    = (f"{float(row['cross_rate']):.0f}%"
                 if str(row['cross_rate']) not in ('', 'nan') else '—')
        atype = row['aircraft_type'] if pd.notna(row['aircraft_type']) else '—'
        spec_raw = row['special_event'] if str(row['special_event']) not in ('', 'nan') else ''
        if lang == 'en':
            spec = translate_special_event(spec_raw)
        else:
            spec = spec_raw
        ac    = int(row['aircraft_total'])    if pd.notna(row['aircraft_total'])    else 0
        sh    = int(row['ships_total'])       if pd.notna(row['ships_total'])       else 0
        ml    = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
        label = fmt_date_display(row['date'], lang)
        tl, type_lbl = type_info(atype, spec_raw, s)
        rows += (f'<tr>'
                 f'<td>{label}</td>'
                 f'<td class="num yellow">{ac}</td>'
                 f'<td class="num">{ml}</td>'
                 f'<td class="num">{cr}</td>'
                 f'<td><span class="badge {tl}">{type_lbl}</span></td>'
                 f'<td class="num red">{sh}</td>'
                 f'<td class="special-cell">{spec}</td>'
                 f'</tr>')

    today_label = fmt_date_display(df.iloc[-1]['date'], lang)
    head = make_head(lang, 'records', s)
    html = f"""{head}
<body>
<header class="site-header">
  <div class="header-inner">
    <div>
      <h1 class="site-title">{s['site_title']}</h1>
      <p class="site-meta">{s['records_page_sub']}　{s['monthly_records_count'].format(n=len(df))}</p>
    </div>
    {nav_html('records', lang, 'records', s)}
  </div>
</header>

<main>
  <div class="tbl-wrap">
  <table>
    <thead><tr>
      <th>{s['tbl_date']}</th><th>{s['tbl_ac']}</th><th>{s['tbl_cross']}</th>
      <th>{s['tbl_rate']}</th><th>{s['tbl_type']}</th><th>{s['tbl_ships']}</th>
      <th>{s['tbl_note']}</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</main>

{footer_html(today_label, s)}
</body></html>"""

    (out_dir / 'records.html').write_text(html, encoding='utf-8')
    print(f'[OK] {out_dir.name}/records.html' if out_dir != SITE_DIR else '[OK] records.html')


# ── monthly.html ──────────────────────────────────────────────────────────────

def build_monthly(df, lang, out_dir, s):
    """Monthly aggregated stats page."""
    df_copy = df.copy()
    df_copy['month'] = df_copy['date'].str[:7]
    months = sorted(df_copy['month'].unique(), reverse=True)

    rows = ''
    for mo in months:
        df_mo = df_copy[df_copy['month'] == mo]
        mo_ac  = int(df_mo['aircraft_total'].fillna(0).sum())
        mo_cr  = int(df_mo['median_line_cross'].fillna(0).sum())
        mo_sh  = df_mo['ships_total'].fillna(0).mean()
        days   = len(df_mo)
        rate   = f"{mo_cr/mo_ac*100:.0f}%" if mo_ac > 0 else '—'

        if lang == 'en':
            dt = pd.to_datetime(mo + '-01')
            mo_label = dt.strftime('%b %Y')
        else:
            yr, mn = mo.split('-')
            mo_label = f"{yr}年{int(mn)}月"

        rows += (f'<tr>'
                 f'<td>{mo_label}</td>'
                 f'<td class="num">{days}</td>'
                 f'<td class="num y">{mo_ac}</td>'
                 f'<td class="num">{mo_cr}</td>'
                 f'<td class="num">{rate}</td>'
                 f'<td class="num r">{mo_sh:.1f}</td>'
                 f'</tr>')

    today_label = fmt_date_display(df.iloc[-1]['date'], lang)
    head = make_head(lang, 'monthly', s)
    html = f"""{head}
<body>
<header class="site-header">
  <div class="header-inner">
    <div>
      <h1 class="site-title">{s['site_title']}</h1>
      <p class="site-sub">{s['monthly_heading']}</p>
    </div>
    {nav_html('monthly', lang, 'monthly', s)}
  </div>
</header>

<main>
  <div class="tbl-wrap">
  <table>
    <thead><tr>
      <th>{s['monthly_col_month']}</th>
      <th>{s['monthly_col_days']}</th>
      <th>{s['monthly_col_ac']}</th>
      <th>{s['monthly_col_cross']}</th>
      <th>{s['monthly_col_rate']}</th>
      <th>{s['monthly_col_ships']}</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  </div>
</main>

{footer_html(today_label, s)}
</body></html>"""

    (out_dir / 'monthly.html').write_text(html, encoding='utf-8')
    print(f'[OK] {out_dir.name}/monthly.html' if out_dir != SITE_DIR else '[OK] monthly.html')


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    df = load_df()
    build_css()

    for lang in ('zh', 'en'):
        s = STRINGS[lang]
        if lang == 'zh':
            out_dir = SITE_DIR
        else:
            out_dir = SITE_DIR / 'en'
            out_dir.mkdir(exist_ok=True)

        build_index(df, lang, out_dir, s)
        build_records(df, lang, out_dir, s)
        build_monthly(df, lang, out_dir, s)

    (SITE_DIR / 'version.txt').write_text(_VER, encoding='utf-8')
    print('[OK] version.txt')
    print('[DONE] Site built →', SITE_DIR)
