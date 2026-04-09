"""
chart_daily.py — PLA Taiwan Strait Tracker
圖表一：每日追蹤分割面板圖（Split Panel — Daily, 最近 7–8 天）
圖表二：月度面積趨勢圖（Area Chart — Monthly）
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
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
    candidates = ['Noto Sans CJK TC', 'Microsoft JhengHei', 'PingFang TC',
                  'STHeiti', 'Arial Unicode MS', 'DejaVu Sans']
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return 'DejaVu Sans'

FONT = get_font()
plt.rcParams['font.family'] = FONT
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


def make_obs_text(row):
    """auto-generate observation sentence"""
    sorties = int(row['aircraft_total']) if pd.notna(row['aircraft_total']) else 0
    cross   = int(row['median_line_cross']) if pd.notna(row['median_line_cross']) else 0
    ships   = int(row['ships_total']) if pd.notna(row['ships_total']) else 0
    special = str(row['special_event']) if str(row['special_event']) not in ('', 'nan') else ''

    if sorties == 0:
        base = f"No sorties · {ships} ships"
    elif cross == sorties:
        base = f"{sorties} {'sortie' if sorties == 1 else 'sorties'}, all crossed · {ships} ships"
    elif cross == 0:
        base = f"{sorties} {'sortie' if sorties == 1 else 'sorties'}, none crossed · {ships} ships"
    else:
        base = f"{sorties} sorties, {cross} crossed · {ships} ships"

    return f"{base} — {special}" if special else base


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

    date_labels = [f"{pd.to_datetime(r['date']).month}/{pd.to_datetime(r['date']).day}"
                   for _, r in df_plot.iterrows()]

    # ── 圖形建立 ──
    fig = plt.figure(figsize=(30, 27), facecolor=BG)
    gs  = gridspec.GridSpec(2, 1,
                            left=0.10, right=0.92,
                            top=0.84,  bottom=0.14,
                            hspace=0.38)
    ax_ac = fig.add_subplot(gs[0])
    ax_sh = fig.add_subplot(gs[1])

    xs = list(range(n))
    labelpad = int(1.5 * 25 * 0.6)

    for ax in [ax_ac, ax_sh]:
        setup_ax(ax)
        ax.set_xlim(-0.7, n - 0.3)
        ax.tick_params(axis='x', bottom=False, labelbottom=False)

    # ── 上面板：飛機 ──
    ylim_ac = max(ac_max * 1.8, 5)
    ax_ac.set_ylim(0, ylim_ac)
    ax_ac.set_yticks(range(0, ceil5(ylim_ac) + 1, 5))
    ax_ac.tick_params(axis='y', colors=AC_BRIGHT, labelsize=27)
    ax_ac.set_ylabel('Sorties', color=AC_BRIGHT, fontsize=25,
                     labelpad=labelpad, fontfamily=FONT)
    ax_ac.yaxis.label.set_color(AC_BRIGHT)

    # connector dashed line
    ax_ac.plot(xs, ac_vals.tolist(), '--', color='#555c62', linewidth=1.5, zorder=2)

    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        v     = int(ac_vals[i])
        sz    = dot_size_aircraft(v, ac_max)
        color = AC_BRIGHT if is_today else (AC_ZERO if v == 0 else AC_DIM)
        alpha = 1.0 if is_today else 0.75
        ax_ac.scatter(i, v, c=color, s=sz, alpha=alpha, zorder=3, clip_on=False)

        if v > 0 or is_today:
            fs = 42 if is_today else 37
            fw = 'bold' if is_today else 'normal'
            fc = AC_BRIGHT if is_today else AC_DIM
            r_d = scatter_radius_y(ax_ac, fig, sz)
            gap = label_gap_y(ax_ac, fig, fs) * 1.0
            ax_ac.text(i, v + r_d + gap, str(v),
                       ha='center', va='bottom', color=fc,
                       fontsize=fs, fontweight=fw, fontfamily=FONT, clip_on=False)

    # panel title: anchored at ylim_ac × 0.97 in data coords
    ax_ac.text(-0.5, ylim_ac * 0.97, 'AIRCRAFT SORTIES',
               ha='left', va='top', color=AC_BRIGHT,
               fontsize=45, fontweight='bold', fontfamily=FONT, clip_on=False)

    # ── 下面板：艦艇 ──
    sh_range = max(sh_max - sh_min, 1)
    ylim_sh  = sh_max + sh_range * 2.5 + 2
    ax_sh.set_ylim(0, max(ylim_sh, sh_max * 1.5, 5))
    ax_sh.set_yticks(range(0, ceil5(ax_sh.get_ylim()[1]) + 1, 5))
    ax_sh.tick_params(axis='y', colors=SH_BRIGHT, labelsize=27)
    ax_sh.set_ylabel('Ships', color=SH_BRIGHT, fontsize=25,
                     labelpad=labelpad, fontfamily=FONT)
    ax_sh.yaxis.label.set_color(SH_BRIGHT)

    # connector dotted line
    ax_sh.plot(xs, sh_vals.tolist(), ':', color='#555c62', linewidth=1.5, zorder=2)

    ylim_sh_top = ax_sh.get_ylim()[1]

    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        v     = int(sh_vals[i])
        sz    = dot_size_ships(v, sh_min, sh_max)
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        ax_sh.scatter(i, v, c=color, s=sz, alpha=alpha, marker='D',
                      zorder=3, clip_on=False)

        fs = 42 if is_today else 37
        fw = 'bold' if is_today else 'normal'
        fc = SH_BRIGHT if is_today else SH_DIM
        r_d = scatter_radius_y(ax_sh, fig, sz)
        gap = label_gap_y(ax_sh, fig, fs) * 1.5
        ax_sh.text(i, v + r_d + gap, str(v),
                   ha='center', va='bottom', color=fc,
                   fontsize=fs, fontweight=fw, fontfamily=FONT, clip_on=False)

    ax_sh.text(-0.5, ylim_sh_top * 0.97, 'PLAN SHIPS',
               ha='left', va='top', color=SH_BRIGHT,
               fontsize=45, fontweight='bold', fontfamily=FONT, clip_on=False)

    # ── X 軸（figure coordinates，只在下圖底部）──
    fig.canvas.draw()
    for i in range(n):
        is_today = (df_plot.iloc[i]['date'] == today_date)
        # data coord (i, 0) → display → figure fraction
        disp = ax_sh.transData.transform((i, 0))
        xf, yf = fig.transFigure.inverted().transform(disp)

        fs  = 47 if is_today else 40
        fc  = TXTDARK if is_today else TXTSUB
        fw  = 'bold' if is_today else 'normal'

        fig.text(xf, yf - 0.018, f'Day {i + 1}',
                 ha='center', va='top',
                 color=fc, fontsize=fs, fontweight=fw, fontfamily=FONT)
        fig.text(xf, yf - 0.018 - 0.040, date_labels[i],
                 ha='center', va='top',
                 color=fc, fontsize=fs, fontweight=fw, fontfamily=FONT)

    # ── 標題區 ──
    source_str = (f"Day {today_pos + 1}  ·  {today_dt.strftime('%Y-%m-%d')}  ·  "
                  f"Source: ROC Ministry of National Defense")

    fig.text(0.04, 0.968, 'PLA ACTIVITY AROUND TAIWAN',
             ha='left', va='top', color=TXTDARK,
             fontsize=54, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.934, obs_text,
             ha='left', va='top', color=AC_BRIGHT,
             fontsize=38, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.900, source_str,
             ha='left', va='top', color=TXTSUB,
             fontsize=33, fontfamily=FONT)

    if out_path is None:
        out_path = OUTPUT_DIR / f"split_{today_date}.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    print(f"[OK] Split panel chart saved: {out_path}")
    return str(out_path)


# ── 圖表二：Area Chart（月度面積趨勢）────────────────────────────────────────

def make_streak_chart(df, today_date=None, obs_text=None, out_path=None):
    """
    figsize (22, 22)，GridSpec hspace=0.30 top=0.82 bottom=0.08
    上圖：fill_between 面積圖（base + cross 疊層）
    下圖：diamond scatter + 數字標籤
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

    ac_max = float(sorties.max())
    sh_min = int(ships.min())
    sh_max = int(ships.max())

    date_labels = [f"{pd.to_datetime(r['date']).month}/{pd.to_datetime(r['date']).day}"
                   for _, r in df_plot.iterrows()]

    # ── 圖形建立 ──
    fig = plt.figure(figsize=(22, 22), facecolor=BG)
    gs  = gridspec.GridSpec(2, 1,
                            hspace=0.30, top=0.82, bottom=0.08,
                            left=0.08,  right=0.96)
    ax_ac = fig.add_subplot(gs[0])
    ax_sh = fig.add_subplot(gs[1])

    for ax in [ax_ac, ax_sh]:
        setup_ax(ax)
        ax.set_xlim(-0.5, n - 0.5)

    # ── 上面板：飛機面積圖 ──
    ylim_ac = max(ac_max * 1.35, 5)
    ax_ac.set_ylim(0, ylim_ac)
    ax_ac.set_yticks(range(0, ceil5(ylim_ac) + 1, 5))
    ax_ac.tick_params(axis='y', colors=AC_BRIGHT, labelsize=22)
    ax_ac.tick_params(axis='x', bottom=False, labelbottom=False)

    # base layer: 總架次（含未越線部分），AC_DIM alpha=0.4
    ax_ac.fill_between(xs, 0, sorties, color=AC_DIM, alpha=0.4, zorder=2)
    # top layer: 越線部分，AC_BRIGHT alpha=0.75
    ax_ac.fill_between(xs, noncross, sorties, color=AC_BRIGHT, alpha=0.75, zorder=3)
    # lines
    ax_ac.plot(xs, sorties, color=AC_BRIGHT, linewidth=2, zorder=4)
    ax_ac.plot(xs, crosses, '--', color=CROSS_COL, linewidth=1.8, zorder=4)

    ax_ac.text(0.01, 0.97, 'AIRCRAFT SORTIES',
               transform=ax_ac.transAxes, ha='left', va='top',
               color=AC_BRIGHT, fontsize=38, fontweight='bold', fontfamily=FONT)

    # ── 下面板：艦艇 ──
    ylim_sh = max(sh_max * 1.8, sh_max + 5, 5)
    ax_sh.set_ylim(0, ylim_sh)
    ax_sh.set_yticks(range(0, ceil5(ylim_sh) + 1, 5))
    ax_sh.tick_params(axis='y', colors=SH_BRIGHT, labelsize=22)

    # connector dotted line
    ax_sh.plot(xs, ships, ':', color='#555c62', linewidth=1.5, zorder=2)

    for i, v in enumerate(ships):
        is_today = (df_plot.iloc[i]['date'] == today_date)
        sz    = dot_size_ships(v, sh_min, sh_max)
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        ax_sh.scatter(i, v, c=color, s=sz, alpha=alpha, marker='D',
                      zorder=3, clip_on=False)

        fs = 33 if is_today else 29
        fw = 'bold' if is_today else 'normal'
        fc = SH_BRIGHT if is_today else SH_DIM
        r_d = scatter_radius_y(ax_sh, fig, sz)
        gap = label_gap_y(ax_sh, fig, fs) * 1.5
        ax_sh.text(i, v + r_d + gap, str(v),
                   ha='center', va='bottom', color=fc,
                   fontsize=fs, fontweight=fw, fontfamily=FONT, clip_on=False)

    ax_sh.text(0.01, 0.97, 'PLAN SHIPS',
               transform=ax_sh.transAxes, ha='left', va='top',
               color=SH_BRIGHT, fontsize=38, fontweight='bold', fontfamily=FONT)

    # ── X 軸：所有日期，今日 bold，35pt ──
    ax_sh.set_xticks(range(n))
    ax_sh.set_xticklabels(date_labels, fontsize=35, fontfamily=FONT)
    for i, tick in enumerate(ax_sh.get_xticklabels()):
        is_today = (df_plot.iloc[i]['date'] == today_date)
        tick.set_color(TXTDARK if is_today else TXTSUB)
        tick.set_fontweight('bold' if is_today else 'normal')
    ax_sh.tick_params(axis='x', pad=8)

    # ── 標題區 ──
    source_str = (f"Day {today_pos + 1}  ·  {today_dt.strftime('%Y-%m-%d')}  ·  "
                  f"Source: ROC Ministry of National Defense")

    fig.text(0.04, 0.964, 'PLA ACTIVITY AROUND TAIWAN',
             ha='left', va='top', color=TXTDARK,
             fontsize=46, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.932, obs_text,
             ha='left', va='top', color=AC_BRIGHT,
             fontsize=30, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.905, source_str,
             ha='left', va='top', color=TXTSUB,
             fontsize=26, fontfamily=FONT)

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
    parser.add_argument('--days',  type=int, default=8, help='split panel 顯示天數')
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

    # ── area chart：當月資料 ──
    month_str = args.month or today_date[:7]
    df_area = load_data(month=month_str)
    if today_date not in df_area['date'].values:
        # fallback: 使用 df_all 最後一筆所在月份
        month_str = df_all['date'].iloc[-1][:7]
        df_area = load_data(month=month_str)

    if args.type in ('split', 'both'):
        make_split_panel_chart(df_split, today_date=today_date)
    if args.type in ('streak', 'both'):
        make_streak_chart(df_area, today_date=today_date)
