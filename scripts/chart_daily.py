"""
chart_daily.py — PLA Taiwan Strait Tracker
圖表一：每日追蹤分割面板圖（Split Panel — Daily, 最近 7–8 天）
圖表二：2026 至今面積趨勢圖（Area Chart — YTD）
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import matplotlib.patheffects as pe
import numpy as np
import sys
from pathlib import Path

# ── 路徑 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
OUTPUT_DIR = ROOT / 'output' / 'charts'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 配色系統 ──────────────────────────────────────────────────────────────────
BG        = '#1e2224'
AC_BRIGHT = '#f5c842'
AC_DIM    = '#8a7020'
AC_ZERO   = '#3a4448'
SH_BRIGHT = '#e05555'
SH_DIM    = '#7a2a2a'
TXTDARK   = '#dce8ec'
TXTSUB    = '#7a9298'
TXTFADE   = '#3e5258'
CROSS_COL = '#ff9933'

# ── 字型 ──────────────────────────────────────────────────────────────────────
def get_font():
    import glob, os
    candidates = [
        'Noto Sans CJK TC', 'Noto Sans TC',
        'Noto Sans CJK SC', 'Noto Sans SC',
        'Microsoft JhengHei', 'PingFang TC',
        'STHeiti', 'Arial Unicode MS',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c

    # Ubuntu / CI：直接搜尋字型檔案並手動載入
    search_dirs = [
        '/usr/share/fonts', '/usr/local/share/fonts',
        os.path.expanduser('~/.local/share/fonts'),
        os.path.expanduser('~/.fonts'),
    ]
    patterns = ['*Noto*CJK*TC*', '*NotoSansCJKtc*', '*NotoSansCJK*TC*',
                '*NotoSansCJK-Regular*', '*Noto*CJK*']
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for pat in patterns:
            for path in glob.glob(os.path.join(d, '**', pat), recursive=True):
                if path.endswith(('.otf', '.ttf', '.ttc')):
                    try:
                        fm.fontManager.addfont(path)
                        name = fm.FontProperties(fname=path).get_name()
                        if name:
                            return name
                    except Exception:
                        pass
    return 'DejaVu Sans'

FONT = get_font()
plt.rcParams['font.family'] = FONT
plt.rcParams['font.weight'] = 'bold'
plt.rcParams['axes.unicode_minus'] = False


# ── 工具函式 ──────────────────────────────────────────────────────────────────

def dot_size_aircraft(n, n_max):
    """log scale dot size, range 1800–11000"""
    if n == 0:
        return 1800
    if n_max <= 0:
        return 1800
    t = np.log1p(n) / np.log1p(max(n_max, 1))
    return 1800 + (11000 - 1800) * t


def dot_size_ships(n, n_min, n_max):
    """linear scale diamond size, range 2500–5500"""
    if n_max == n_min:
        return (2500 + 5500) / 2
    return 2500 + (5500 - 2500) * (n - n_min) / (n_max - n_min)


def label_gap_y(ax, fig, fontsize_pts):
    """1 fontsize unit in y-axis data coordinates"""
    fig_h = fig.get_figheight()
    ax_h_frac = ax.get_position().height
    ax_h_in = ax_h_frac * fig_h
    ylim = ax.get_ylim()
    data_per_inch = (ylim[1] - ylim[0]) / ax_h_in
    return (fontsize_pts / 72.0) * data_per_inch


def scatter_radius_y(ax, fig, size_pts2):
    """scatter marker size (pts²) → radius in y-axis data units"""
    r_pts = np.sqrt(size_pts2) / 2
    fig_h = fig.get_figheight()
    ax_h_pts = ax.get_position().height * fig_h * 72
    ylim = ax.get_ylim()
    data_per_pt = (ylim[1] - ylim[0]) / ax_h_pts
    return r_pts * data_per_pt


def ceil5(x):
    return int(np.ceil(max(x, 1) / 5) * 5)


def _ystep(top):
    if top <= 10:   return 2
    elif top <= 30: return 5
    else:           return 10


def _ceil_s(x, s):
    return int(np.ceil(max(x, s) / s) * s)


def make_obs_text(row):
    """自動生成觀察文字（中文）"""
    sorties = int(row['aircraft_total']) if pd.notna(row['aircraft_total']) else 0
    cross   = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
    ships   = int(row['ships_total']) if pd.notna(row['ships_total']) else 0
    special = str(row['special_event']) if str(row['special_event']) not in ('', 'nan') else ''

    if sorties == 0:
        base = f"零架次　艦艇 {ships} 艘"
    elif cross == sorties:
        base = f"共機 {sorties} 架次，全數越線　艦艇 {ships} 艘"
    elif cross == 0:
        base = f"共機 {sorties} 架次，未越線　艦艇 {ships} 艘"
    else:
        base = f"共機 {sorties} 架次，{cross} 架越線　艦艇 {ships} 艘"

    return f"{base}　{special}" if special else base


def bold_stroke(obj, lw=2.0):
    """Simulate bold via path stroke — works on any single-weight CJK font."""
    c = obj.get_color() if hasattr(obj, 'get_color') else obj.get_facecolor()
    obj.set_path_effects([pe.Stroke(linewidth=lw, foreground=c), pe.Normal()])


def setup_ax(ax):
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_color('#2a3336')
    ax.tick_params(colors=TXTSUB, length=0)
    ax.grid(axis='y', color='#2a3336', linewidth=0.8, zorder=0)


# ── 圖表一：Split Panel（每日追蹤，最近 7–8 天）─────────────────────────────

def make_split_panel_chart(df, today_date=None, obs_text=None, out_path=None):
    """
    figsize (30, 27)，GridSpec top=0.84 bottom=0.14 hspace=0.38
    上圖：scatter dots（log scale）+ 虛線
    下圖：diamond scatter（linear scale）+ 點線
    X 軸：只在下圖，figure coordinates，兩行標籤
    """
    if today_date is None:
        today_date = df['date'].iloc[-1]

    df_plot = df.copy().reset_index(drop=True)
    n = len(df_plot)

    ac_vals = df_plot['aircraft_total'].fillna(0).astype(int)
    sh_vals = df_plot['ships_total'].fillna(0).astype(int)
    ac_max  = int(ac_vals.max())
    sh_min  = int(sh_vals.min())
    sh_max  = int(sh_vals.max())

    today_pos = int(df_plot[df_plot['date'] == today_date].index[0])
    today_row = df_plot.iloc[today_pos]
    today_dt  = pd.to_datetime(today_date)

    if obs_text is None:
        obs_text = make_obs_text(today_row)

    _dts = [pd.to_datetime(r['date']) for _, r in df_plot.iterrows()]
    _same_month = len({d.month for d in _dts}) == 1
    date_labels = ([f"{d.day}" for d in _dts] if _same_month
                   else [f"{d.month}/{d.day}" for d in _dts])

    # ── 圖形建立（去掉 ylabel 後 left 縮小）──
    fig = plt.figure(figsize=(22, 16), facecolor=BG)
    gs  = gridspec.GridSpec(2, 1,
                            left=0.08, right=0.97,
                            top=0.96,  bottom=0.13,
                            hspace=0.38)
    ax_ac = fig.add_subplot(gs[0])
    ax_sh = fig.add_subplot(gs[1])

    xs = list(range(n))

    for ax in [ax_ac, ax_sh]:
        setup_ax(ax)
        ax.set_xlim(-0.7, n - 0.3)
        ax.tick_params(axis='x', bottom=False, labelbottom=False)

    # ── 上面板：飛機（fill_between 面積圖）──
    ac_arr   = ac_vals.values.astype(float)
    cr_arr   = df_plot['median_line_cross'].fillna(0).astype(float).values
    nc_arr   = ac_arr - cr_arr

    ylim_ac_raw = max(ac_max * 1.8, 4)
    step_ac     = _ystep(ylim_ac_raw)
    ylim_ac     = _ceil_s(ylim_ac_raw, step_ac)
    ticks_ac = list(range(0, ylim_ac + 1, step_ac))
    ax_ac.set_ylim(0, ylim_ac)
    ax_ac.set_yticks(ticks_ac)
    ax_ac.set_yticklabels([str(t) for t in ticks_ac])
    _fp_ac = FontProperties(family=FONT, size=34)
    for lbl in ax_ac.get_yticklabels():
        lbl.set_fontproperties(_fp_ac); lbl.set_color(AC_BRIGHT); bold_stroke(lbl)
    ax_ac.tick_params(axis='y', length=0)

    ax_ac.fill_between(xs, 0, ac_arr, color=AC_DIM, alpha=0.4, zorder=2)
    ax_ac.fill_between(xs, nc_arr, ac_arr, color=AC_BRIGHT, alpha=0.75, zorder=3)
    ax_ac.plot(xs, ac_arr, color=AC_BRIGHT, linewidth=2.5, zorder=4)
    ax_ac.plot(xs, cr_arr, '--', color=CROSS_COL, linewidth=2.0, zorder=4)

    # 面板標題：右側靠右對齊
    _t = ax_ac.text(0.99, 0.97, '共機架次',
               transform=ax_ac.transAxes, ha='right', va='top',
               color=AC_BRIGHT, fontsize=46, fontfamily=FONT)
    bold_stroke(_t)

    # ── 下面板：艦艇 ──
    ylim_sh_raw = max(sh_max * 2.2, sh_max + 5, 5)
    step_sh     = _ystep(ylim_sh_raw)
    ylim_sh_top = _ceil_s(ylim_sh_raw, step_sh)
    ticks_sh = list(range(0, ylim_sh_top + 1, step_sh))
    ax_sh.set_ylim(-0.5, ylim_sh_top)   # -0.5 讓 y=0 的菱形不貼軸
    ax_sh.set_yticks(ticks_sh)
    ax_sh.set_yticklabels([str(t) for t in ticks_sh])
    _fp_sh = FontProperties(family=FONT, size=34)
    for lbl in ax_sh.get_yticklabels():
        lbl.set_fontproperties(_fp_sh); lbl.set_color(SH_BRIGHT); bold_stroke(lbl)
    ax_sh.tick_params(axis='y', length=0)
    ax_sh.spines['bottom'].set_visible(False)

    # connector dotted line
    ax_sh.plot(xs, sh_vals.tolist(), ':', color='#555c62', linewidth=1.8, zorder=2)

    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        v     = int(sh_vals[i])
        sz    = dot_size_ships(v, sh_min, sh_max) * 0.35
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        ax_sh.scatter(i, v, c=color, s=sz, alpha=alpha, marker='D',
                      zorder=3, clip_on=False)

        fs = 44 if is_today else 36
        fc = SH_BRIGHT if is_today else SH_DIM
        r_d = scatter_radius_y(ax_sh, fig, sz)
        gap = label_gap_y(ax_sh, fig, fs) * 0.9
        _lbl = ax_sh.text(i, v + r_d + gap, str(v),
                          ha='center', va='bottom', color=fc,
                          fontsize=fs, fontfamily=FONT, clip_on=False)
        bold_stroke(_lbl)

    # 面板標題：右側靠右對齊
    _t2 = ax_sh.text(0.99, 0.97, '解放軍艦艇',
               transform=ax_sh.transAxes, ha='right', va='top',
               color=SH_BRIGHT, fontsize=46, fontfamily=FONT)
    bold_stroke(_t2)

    # ── X 軸（figure coordinates，只在下圖底部）──
    fig.canvas.draw()
    for i in range(n):
        is_today = (df_plot.iloc[i]['date'] == today_date)
        disp = ax_sh.transData.transform((i, 0))
        xf, yf = fig.transFigure.inverted().transform(disp)

        fs  = 50 if is_today else 42
        fc  = TXTDARK if is_today else TXTSUB

        t1 = fig.text(xf, yf - 0.022, date_labels[i],
                      ha='center', va='top', color=fc, fontsize=fs, fontfamily=FONT)
        bold_stroke(t1)

    if out_path is None:
        out_path = OUTPUT_DIR / f"split_{today_date}.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f"[OK] Split panel chart saved: {out_path}")
    return str(out_path)


# ── 圖表二：Area Chart（2026 至今）──────────────────────────────────────────

def _silence_runs(sorties, min_days=2):
    """偵測連續零架次區間，回傳 [(start_i, end_i), ...]"""
    runs, start = [], None
    for i, v in enumerate(sorties):
        if v == 0:
            if start is None:
                start = i
        else:
            if start is not None:
                if i - start >= min_days:
                    runs.append((start, i - 1))
                start = None
    if start is not None and len(sorties) - start >= min_days:
        runs.append((start, len(sorties) - 1))
    return runs


def _is_local_max(vals, i, window=2):
    lo = max(0, i - window)
    hi = min(len(vals) - 1, i + window)
    return vals[i] > 0 and vals[i] >= max(vals[lo:hi + 1])


def _xaxis_show(i, n, dates, today_date):
    """只顯示每月月首"""
    return pd.to_datetime(dates[i]).day == 1


def make_streak_chart(df, today_date=None, obs_text=None, out_path=None):
    """
    figsize 動態寬度，GridSpec hspace=0.30 top=0.82 bottom=0.10
    上圖：fill_between 面積圖 + silence 標示 + peak 亮色標籤
    下圖：diamond scatter + 機動標籤（避免重疊）
    X 軸：選擇性顯示（月首 / 每 7 天 / 今日）
    """
    if today_date is None:
        today_date = df['date'].iloc[-1]

    df_plot = df.copy().reset_index(drop=True)
    n = len(df_plot)

    today_pos = int(df_plot[df_plot['date'] == today_date].index[0])
    today_row = df_plot.iloc[today_pos]
    today_dt  = pd.to_datetime(today_date)

    if obs_text is None:
        obs_text = make_obs_text(today_row)

    xs       = np.arange(n)
    sorties  = df_plot['aircraft_total'].fillna(0).astype(float).values
    crosses  = df_plot['median_line_cross'].fillna(0).astype(float).values
    noncross = sorties - crosses
    ships    = df_plot['ships_total'].fillna(0).astype(int).values
    dates    = df_plot['date'].tolist()

    ac_max  = float(sorties.max())
    sh_min  = int(ships.min())
    sh_max  = int(ships.max())
    PEAK_TH = max(ac_max * 0.25, 10)  # 高峰門檻：25% 或 10，取大值

    # ── 動態 figsize（資料多時加寬，上限 38 吋避免文字過小）──
    fig_w = min(38, max(24, n * 0.62))
    fig_h = 22

    # ── 自適應字體（只縮到 82%，保留可讀性）──
    def afs(base, floor=0.82):
        return max(base * min(1.0, 20 / max(n, 1)), base * floor)

    date_labels = [f"{pd.to_datetime(d).month}/{pd.to_datetime(d).day}" for d in dates]

    # ── 圖形建立 ──
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG)
    gs  = gridspec.GridSpec(2, 1,
                            hspace=0.30, top=0.96, bottom=0.10,
                            left=0.07,  right=0.97)
    ax_ac = fig.add_subplot(gs[0])
    ax_sh = fig.add_subplot(gs[1])

    for ax in [ax_ac, ax_sh]:
        setup_ax(ax)
        ax.set_xlim(-2.5, n - 0.5)

    # ── 上面板：飛機面積圖 ──
    ylim_ac_raw = max(ac_max * 1.45, 5)
    step_ac     = _ystep(ylim_ac_raw)
    ylim_ac     = _ceil_s(ylim_ac_raw, step_ac)
    sticks_ac   = list(range(0, ylim_ac + 1, step_ac))
    ax_ac.set_ylim(0, ylim_ac)
    ax_ac.set_yticks(sticks_ac)
    ax_ac.set_yticklabels([str(t) for t in sticks_ac])
    _sfp_ac = FontProperties(family=FONT, size=27)
    for lbl in ax_ac.get_yticklabels():
        lbl.set_fontproperties(_sfp_ac); lbl.set_color(AC_BRIGHT); bold_stroke(lbl)
    ax_ac.tick_params(axis='y', length=0)
    ax_ac.tick_params(axis='x', bottom=False, labelbottom=False)

    # silence 區間底色
    for s, e in _silence_runs(sorties, min_days=2):
        ax_ac.axvspan(s - 0.5, e + 0.5, color=AC_ZERO, alpha=0.18, zorder=1)
        mid = (s + e) / 2
        ax_ac.text(mid, ylim_ac * 0.06, '靜默',
                   ha='center', va='bottom', color=TXTFADE,
                   fontsize=afs(20), alpha=0.8, fontfamily=FONT,
                   rotation=90 if (e - s) < 3 else 0)

    # 面積填充
    ax_ac.fill_between(xs, 0, sorties, color=AC_DIM, alpha=0.35, zorder=2)
    ax_ac.fill_between(xs, noncross, sorties, color=AC_BRIGHT, alpha=0.70, zorder=3)
    ax_ac.plot(xs, sorties, color=AC_BRIGHT, linewidth=2, zorder=4)
    ax_ac.plot(xs, crosses, '--', color=CROSS_COL, linewidth=1.6, zorder=4)

    # 月份分隔線
    for i in range(1, n):
        if pd.to_datetime(dates[i]).month != pd.to_datetime(dates[i - 1]).month:
            ax_ac.axvline(i - 0.5, color='#2a3a42', linewidth=1.2, zorder=1)

    _pt = ax_ac.text(0.99, 0.97, '共機架次',
               transform=ax_ac.transAxes, ha='right', va='top',
               color=AC_BRIGHT, fontsize=48, fontfamily=FONT)
    bold_stroke(_pt)

    # ── 下面板：艦艇 ──
    ylim_sh_raw2 = max(sh_max * 1.8, sh_max + 5, 5)
    step_sh2     = _ystep(ylim_sh_raw2)
    ylim_sh2     = _ceil_s(ylim_sh_raw2, step_sh2)
    sticks_sh2   = list(range(0, ylim_sh2 + 1, step_sh2))
    ax_sh.set_ylim(0, ylim_sh2)
    ax_sh.set_yticks(sticks_sh2)
    ax_sh.set_yticklabels([str(t) for t in sticks_sh2])
    _sfp_sh = FontProperties(family=FONT, size=27)
    for lbl in ax_sh.get_yticklabels():
        lbl.set_fontproperties(_sfp_sh); lbl.set_color(SH_BRIGHT); bold_stroke(lbl)
    ax_sh.tick_params(axis='y', length=0)

    # silence 區間底色（同飛機面板）
    for s, e in _silence_runs(sorties, min_days=2):
        ax_sh.axvspan(s - 0.5, e + 0.5, color=AC_ZERO, alpha=0.12, zorder=1)

    # 月份分隔線
    for i in range(1, n):
        if pd.to_datetime(dates[i]).month != pd.to_datetime(dates[i - 1]).month:
            ax_sh.axvline(i - 0.5, color='#2a3a42', linewidth=1.2, zorder=1)

    ax_sh.plot(xs, ships, ':', color='#555c62', linewidth=1.5, zorder=2)

    # 菱形縮小，避免重疊；streak chart 用較小 size range
    sh_sz_max = max(400, 1600 - n * 20)  # n=39 → 820; n=99 → 640
    sh_sz_min = max(200, sh_sz_max * 0.45)

    for i, v in enumerate(ships):
        is_today = (dates[i] == today_date)
        raw_sz = dot_size_ships(v, sh_min, sh_max)
        sz = sh_sz_min + (sh_sz_max - sh_sz_min) * (raw_sz - 2500) / (5500 - 2500)
        sz = max(sh_sz_min, min(sh_sz_max, sz))
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        ax_sh.scatter(i, v, c=color, s=sz, alpha=alpha, marker='D',
                      zorder=3, clip_on=False)

    _pt2 = ax_sh.text(0.99, 0.97, '解放軍艦艇',
               transform=ax_sh.transAxes, ha='right', va='top',
               color=SH_BRIGHT, fontsize=48, fontfamily=FONT)
    bold_stroke(_pt2)

    # ── X 軸：選擇性顯示，全粗體，今日亮色 ──
    show_ticks = [i for i in range(n) if _xaxis_show(i, n, dates, today_date)]
    ax_sh.set_xticks(show_ticks)
    ax_sh.set_xticklabels([date_labels[i] for i in show_ticks])
    _xfp = FontProperties(family=FONT, size=34)
    for tick in ax_sh.get_xticklabels():
        tick.set_fontproperties(_xfp)
        tick.set_color(TXTSUB)
        bold_stroke(tick)
    ax_sh.tick_params(axis='x', pad=6, length=0)

    if out_path is None:
        out_path = OUTPUT_DIR / f"streak_{today_date}.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f"[OK] Area chart saved: {out_path}")
    return str(out_path)


# ── 資料載入 ──────────────────────────────────────────────────────────────────

def load_data(month=None, last_n=None):
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df = df.sort_values('date').reset_index(drop=True)
    if month:
        df = df[df['date'].str.startswith(month)].reset_index(drop=True)
    if last_n:
        df = df.tail(last_n).reset_index(drop=True)
    return df


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--date',  default=None, help='YYYY-MM-DD，預設最新一筆')
    parser.add_argument('--month', default=None, help='YYYY-MM，area chart 月份')
    parser.add_argument('--days',  type=int, default=10, help='split panel 顯示天數')
    parser.add_argument('--type',  choices=['streak', 'split', 'both'], default='both')
    args = parser.parse_args()

    # ── split panel：最近 N 天 ──
    df_all = load_data()
    today_date = args.date or df_all['date'].iloc[-1]

    if today_date in df_all['date'].values:
        idx = int(df_all[df_all['date'] == today_date].index[0])
        df_split = df_all.iloc[max(0, idx - args.days + 1): idx + 1].reset_index(drop=True)
    else:
        print(f"[WARN] date {today_date} not found, using last {args.days} rows")
        df_split = df_all.tail(args.days).reset_index(drop=True)
        today_date = df_split['date'].iloc[-1]

    # ── area chart：2026 至今全部資料 ──
    df_area = df_all  # 全部資料，不限月份

    if args.type in ('split', 'both'):
        make_split_panel_chart(df_split, today_date=today_date)
    if args.type in ('streak', 'both'):
        make_streak_chart(df_area, today_date=today_date)
