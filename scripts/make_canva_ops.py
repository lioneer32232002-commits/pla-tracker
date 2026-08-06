"""make_canva_ops.py — 產生「更新 Canva 每日圖卡」所需的編輯指令（JSON）。

背景：圖卡在 Canva 有一份手工調整過的母版（字型／效果／動畫由使用者自己維護）。
每天要換的只有兩樣：三個數字等文字，以及當日活動空域的黃色分層方框。
文字可以直接取代；**空域是形狀，Canva 的自動填入換不了**，只能刪掉重畫。

關鍵設計：空域座標**不寫死**。地圖在設計裡是一個 viewBox 1080x816 的形狀，
本腳本從該元素當下的 top/left/width/height 反推投影，再算出空域方框位置。
所以使用者之後把地圖移動或縮放，算出來的空域仍然貼合。

用法（先用 read-design 讀出地圖元素的位置，再餵進來）：
  python -X utf8 scripts/make_canva_ops.py --top 690 --left -22 --width 1125 --height 850
  python -X utf8 scripts/make_canva_ops.py --date 2026-08-05 --top ... （回填指定日期）

輸出 JSON 到 stdout：
  {"date":…, "texts":{…}, "zones":[…], "zone_labels":[…]}
`zones` 每筆已是 insert_shape 需要的欄位（缺 page_id，套用時補上）。
"""
import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
# 空域判斷共用 build_site 的同一份函式。不要在這裡重寫——實際公告寫的是
# 「西南空域」而不是「西南部」，自己重寫過一次就漏判了（2026-08-05 踩過）。
from build_site import zones_from_special  # noqa: E402

ROOT = Path(__file__).parent.parent
DATA = ROOT / 'data' / 'records.csv'

# 與 build_site.py 的 _CARD_JS 同一組常數。改那邊就要改這邊（兩處刻意同源）。
MAP_VB_W, MAP_VB_H = 1080, 816        # 地圖元素的 viewBox
LONC, LATC = 120.32, 23.78
ZSC = [1.0, 0.78, 0.58, 0.40, 0.24]   # 由外而內的縮放
ZFO = [0.04, 0.07, 0.10, 0.14, 0.19]  # 對應透明度
ZONE_COLOR = '#F5C842'

# 空域：[多邊形(lat,lon), 焦點, 標籤點]
ZP = {
    'n':  [[(25.5, 120.3), (26.5, 120.3), (26.5, 122.5), (25.5, 122.0)], (25.6, 121.2), (26.16, 120.72)],
    'c':  [[(25.05, 119.75), (25.05, 120.45), (23.6, 120.05), (23.6, 118.95)], (24.3, 119.8), (24.88, 119.98)],
    'sw': [[(23.0, 117.0), (23.0, 119.8), (21.0, 121.0), (21.0, 117.0)], (22.2, 119.5), (21.72, 117.35)],
    's':  [[(21.9, 120.05), (21.9, 121.9), (21.0, 121.9), (21.0, 120.05)], (21.45, 121.0), (21.72, 121.45)],
    'e':  [[(22.0, 122.0), (24.5, 122.0), (24.5, 123.5), (22.0, 123.5)], (23.0, 122.1), (24.28, 122.15)],
    'ne': [[(26.5, 120.7), (26.5, 122.2), (25.4, 121.8), (25.4, 121.0)], (25.5, 121.2), (25.62, 121.42)],
}
ZONE_NAMES = {'n': '北部空域', 'c': '中部空域', 'sw': '西南部空域',
              's': '南部空域', 'e': '東部空域', 'ne': '東北部空域'}

# --atlas 輸出的固定欄位。母版與其複製品的 locator id 完全相同（2026-08-06 實測：
# 拿複製品的 id 去 read-design 母版，三個元素都命中），所以可以先寫死。
# 使用者若在 Canva 裡刪掉又重畫某個元素，該 id 會失效 → 照 _readme 的指示重讀。
MASTER_DESIGN_ID = 'DAHRZtscuZM'
FOLDER_ID = 'FAFzxKT6D0A'
PAGE_ID = 'PBrY48DlSrkTrB5h'
TEXT_SLOTS = {                      # 語意名稱 → (locator id, 這格旁邊的說明文字)
    'date_range':     ('LBlNdXK4RZgP3xXX', '標題下方的日期區間'),
    'aircraft':       ('LBb6ryCyhfc7vLLQ', '大數字：共機架次'),
    'delta_aircraft': ('LBQGpt2ffdTNr5bq', '共機架次下方的增減'),
    'median_line':    ('LByw5bYZfGzvKp6N', '大數字：越過中線'),
    'cross_rate':     ('LBZg5xqdHs75jY8T', '越過中線下方的百分比'),
    'ships':          ('LBLx3NlgnZF7n7vT', '大數字：共艦'),
    'delta_ships':    ('LBd3YDqgZYwNVbLZ', '共艦下方的增減'),
    'month_line':     ('LBMnWj94YJ3FhttV', '地圖下方的月累計一行'),
}
# 新插入的空域標籤要跟母版既有標籤同款式（add_text 建出來是黑色 16px，必須補這步）
LABEL_FORMAT = {'color': ZONE_COLOR, 'font_size': 25,
                'font_weight': 'bold', 'text_align': 'center'}
ATLAS_README = (
    '六個空域的 insert_shape 指令對照表，讓沒有本機 repo 的環境（手機、雲端）也能更新 '
    'Canva 每日圖卡。用法：copy-design 母版 → read-design（open_transaction）→ '
    '先核對地圖元素 %s 的 top/left/width/height 是否等於下面的 map_element；'
    '相符才可直接套用本表，不符代表使用者移動過地圖，必須改跑 '
    'python -X utf8 scripts/make_canva_ops.py 重算。'
    '每日只需：換掉 text_slots 的八格文字、刪掉昨日空域的形狀與標籤、'
    '插入今日空域的 5 個 shapes 與 1 個 label（label 插完要再套 label_format）。'
    '完成後 commit，並把設計 move-item-to-folder 到 folder_id。'
) % 'map_element_id'


def build_zones(top, left, width, height, zone_keys):
    """算出指定空域的 insert_shape 指令與標籤位置。

    地圖投影由元素實際大小反推（元素被縮放時，viewBox 內的座標同比例縮放），
    所以使用者在 Canva 裡移動或縮放地圖後，重跑一次仍然貼合。
    """
    sx, sy = width / MAP_VB_W, height / MAP_VB_H
    cs = math.cos(math.radians(LATC))
    k = max(MAP_VB_H / 5.67 * cs, MAP_VB_W / 9.0)
    ky = k / cs
    lon0 = LONC - MAP_VB_W / 2 / k
    latt = LATC + MAP_VB_H / 2 / ky

    def page_x(lon):
        return left + (lon - lon0) * k * sx

    def page_y(lat):
        return top + (latt - lat) * ky * sy

    shapes, labels = [], []
    for zk in zone_keys:
        poly, focus, lp = ZP[zk]
        for li in range(len(ZSC) - 1, -1, -1):     # 由外而內，外層先畫
            pts = [(page_x(focus[1] + ZSC[li] * (lon - focus[1])),
                    page_y(focus[0] + ZSC[li] * (lat - focus[0]))) for lat, lon in poly]
            x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
            y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
            w, h = round(x1 - x0, 1), round(y1 - y0, 1)
            # path 用元素自身 bbox 的區域座標 → 元素外框貼齊形狀，才好單獨選取與套動畫
            d = 'M' + ' L'.join(f'{p[0]-x0:.1f} {p[1]-y0:.1f}' for p in pts) + ' Z'
            shapes.append({
                'label': f'{ZONE_NAMES[zk]}-L{len(ZSC)-li}',
                'type': 'insert_shape', 'path': d,
                'view_box_width': w, 'view_box_height': h,
                'top': round(y0, 1), 'left': round(x0, 1), 'width': w, 'height': h,
                'color': ZONE_COLOR, 'opacity': ZFO[li],
            })
        labels.append({'text': ZONE_NAMES[zk],
                       'top': round(page_y(lp[0]) - 20 * sy, 1),
                       'left': round(page_x(lp[1]) - 94 * sx, 1),
                       'width': round(188 * sx, 1)})
    return shapes, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=float, required=True, help='地圖元素在頁面上的 top')
    ap.add_argument('--left', type=float, required=True, help='地圖元素的 left')
    ap.add_argument('--width', type=float, required=True, help='地圖元素的 width')
    ap.add_argument('--height', type=float, required=True, help='地圖元素的 height')
    ap.add_argument('--date', help='要產生的日期（YYYY-MM-DD），預設最新一列')
    ap.add_argument('--atlas', action='store_true',
                    help='改為輸出「六個空域全部算好」的對照表（不讀 CSV），'
                         '用來重建 data/canva_zone_ops.json')
    args = ap.parse_args()

    if args.atlas:
        shapes, labels = build_zones(args.top, args.left, args.width, args.height, ZP)
        per = len(ZSC)
        for s in shapes:
            s['page_id'] = PAGE_ID
        for lb in labels:
            lb.update(type='add_text', page_id=PAGE_ID)
        print(json.dumps({
            '_readme': ATLAS_README,
            '_regenerate': ('python -X utf8 scripts/make_canva_ops.py --atlas '
                            '--top T --left L --width W --height H '
                            '> data/canva_zone_ops.json'),
            'master_design_id': MASTER_DESIGN_ID,
            'folder_id': FOLDER_ID,
            'page_id': PAGE_ID,
            'map_element_id': f'{PAGE_ID}-LBjrvGjrMJF1lJTH',
            'map_element': {'top': args.top, 'left': args.left,
                            'width': args.width, 'height': args.height,
                            'view_box': [MAP_VB_W, MAP_VB_H]},
            'text_slots': {k: {'element_id': f'{PAGE_ID}-{eid}', 'note': note}
                           for k, (eid, note) in TEXT_SLOTS.items()},
            'label_format': LABEL_FORMAT,
            'zones': {zk: {'name': ZONE_NAMES[zk],
                           'shapes': shapes[n * per:(n + 1) * per],
                           'label': labels[n]}
                      for n, zk in enumerate(ZP)},
        }, ensure_ascii=False, indent=1))
        return

    df = pd.read_csv(DATA, dtype=str).fillna('')
    row = df[df['date'] == args.date] if args.date else df.tail(1)
    if row.empty:
        sys.exit(f'找不到日期 {args.date}')
    row = row.iloc[0]
    idx = df.index[df['date'] == row['date']][0]
    prev = df.iloc[idx - 1] if idx > 0 else row

    def i(v):
        return int(float(v)) if str(v) not in ('', 'nan') else 0

    ac, ml, sh = i(row['aircraft_total']), i(row['median_line_cross']), i(row['ships_total'])
    cr = f"{float(row['cross_rate']):.0f}%" if row['cross_rate'] else '—'

    def delta(cur, old):
        d = i(cur) - i(old)
        if d == 0:
            return '與昨日持平'
        return f'較昨日 {"+" if d > 0 else "−"}{abs(d)}'

    dt = pd.to_datetime(row['date'])
    df_mo = df[df['date'].str.startswith(row['date'][:7])]
    mo_ac = sum(i(v) for v in df_mo['aircraft_total'])
    mo_ml = sum(i(v) for v in df_mo['median_line_cross'])
    mo_rate = f'{mo_ml / mo_ac * 100:.0f}%' if mo_ac else '—'

    zones_on = zones_from_special(row['special_event'])
    zones, labels = build_zones(args.top, args.left, args.width, args.height,
                                [zk for zk, on in zones_on.items() if on])

    out = {
        'date': row['date'],
        'texts': {
            'date_range': (dt - pd.Timedelta(days=1)).strftime('%Y.%m.%d') + ' – ' + dt.strftime('%m.%d'),
            'aircraft': str(ac), 'median_line': str(ml), 'ships': str(sh),
            'cross_rate': cr if ac else '',
            'delta_aircraft': delta(row['aircraft_total'], prev['aircraft_total']),
            'delta_ships': delta(row['ships_total'], prev['ships_total']),
            'month_line': (f'{dt.month} 月至今 {len(df_mo)} 天　｜　共機 {mo_ac} 架次'
                           f'　｜　越過中線 {mo_ml}（{mo_rate}）'),
        },
        'zones': zones,
        'zone_labels': labels,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
