"""
build_site.py — 讀取 records.csv，產出靜態網站（中英雙語）
圖表使用 Chart.js 瀏覽器端渲染，不需要 matplotlib 或字型安裝。
en/ 子目錄由本腳本自動產生，禁止手動修改。
"""
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
import pandas as pd

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
SITE_DIR  = ROOT
SITE_DIR.mkdir(exist_ok=True)

# 正式部署網域（canonical / OG / sitemap / robots 的絕對網址基準）
BASE_URL = 'https://pla-tracker.pages.dev'
# Skyfaring 作品集主站（頁尾回連）
HUB_URL  = 'https://skyfaring.pages.dev/'
# 相關發布（部落格）
BLOG_URL = 'https://yi-tienpan.blogspot.com'


# ── 字串對照表（UI 文字全部抽在這裡）────────────────────────────────────────────

STRINGS = {
    'zh': {
        'html_lang': 'zh-Hant',
        'page_titles': {
            'index':   '中國擾台趨勢數據分析',
            'records': '每日紀錄 — 中國擾台趨勢數據分析',
            'monthly': '月統計 — 中國擾台趨勢數據分析',
            'about':   '方法論與資料來源 — 中國擾台趨勢數據分析',
        },
        'meta_descs': {
            'index':   '每日追蹤中國解放軍在台灣周邊的軍事活動：共機架次、逾越海峽中線比例、共艦數量與趨勢圖。資料來源：中華民國國防部每日公布。',
            'records': '解放軍擾台每日紀錄表：逐日共機架次、逾越中線數、機型、共艦艘數。資料來源：國防部，每日更新。',
            'monthly': '解放軍擾台月統計：每月共機總架次、逾越中線數、越線率與共艦日均。資料來源：國防部。',
            'about':   '本站方法論：資料來源（國防部每日公布）、更新頻率、海峽中線與12浬領海線的定義差異、數據整理流程與引用授權。',
        },
        'site_title': '中國擾台趨勢數據分析',
        'site_sub': 'PLA Activity Around Taiwan',
        'nav_about': '關於',
        'footer_hub': '由 Skyfaring 製作',
        'sitrep_text':      '{date}：偵獲中共軍機 {ac} 架次，其中 {ml} 架次逾越海峽中線（越線率 {rate}）；中共艦艇 {sh} 艘。',
        'sitrep_text_zero': '{date}：當日未偵獲中共軍機；中共艦艇 {sh} 艘。',
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
        'chart_dl': '下載 PNG',
        'chart_embed': '嵌入',
        'chart_embed_hint': '把這段貼到你的網站或部落格：',
        'chart_embed_copy': '複製',
        'chart_embed_copied': '已複製 ✓',
        'embed_wm': '資料來源：中華民國國防部　·　圖表：解放軍擾台動態追蹤　·　pla-tracker.pages.dev',
        'embed_foot': '資料來源：國防部　·　圖表：解放軍擾台動態追蹤',
        'embed_cta': '看完整數據 →',
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
            'about':   'Methodology & Data Sources — PLA Activity Tracker',
        },
        'meta_descs': {
            'index':   'Daily tracking of PLA military activity around Taiwan: aircraft sorties, Taiwan Strait median-line crossings, naval vessels and trends. Source: ROC Ministry of National Defense daily releases.',
            'records': 'Daily log of PLA activity around Taiwan: per-day sorties, median-line crossings, aircraft type and vessel counts. Source: ROC MND, updated daily.',
            'monthly': 'Monthly PLA activity statistics for the Taiwan Strait: total sorties, median-line crossings, crossing rate and average vessels per day. Source: ROC MND.',
            'about':   'Methodology: data source (ROC MND daily releases), update frequency, the difference between the Taiwan Strait median line and the 12 NM territorial sea, data compilation and citation/licensing.',
        },
        'site_title': 'PLA Activity Tracker — Taiwan Strait',
        'site_sub': 'Daily data from ROC MND public releases',
        'nav_about': 'About',
        'footer_hub': 'Made by Skyfaring',
        'sitrep_text':      'On {date}, {ac} PLA aircraft sorties were detected, of which {ml} crossed the Taiwan Strait median line ({rate} crossing rate); {sh} PLA naval vessels.',
        'sitrep_text_zero': 'On {date}, no PLA aircraft were detected; {sh} PLA naval vessels.',
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
        'chart_dl': 'Download PNG',
        'chart_embed': 'Embed',
        'chart_embed_hint': 'Paste this into your site or blog:',
        'chart_embed_copy': 'Copy',
        'chart_embed_copied': 'Copied ✓',
        'embed_wm': 'Source: ROC MND   ·   Chart: PLA Activity Tracker   ·   pla-tracker.pages.dev',
        'embed_foot': 'Source: ROC MND   ·   Chart: PLA Activity Tracker',
        'embed_cta': 'See full data →',
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


def fmt_date_full(date_str, lang):
    """YYYY-MM-DD → 'Jun 18, 2026' (en) / '2026年6月18日' (zh) for prose text."""
    dt = pd.to_datetime(date_str)
    if lang == 'en':
        return f"{dt.strftime('%b')} {dt.day}, {dt.year}"
    return f"{dt.year}年{dt.month}月{dt.day}日"


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
  --rad:10px;
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
.sitrep{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);
  padding:1rem 1.25rem 1.1rem;margin-bottom:1.25rem}
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
.badge{display:inline-block;padding:.2em .7em;border-radius:999px;font-size:.78rem;font-weight:700}
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
.chart-title{font-size:.7rem;font-weight:800;letter-spacing:.16em;
  text-transform:uppercase;color:var(--sub);white-space:nowrap}
.chart-obs{font-size:.95rem;color:var(--y);font-weight:600}

/* ── Chart.js split panels ── */
.split-panels{background:#1e2224;border-radius:var(--rad);padding:12px 12px 8px}
.panel-wrap-ac{position:relative;height:200px}
.panel-wrap-sh{position:relative;height:130px;margin-top:8px}

/* ── Chart tools: PNG download + iframe embed (媒體可引用) ── */
.chart-tools{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;margin-top:.7rem}
.chart-btn{background:var(--sur);border:1px solid var(--bdr);color:var(--sub);
  font:inherit;font-size:.68rem;font-weight:700;letter-spacing:.04em;
  padding:.42em 1em;border-radius:999px;cursor:pointer;transition:.15s}
.chart-btn:hover{color:var(--tx);border-color:#2c4049;background:#11201f}
.embed-box{display:none;flex-basis:100%;margin-top:.3rem}
.embed-hint{font-size:.66rem;color:var(--sub);margin-bottom:.35rem;letter-spacing:.03em}
.embed-box textarea{width:100%;height:66px;resize:vertical;display:block;
  background:#0a1014;border:1px solid var(--bdr);border-radius:5px;color:var(--tx);
  font:12px/1.55 ui-monospace,Menlo,Consolas,monospace;padding:.55rem .6rem}
.embed-copy{margin-top:.45rem;background:var(--y);border:0;color:#1a1400;
  font-weight:800;font-size:.66rem;letter-spacing:.03em;
  padding:.38em .95em;border-radius:999px;cursor:pointer}
.embed-copy:hover{background:#ffd75e}

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
.monthly-month-label{font-size:.7rem;font-weight:800;letter-spacing:.16em;
  text-transform:uppercase;color:var(--sub);padding:.6rem 0 .4rem;
  border-bottom:1px solid var(--bdr);margin-bottom:.75rem}

/* ── Footer ── */
footer{border-top:1px solid var(--bdr);padding:1.1rem 1.5rem 1.4rem;margin-top:1rem;
  display:flex;flex-wrap:wrap;gap:.5rem 2rem;
  font-size:.65rem;color:var(--sub);letter-spacing:.05em}
footer a{color:var(--sub);text-decoration:none}
footer a:hover{color:var(--tx)}
.footer-hub{margin-left:auto}
.footer-hub a{color:var(--sub)}
.footer-hub a:hover{color:var(--y)}

/* ── Text SITREP (crawler-readable one-liner) ── */
.sitrep-text{font-size:.85rem;color:var(--sub);line-height:1.75;
  margin:1rem 0 2.25rem;padding:0}
html[lang="zh-Hant"] .sitrep-text{font-size:.9rem}

/* ── About / methodology prose ── */
.prose{max-width:760px;margin:0 auto}
.prose-title{font-size:1.5rem;font-weight:800;letter-spacing:-.01em;
  color:var(--tx);margin-bottom:.6rem}
.prose h2{font-size:1rem;font-weight:800;color:var(--tx);letter-spacing:.02em;
  margin:2rem 0 .6rem;padding-bottom:.4rem;border-bottom:1px solid var(--bdr)}
.prose p{font-size:.92rem;line-height:1.85;color:var(--tx);margin:.6rem 0}
.prose .lead{font-size:1rem;color:var(--sub);line-height:1.8;margin-bottom:.4rem}
.prose a{color:var(--y);text-decoration:none;border-bottom:1px solid #4a3f12;
  word-break:break-word}
.prose a:hover{color:#fff;border-bottom-color:var(--y)}
.prose strong{color:var(--tx);font-weight:700}
.prose ul{margin:.6rem 0 .6rem 1.2rem}
.prose li{font-size:.92rem;line-height:1.8;color:var(--tx);margin:.35rem 0}
html[lang="zh-Hant"] .prose p,html[lang="zh-Hant"] .prose li{font-size:.95rem}
.about-meta{display:flex;flex-wrap:wrap;gap:.4rem 1.5rem;font-size:.72rem;
  color:var(--sub);letter-spacing:.04em;margin:.6rem 0 1.5rem;
  padding:.6rem 0;border-top:1px solid var(--bdr);border-bottom:1px solid var(--bdr)}
.def-card{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);
  padding:.85rem 1rem;margin:.7rem 0}
.def-card .term{font-weight:800;color:var(--tx);font-size:.95rem}
.def-card .term .en{color:var(--sub);font-weight:500;font-size:.78rem;margin-left:.4rem}
.def-card p{margin:.4rem 0 0;font-size:.88rem;color:var(--sub);line-height:1.8}
html[lang="zh-Hant"] .def-card p{font-size:.9rem}

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
  .header-inner{gap:.5rem}
  nav{gap:.95rem;flex-wrap:wrap;justify-content:flex-end}
  main{padding:.6rem 1rem 1rem}
  .alert{margin-bottom:1rem}
  .sitrep{padding:.55rem .9rem .6rem;margin-bottom:1rem}
  .map-note{margin-top:.5rem}
  .stats-row{grid-template-columns:repeat(3,1fr);gap:0}
  .stat{padding:0 .5rem;min-width:0}
  .stat:first-child{border-left:none;padding-left:0}
  .stat-n{font-size:2.3rem}
  .stat-l{white-space:normal;font-size:.78rem;overflow-wrap:break-word}
  .stat-detail{display:block;white-space:nowrap;margin-top:.1rem}
  footer{padding:.75rem 1rem;gap:.4rem 1.2rem}
  .footer-hub{margin-left:0;flex-basis:100%}
  .prose-title{font-size:1.3rem}
  #activity-map{height:260px}
}
@media(max-width:380px){
  .stat-n{font-size:1.9rem}
  nav{gap:.7rem}
  html[lang="zh-Hant"] nav a{font-size:.78rem;letter-spacing:.03em}
}
"""
    (SITE_DIR / 'style.css').write_text(css, encoding='utf-8')
    print('[OK] style.css')


# ── Chart.js 圖表產生 ─────────────────────────────────────────────────────────

_CHART_JS_RECENT = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
// 垂直漸層填色（頂濃底透）：area chart 質感關鍵；匯出 PNG 端會保留此函式重畫。
function gfill(hex){return function(c){var a=c.chart.chartArea;if(!a)return 'rgba(0,0,0,0)';
  var g=c.chart.ctx.createLinearGradient(0,a.top,0,a.bottom);
  g.addColorStop(0,hex+'59');g.addColorStop(0.85,hex+'0d');g.addColorStop(1,hex+'00');return g;};}
var xA={grid:{display:false},ticks:{color:'#96b0b8',font:{size:10},maxRotation:0},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?'#3a4448':'transparent';}},ticks:{color:'#96b0b8',font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var animDelay=function(c){return c.type==='data'&&c.mode==='default'?c.dataIndex*40+c.datasetIndex*120:0;};
var baseOpts={animation:{delay:animDelay,duration:800,easing:'easeOutQuart'},transitions:{active:{animation:{duration:0}}},responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'line',data:AC,borderColor:'#f5c842',backgroundColor:gfill('#f5c842'),fill:true,tension:0.35,borderWidth:2.5,pointRadius:3,pointHoverRadius:5,pointBackgroundColor:ACbg,pointBorderColor:'#1e2224',pointBorderWidth:1.5,order:2},
  {type:'line',data:CR,borderColor:'#ff9933',borderDash:[5,4],borderWidth:1.5,pointBackgroundColor:'#ff9933',pointRadius:0,pointHoverRadius:4,tension:0.35,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'line',data:SH,borderColor:'#e05555',backgroundColor:gfill('#e05555'),fill:true,tension:0.35,borderWidth:2.5,pointRadius:3,pointHoverRadius:5,pointBackgroundColor:SHbg,pointBorderColor:'#1e2224',pointBorderWidth:1.5}
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


def chart_section_html(title, chart_html, obs_ac='', obs_sh='', tools_html=''):
    ac_tag = f'<span class="chart-obs">{obs_ac}</span>' if obs_ac else ''
    sh_tag = f'<span class="chart-obs" style="color:var(--r)">{obs_sh}</span>' if obs_sh else ''
    return (f'<section class="chart-section anim-ready">'
            f'<div class="chart-header">'
            f'<span class="chart-title">{title}</span>{ac_tag}{sh_tag}'
            f'</div>'
            f'{chart_html}'
            f'{tools_html}'
            f'</section>')


def chart_tools_html(slug, uid, title, today_date, s, lang):
    """媒體可引用工具列：高解析 PNG 下載 + iframe 嵌入碼（皆瀏覽器端，無需 CI 字型）.

    slug  → 嵌入頁檔名（/embed/{slug}.html）
    uid   → 頁面內 canvas 前綴（{uid}-ac / {uid}-sh），供 plaDownloadChart 取圖
    """
    base   = '/en' if lang == 'en' else ''
    src    = f'{BASE_URL}{base}/embed/{slug}.html'
    box_id = f'emb-{uid}'
    fn     = f'pla-tracker-{slug}-{today_date}'
    # iframe 片段放進 <textarea>：以實體編碼顯示，使用者複製到的就是可用標記
    iframe = (
        f'&lt;iframe src=&quot;{src}&quot; width=&quot;100%&quot; height=&quot;470&quot; '
        f'style=&quot;border:0;max-width:680px;width:100%&quot; loading=&quot;lazy&quot; '
        f'title=&quot;{html.escape(title, quote=True)}&quot;&gt;&lt;/iframe&gt;'
    )
    return (
        '<div class="chart-tools">'
        f'<button type="button" class="chart-btn" data-uid="{uid}" '
        f'data-title="{html.escape(title, quote=True)}" '
        f'data-sub="{html.escape(s["site_title"], quote=True)}" '
        f'data-wm="{html.escape(s["embed_wm"], quote=True)}" data-fn="{fn}" '
        f'onclick="plaDownloadChart(this)">↓ {s["chart_dl"]}</button>'
        f'<button type="button" class="chart-btn" '
        f'onclick="plaToggleEmbed(&#39;{box_id}&#39;)">&lt;/&gt; {s["chart_embed"]}</button>'
        f'<div id="{box_id}" class="embed-box">'
        f'<div class="embed-hint">{s["chart_embed_hint"]}</div>'
        f'<textarea readonly rows="3" onclick="this.select()">{iframe}</textarea>'
        f'<button type="button" class="embed-copy" '
        f'data-done="{html.escape(s["chart_embed_copied"], quote=True)}" '
        f'onclick="plaCopyEmbed(this)">{s["chart_embed_copy"]}</button>'
        '</div>'
        '</div>'
    )


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

# 精確到分：同日重 build（改 CSS/版面）也能失效快取並觸發 version.txt 自動 reload
_VER = datetime.now().strftime('%Y%m%d%H%M')


def make_head(lang, page_name, s, head_extra=''):
    """Build complete <head> block for the given lang and page.

    head_extra: optional raw HTML (e.g. JSON-LD) injected just before </head>.
    """
    title    = s['page_titles'][page_name]
    html_lng = s['html_lang']
    desc     = s['meta_descs'][page_name]

    # Absolute URLs for canonical / hreflang / OG (full domain, per SEO best practice)
    path     = f'/{page_name}.html'
    canon_zh = f'{BASE_URL}{path}'
    canon_en = f'{BASE_URL}/en{path}'
    canonical = canon_en if lang == 'en' else canon_zh

    # Asset paths: en/ pages use absolute paths to avoid subdirectory issues
    if lang == 'en':
        css_href = f'/style.css?v={_VER}'
        fav_href = f'/favicon.svg?v={_VER}'
        ver_path = '/version.txt'
        og_image = f'{BASE_URL}/og-en.png'
        og_locale, og_locale_alt = 'en_US', 'zh_TW'
    else:
        css_href = f'style.css?v={_VER}'
        fav_href = f'favicon.svg?v={_VER}'
        ver_path = 'version.txt'
        og_image = f'{BASE_URL}/og.png'
        og_locale, og_locale_alt = 'zh_TW', 'en_US'

    return f"""\
<!DOCTYPE html>
<html lang="{html_lng}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="zh-Hant" href="{canon_zh}">
<link rel="alternate" hreflang="en" href="{canon_en}">
<link rel="alternate" hreflang="x-default" href="{canon_zh}">
<meta name="theme-color" content="#090d0f">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{s['site_title']}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{s['site_title']}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:locale:alternate" content="{og_locale_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og_image}">
<meta name="twitter:image:alt" content="{s['site_title']}">
<link rel="icon" type="image/svg+xml" href="{fav_href}">
<link rel="stylesheet" href="{css_href}">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script>fetch('{ver_path}?t='+Date.now(),{{cache:'no-store'}}).then(r=>r.text()).then(v=>{{if(v.trim()!=='{_VER}')location.reload(true);}});</script>
{head_extra}
</head>"""


# ── schema.org Dataset 結構化資料（JSON-LD，給 Google Dataset Search）──────────

def dataset_jsonld(df, lang):
    """Build a schema.org Dataset JSON-LD block from the live data range."""
    start = df['date'].min()
    end   = df['date'].max()
    if lang == 'en':
        name = 'PLA Activity Around Taiwan — Daily Dataset'
        desc = ("Daily structured record of People's Liberation Army (PLA) military activity "
                "around Taiwan, compiled from ROC Ministry of National Defense public releases: "
                "aircraft sorties, Taiwan Strait median-line crossings and naval vessel counts.")
        page = f'{BASE_URL}/en/index.html'   # 與 canonical / og:url 一致
    else:
        name = '中國擾台每日數據集'
        desc = ('每日整理中國解放軍（PLA）在台灣周邊軍事活動的結構化資料，'
                '來源為中華民國國防部每日公布：共機架次、逾越海峽中線數、共艦艘數。')
        page = f'{BASE_URL}/index.html'      # 與 canonical / og:url 一致

    data = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": name,
        "description": desc,
        "url": page,
        "keywords": ["PLA", "People's Liberation Army", "Taiwan", "Taiwan Strait",
                     "ADIZ", "median line", "Taiwan Strait median line", "PLA incursions",
                     "PLAAF", "PLAN", "cross-strait tensions",
                     "解放軍", "擾台", "海峽中線", "防空識別區"],
        "creator": {"@type": "Person", "name": "Adam Pan"},
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "temporalCoverage": f"{start}/{end}",
        "dateModified": end,
        "spatialCoverage": {"@type": "Place", "name": "Taiwan Strait / Taiwan ADIZ"},
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "aircraft_total",
             "description": "PLA aircraft sorties detected per day"},
            {"@type": "PropertyValue", "name": "median_line_cross",
             "description": "Sorties crossing the Taiwan Strait median line per day"},
            {"@type": "PropertyValue", "name": "ships_total",
             "description": "PLA naval vessels detected per day"},
        ],
        "isBasedOn": "https://www.mnd.gov.tw/news/plaactlist",
        "creditText": "Source: ROC Ministry of National Defense (MND)",
        "distribution": [{
            "@type": "DataDownload",
            "encodingFormat": "text/csv",
            "contentUrl": f"{BASE_URL}/data/records.csv",
        }],
    }
    return ('\n<script type="application/ld+json">'
            + json.dumps(data, ensure_ascii=False) + '</script>')


def nav_html(active, lang, page_name, s):
    """Navigation bar with language toggle."""
    base   = '/en' if lang == 'en' else ''
    toggle = f'/{page_name}.html' if lang == 'en' else f'/en/{page_name}.html'

    pages = [
        ('index',   s['nav_index']),
        ('records', s['nav_records']),
        ('monthly', s['nav_monthly']),
        ('about',   s['nav_about']),
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
        f'<span>{s["footer_src_label"]}<a href="{s["footer_src_url"]}" target="_blank" rel="noopener">'
        f'{s["footer_src_name"]}</a></span>'
        f'<span>{s["footer_credit"]}</span>'
        f'<span>{s["footer_update"]}{update_label}</span>'
        f'<span class="footer-hub"><a href="{HUB_URL}" rel="noopener">{s["footer_hub"]}</a></span>'
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
        f'<div class="stat"><div class="stat-n y" data-count="{mo_ac}">{mo_ac}</div>'
        f'<div class="stat-l">{s["mo_aircraft"]}</div></div>'
        f'<div class="stat"><div class="stat-n y" data-count="{mo_cr}">{mo_cr}</div>'
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
/* Static HTML already holds the real numbers (for crawlers / no-JS); with JS reset to 0 then count up */
document.querySelectorAll('[data-count]').forEach(function(el){el.textContent='0';});
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


# ── 圖表匯出：高解析 PNG 下載 + 嵌入碼切換（全部瀏覽器端，無需 CI 字型）──────────
# 不複製 Chart 的 options（內含函式），只取乾淨可序列化的 config.data 重畫一張高解析圖，
# 再疊上標題與「資料來源 / 圖表出處 / 網址」浮水印，最後 toBlob 觸發下載。
_CHART_EXPORT_JS = """\
<script>(function(){
// 淺拷貝 data：保留 scriptable 函式（如漸層 backgroundColor，JSON 會把函式吃掉），
// 同時複製陣列避免與頁面上的 live chart 共用可變狀態。
function copyData(d){
  return {labels:(d.labels||[]).slice(),datasets:(d.datasets||[]).map(function(ds){
    var nd={};for(var k in ds){nd[k]=ds[k];}
    ['data','backgroundColor','pointBackgroundColor','pointBorderColor','borderColor','borderDash'].forEach(function(k){
      if(Array.isArray(ds[k]))nd[k]=ds[k].slice();});
    return nd;
  })};
}
function dtype(src){
  if(src.config.type)return src.config.type;
  var ds=src.config.data.datasets||[];
  for(var i=0;i<ds.length;i++){if(ds[i].type)return ds[i].type;}
  return 'line';
}
function renderHi(src,w,h,scale){
  var c=document.createElement('canvas');
  c.width=Math.round(w*scale);c.height=Math.round(h*scale);
  var n=(src.config.data.labels||[]).length;
  return new Chart(c.getContext('2d'),{
    type:dtype(src),
    data:copyData(src.config.data),
    options:{
      responsive:false,maintainAspectRatio:false,animation:false,devicePixelRatio:scale,
      plugins:{legend:{display:false},tooltip:{enabled:false}},
      scales:{
        x:{grid:{display:false},border:{display:false},
           ticks:{color:'#96b0b8',font:{size:12},maxRotation:0,autoSkip:n<=20,
             callback:function(v){var L=this.getLabelForValue(v);
               return n>20?((L&&String(L).endsWith('/1'))?L:''):L;}}},
        y:{grid:{color:function(x){return x.tick.value===0?'#3a4448':'rgba(58,68,72,0.22)';}},
           border:{display:false},beginAtZero:true,
           ticks:{color:'#96b0b8',font:{size:12},maxTicksLimit:4}}
      }
    }
  });
}
window.plaDownloadChart=function(btn){
  if(typeof Chart==='undefined')return;
  var d=btn.dataset;
  var acS=Chart.getChart(d.uid+'-ac'),shS=Chart.getChart(d.uid+'-sh');
  if(!acS||!shS)return;
  var old=btn.textContent;btn.disabled=true;
  var scale=2,W=1000,pad=28,head=82,gap=10,acH=360,shH=210,foot=56;
  var H=head+acH+gap+shH+foot;
  var out=document.createElement('canvas');
  out.width=W*scale;out.height=H*scale;
  var ctx=out.getContext('2d');ctx.scale(scale,scale);
  ctx.fillStyle='#0e1618';ctx.fillRect(0,0,W,H);
  ctx.textBaseline='top';
  ctx.fillStyle='#c4d4dc';
  ctx.font='700 27px "Noto Sans TC","Microsoft JhengHei","PingFang TC",system-ui,sans-serif';
  ctx.fillText(d.title||'',pad,24);
  ctx.fillStyle='#8a9faa';
  ctx.font='500 15px "Noto Sans TC","Microsoft JhengHei","PingFang TC",system-ui,sans-serif';
  ctx.fillText(d.sub||'',pad,58);
  var acC=renderHi(acS,W-pad*2,acH,scale),shC=renderHi(shS,W-pad*2,shH,scale);
  try{
    ctx.drawImage(acC.canvas,pad,head,W-pad*2,acH);
    ctx.drawImage(shC.canvas,pad,head+acH+gap,W-pad*2,shH);
  }finally{acC.destroy();shC.destroy();}   // 一定銷毀暫存 Chart，避免洩漏
  ctx.fillStyle='#0a1014';ctx.fillRect(0,H-foot,W,foot);
  ctx.fillStyle='#7c929b';ctx.textBaseline='middle';
  ctx.font='500 14px "Noto Sans TC","Microsoft JhengHei","PingFang TC",system-ui,sans-serif';
  ctx.fillText(d.wm||'',pad,H-foot/2);
  var fn=(d.fn||'chart')+'.png';
  var reset=function(){btn.disabled=false;btn.textContent=old;};
  var save=function(href,revoke){
    var a=document.createElement('a');a.href=href;a.download=fn;
    document.body.appendChild(a);a.click();
    setTimeout(function(){if(revoke)URL.revokeObjectURL(href);a.remove();},150);
    reset();
  };
  if(out.toBlob){
    out.toBlob(function(b){b?save(URL.createObjectURL(b),true):reset();},'image/png');
  }else{
    try{save(out.toDataURL('image/png'),false);}catch(e){reset();}  // 舊瀏覽器後備
  }
};
window.plaToggleEmbed=function(id){
  var el=document.getElementById(id);if(!el)return;
  var open=el.style.display==='block';
  el.style.display=open?'none':'block';
  if(!open){var ta=el.querySelector('textarea');if(ta){ta.focus();ta.select();}}
};
window.plaCopyEmbed=function(btn){
  var ta=btn.parentNode.querySelector('textarea');if(!ta)return;
  ta.focus();ta.select();
  // 真正的按鈕標籤存進 data-label，避免在「已複製」回饋期間連點時把回饋文字當原文
  var label=btn.dataset.label||btn.textContent;btn.dataset.label=label;
  var done=function(){btn.textContent=btn.dataset.done||'OK';
    setTimeout(function(){btn.textContent=btn.dataset.label;},1600);};
  var legacy=function(){try{return document.execCommand('copy');}catch(e){return false;}};
  // 只有真的成功才顯示「已複製」；全失敗就保留選取讓使用者手動 Ctrl+C
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(ta.value).then(done,function(){legacy()?done():ta.select();});
  }else{legacy()?done():ta.select();}
};
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

    recent_tools = chart_tools_html('recent', 'rc',  s['chart_recent'], today_date, s, lang)
    ytd_tools    = chart_tools_html('ytd',    'ytd', s['chart_ytd'],    today_date, s, lang)

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

    # 可被爬蟲索引的一句話 SITREP（純文字，數字直接取自當日資料）
    full_date = fmt_date_full(today_date, lang)
    if ac_val == 0:
        sitrep_text = s['sitrep_text_zero'].format(date=full_date, sh=sh_val)
    else:
        sitrep_text = s['sitrep_text'].format(
            date=full_date, ac=ac_val, ml=ml_val, rate=cr_str, sh=sh_val)
    sitrep_text_html = f'<p class="sitrep-text">{sitrep_text}</p>'

    head = make_head(lang, 'index', s, head_extra=dataset_jsonld(df, lang))
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
        <div class="stat-n y" data-count="{ac_val}">{ac_val}</div>
        <div class="stat-l">{s['stat_aircraft']}</div>
        {ac_delta}
      </div>
      <div class="stat">
        <div class="stat-n y" data-count="{ml_val}">{ml_val}</div>
        <div class="stat-l">{s['stat_median']}&nbsp;<span class="stat-detail">{cr_str}</span></div>
      </div>
      <div class="stat">
        <div class="stat-n r" data-count="{sh_val}">{sh_val}</div>
        <div class="stat-l">{s['stat_ships']}</div>
        {sh_delta}
      </div>
    </div>
  </div>

  {monthly_html}

  {map_html}

  {sitrep_text_html}

  {chart_section_html(s['chart_recent'], recent_html, split_ac, split_sh, recent_tools)}
  {chart_section_html(s['chart_ytd'], ytd_html, streak_ac, streak_sh, ytd_tools)}

</main>

{_ANIM_JS}
{_CHART_EXPORT_JS}
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


# ── about.html（方法論與資料來源）──────────────────────────────────────────────

def build_about(df, lang, out_dir, s):
    """Methodology / data-source page. Bilingual via lang branch (en = no CJK)."""
    start = df['date'].min()
    end   = df['date'].max()
    n     = len(df)
    MND   = 'https://www.mnd.gov.tw/news/plaactlist'
    CSV   = f'{BASE_URL}/data/records.csv'
    CC    = 'https://creativecommons.org/licenses/by/4.0/'
    today_label = fmt_date_display(end, lang)

    if lang == 'en':
        body = f"""\
  <article class="prose">
    <h1 class="prose-title">Methodology &amp; Data Sources</h1>
    <p class="lead">This site tracks the daily military activity of the People's Liberation
      Army (PLA) around Taiwan. Every figure is transcribed verbatim from the daily public
      releases of the Republic of China (Taiwan) Ministry of National Defense (MND) — nothing
      is estimated or inferred. This page documents the source, update process, and the
      definitions of key terms such as the "Taiwan Strait median line" versus the
      "12 nautical-mile territorial sea", so journalists and researchers can verify and cite
      the data.</p>
    <div class="about-meta">
      <span>Coverage: {start} – {end}</span>
      <span>{n} daily records</span>
      <span>License: CC BY 4.0</span>
    </div>

    <h2>Data source</h2>
    <p>The single source is the <a href="{MND}" target="_blank" rel="noopener">ROC Ministry
      of National Defense "Real-time Military Activity" bulletins</a> — the official daily
      announcements and flight-path graphics on PLA activity in the airspace and waters around
      Taiwan. This site only transcribes, structures and visualizes that data; it never
      incorporates information not confirmed by the MND.</p>

    <h2>Update frequency</h2>
    <p>Updated automatically once per day, fetched after the MND publishes around midday Taiwan
      time (≈ 12:00–14:00), with backup retry runs. If the MND is delayed or does not publish
      on a given day, that day is left blank rather than filled with an estimate. Historical
      records are append-only and never altered once written, so cited figures stay stable.</p>

    <h2>Key term definitions</h2>
    <div class="def-card">
      <div class="term">Taiwan Strait median line <span class="en">/ Davis Line</span></div>
      <p>An informal line down the centre of the Taiwan Strait, never recognized by any formal
        treaty between the two sides. For decades aircraft and vessels largely refrained from
        crossing it, so a crossing carries strong political and military signalling weight.
        However, crossing the median line <strong>does not constitute a violation of territory
        or sovereign airspace under international law</strong> and does not automatically
        trigger the right of self-defense. The "median-line crossings" figure on this site
        counts the PLA sorties that crossed this line on a given day.</p>
    </div>
    <div class="def-card">
      <div class="term">12 NM territorial sea</div>
      <p>Under the UN Convention on the Law of the Sea, the 12 nautical miles measured from the
        baseline constitute a state's territorial sea, and the airspace above it is sovereign
        airspace — the boundary that actually carries legal weight. Once PLA aircraft or vessels
        enter the territorial sea or airspace within this line, Taiwan may take defensive action
        under international law and its Defense Act. This is a different order of event from a
        median-line crossing.</p>
    </div>
    <div class="def-card">
      <div class="term">ADIZ <span class="en">Air Defense Identification Zone</span></div>
      <p>A zone declared for the early identification of airborne objects; it is far larger than
        sovereign airspace. Entering an ADIZ is not a violation of sovereignty, but is commonly
        used to gauge the intensity and posture of activity.</p>
    </div>
    <div class="def-card">
      <div class="term">Sorties &amp; vessels</div>
      <p>"Sorties" is the number of PLA aircraft missions detected that day, per the MND's own
        count; "vessels" is the number of PLA Navy ships detected that day. Other activity such
        as surveillance balloons is noted separately in the notes column of the daily records.</p>
    </div>

    <h2>How the data is compiled</h2>
    <p>The pipeline is deterministic and uses no manual estimation:</p>
    <ul>
      <li>MND bulletin → fields extracted into a single master CSV;</li>
      <li>Automated validation: median-line crossings may not exceed total sorties; the crossing
        rate must match the computed value (±1%); no duplicate dates; aircraft-type values must
        be valid;</li>
      <li>Only after validation passes are the static pages and charts generated, in both
        Chinese and English.</li>
    </ul>

    <h2>Citation &amp; license</h2>
    <p>The underlying figures are public information from the MND. This site's compilation, field
      structure and charts are released under <a href="{CC}" target="_blank" rel="noopener">CC
      BY 4.0</a>. Journalists and researchers are welcome to cite them, please credit:</p>
    <p><strong>Source: ROC Ministry of National Defense; compilation &amp; charts: PLA Activity
      Tracker ({BASE_URL}).</strong></p>
    <ul>
      <li>Raw data (CSV): <a href="{CSV}" target="_blank" rel="noopener">{CSV}</a></li>
      <li>Related posts: <a href="{BLOG_URL}" target="_blank" rel="noopener">Blog</a></li>
    </ul>
  </article>"""
    else:
        body = f"""\
  <article class="prose">
    <h1 class="prose-title">方法論與資料來源</h1>
    <p class="lead">本站每日追蹤中國解放軍（PLA）在台灣周邊的軍事活動。所有數字均逐字取自
      中華民國國防部每日公布的資料，不推估、不加工。本頁說明資料來源、更新方式，以及
      「海峽中線」與「12 浬領海線」等關鍵名詞的定義差異，供媒體與研究者查證引用。</p>
    <div class="about-meta">
      <span>資料區間：{start} ～ {end}</span>
      <span>{n} 筆每日紀錄</span>
      <span>授權：CC BY 4.0</span>
    </div>

    <h2>資料來源</h2>
    <p>唯一來源為 <a href="{MND}" target="_blank" rel="noopener">中華民國國防部「即時軍事動態」</a>，
      即國防部每日就「中共解放軍進入我周邊海空域動態」所發布的官方公告與航跡圖。
      本站僅做轉錄、結構化與視覺化，不引用任何未經國防部證實的訊息。</p>

    <h2>更新頻率</h2>
    <p>每日自動更新一次，於台灣時間中午國防部公布後擷取（約 12:00–14:00），並設有備援班次重試。
      若當日國防部延遲或未發布，則當日從缺，不以估計值填補。歷史資料一旦寫入即不再修改（僅新增），
      以確保被引用的數字穩定不變。</p>

    <h2>關鍵名詞定義</h2>
    <div class="def-card">
      <div class="term">海峽中線 <span class="en">Taiwan Strait median line / Davis Line</span></div>
      <p>台灣海峽中央一條未經雙方正式條約承認的默契分界線。長期以來兩岸軍機艦多半不越線，
        因此越線具有高度政治與軍事訊號意義。但越過中線<strong>並不構成國際法上的領土或領空侵犯</strong>，
        不會自動觸發自衛權。本站「逾越中線」數字即指當日越過此線的共機架次。</p>
    </div>
    <div class="def-card">
      <div class="term">12 浬領海線 <span class="en">12 NM territorial sea</span></div>
      <p>依《聯合國海洋法公約》，自基線起算 12 浬為一國領海，其上空為領空，是真正具法律意義的邊界。
        共機艦一旦進入此界線內的領海或領空，依國際法及我國《國防法》，台灣方得採取防衛行動。
        這與「越中線」屬於兩個不同層級的事件。</p>
    </div>
    <div class="def-card">
      <div class="term">防空識別區 <span class="en">ADIZ</span></div>
      <p>為早期識別空中目標而劃設的空域，範圍遠大於領空。進入 ADIZ 不等於侵犯主權，
        但常被用來觀察活動強度與態勢。</p>
    </div>
    <div class="def-card">
      <div class="term">架次與共艦 <span class="en">sorties &amp; vessels</span></div>
      <p>「架次」為當日偵獲的共機出動次數，以國防部計數為準；「共艦」為當日偵獲的解放軍海軍艦艇艘數。
        空飄氣球等其他活動另記於每日紀錄的備註欄。</p>
    </div>

    <h2>數據如何整理</h2>
    <p>處理流程為決定式（deterministic），不使用人工估計：</p>
    <ul>
      <li>國防部公告 → 擷取欄位寫入單一 CSV 主檔；</li>
      <li>自動驗證：逾越中線數不得大於總架次、越線率與計算值一致（容許 ±1%）、日期不重複、機型值合法；</li>
      <li>通過驗證後才產生靜態網頁與圖表，中英雙語同步輸出。</li>
    </ul>

    <h2>引用與授權</h2>
    <p>底層數字屬國防部公開資訊。本站的整理、欄位結構與圖表以
      <a href="{CC}" target="_blank" rel="noopener">CC BY 4.0</a> 釋出，歡迎媒體與研究者引用，請註明：</p>
    <p><strong>資料來源：中華民國國防部；整理與圖表：解放軍擾台動態追蹤（{BASE_URL}）。</strong></p>
    <ul>
      <li>原始資料（CSV）：<a href="{CSV}" target="_blank" rel="noopener">{CSV}</a></li>
      <li>相關發布：<a href="{BLOG_URL}" target="_blank" rel="noopener">部落格</a></li>
    </ul>
  </article>"""

    head = make_head(lang, 'about', s)
    html = f"""{head}
<body>
<header class="site-header">
  <div class="header-inner">
    <div class="site-brand">
      <div class="site-title">{s['site_title']}</div>
      <div class="site-sub">{s['site_sub']}</div>
    </div>
    {nav_html('about', lang, 'about', s)}
  </div>
</header>

<main>
{body}
</main>

{footer_html(today_label, s)}
</body></html>"""

    (out_dir / 'about.html').write_text(html, encoding='utf-8')
    print(f'[OK] {out_dir.name}/about.html' if out_dir != SITE_DIR else '[OK] about.html')


# ── sitemap.xml / robots.txt ──────────────────────────────────────────────────

# ── 可嵌入圖表頁（/embed/*.html）─────────────────────────────────────────────
# 自成一頁、樣式內嵌，給其他網站/部落格以 <iframe> 引用。noindex（不參與排名，
# 反向連結來自嵌入者頁面與頁腳回連）。圖表同樣 Chart.js 瀏覽器端渲染，無需 CI 字型。

_EMBED_CSS = (
    "*{margin:0;box-sizing:border-box}"
    "html,body{background:#090d0f}"
    "body{color:#c4d4dc;font-family:'Noto Sans TC','Microsoft JhengHei',system-ui,"
    "-apple-system,sans-serif;padding:10px}"
    ".emb{background:#0e1618;border:1px solid #1a2830;border-radius:6px;"
    "padding:12px 12px 10px;max-width:660px;margin:0 auto}"
    ".emb-h{font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;"
    "color:#8a9faa;margin-bottom:.55rem;padding-bottom:.45rem;border-bottom:1px solid #1a2830}"
    ".split-panels{background:#1e2224;border-radius:6px;padding:10px 10px 6px}"
    ".panel-wrap-ac{position:relative;height:188px}"
    ".panel-wrap-sh{position:relative;height:118px;margin-top:8px}"
    ".emb-f{display:flex;flex-wrap:wrap;gap:.25rem .7rem;align-items:center;"
    "justify-content:space-between;margin-top:.65rem;padding-top:.5rem;"
    "border-top:1px solid #1a2830;font-size:.62rem;color:#7c929b;text-decoration:none;"
    "letter-spacing:.02em}"
    ".emb-f:hover{color:#9fb3bd}"
    ".emb-cta{color:#f5c842;font-weight:700;white-space:nowrap}"
)


def build_embed(df, lang, out_dir, s):
    today_date = df.iloc[-1]['date']
    year_prefix = today_date[:4]
    embed_dir = out_dir / 'embed'
    embed_dir.mkdir(exist_ok=True)

    base = '/en' if lang == 'en' else ''
    site_link = f'{BASE_URL}{base}/index.html'

    charts = [
        ('recent', s['chart_recent'], 'er', df.tail(10),                      _CHART_JS_RECENT),
        ('ytd',    s['chart_ytd'],    'ey', df[df['date'] >= year_prefix],     _CHART_JS_YTD),
    ]
    for slug, title, uid, sl, tmpl in charts:
        panels = _build_panels(uid, sl, today_date, tmpl)
        page = (
            '<!DOCTYPE html>\n'
            f'<html lang="{s["html_lang"]}">\n<head>\n'
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<meta name="robots" content="noindex,follow">\n'
            f'<title>{title} — {s["site_title"]}</title>\n'
            f'<style>{_EMBED_CSS}</style>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>\n'
            '</head>\n<body>\n'
            '<div class="emb">\n'
            f'<div class="emb-h">{title}</div>\n'
            f'{panels}\n'
            f'<a class="emb-f" href="{site_link}" target="_top" rel="noopener">'
            f'<span>{s["embed_foot"]}</span><span class="emb-cta">{s["embed_cta"]}</span></a>\n'
            '</div>\n</body></html>'
        )
        (embed_dir / f'{slug}.html').write_text(page, encoding='utf-8')

    print(f'[OK] {("en/" if lang == "en" else "")}embed/ ({len(charts)} charts)')


def build_sitemap(df):
    """Generate sitemap.xml covering both languages, with hreflang alternates."""
    data_mod   = df['date'].max()                       # 資料頁用最新資料日期
    build_mod  = f'{_VER[:4]}-{_VER[4:6]}-{_VER[6:]}'   # 靜態頁用 build 日期
    pages = [
        ('index',   'daily',   '1.0', data_mod),
        ('records', 'daily',   '0.9', data_mod),
        ('monthly', 'weekly',  '0.7', data_mod),
        ('about',   'monthly', '0.6', build_mod),
    ]
    blocks = []
    for page, freq, prio, mod in pages:
        zh = f'{BASE_URL}/{page}.html'
        en = f'{BASE_URL}/en/{page}.html'
        for loc in (zh, en):
            blocks.append(
                '  <url>\n'
                f'    <loc>{loc}</loc>\n'
                f'    <lastmod>{mod}</lastmod>\n'
                f'    <changefreq>{freq}</changefreq>\n'
                f'    <priority>{prio}</priority>\n'
                f'    <xhtml:link rel="alternate" hreflang="zh-Hant" href="{zh}"/>\n'
                f'    <xhtml:link rel="alternate" hreflang="en" href="{en}"/>\n'
                f'    <xhtml:link rel="alternate" hreflang="x-default" href="{zh}"/>\n'
                '  </url>'
            )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
           '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
           + '\n'.join(blocks) + '\n</urlset>\n')
    (SITE_DIR / 'sitemap.xml').write_text(xml, encoding='utf-8')
    print('[OK] sitemap.xml')


def build_robots():
    """Generate robots.txt pointing at the sitemap."""
    txt = ('User-agent: *\n'
           'Allow: /\n\n'
           f'Sitemap: {BASE_URL}/sitemap.xml\n')
    (SITE_DIR / 'robots.txt').write_text(txt, encoding='utf-8')
    print('[OK] robots.txt')


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
        build_about(df, lang, out_dir, s)
        build_embed(df, lang, out_dir, s)

    build_sitemap(df)
    build_robots()

    (SITE_DIR / 'version.txt').write_text(_VER, encoding='utf-8')
    print('[OK] version.txt')
    print('[DONE] Site built →', SITE_DIR)
