"""
chart_daily.py — PLA Taiwan Strait Tracker
產出每日趨勢圖（streak chart）及雙面板圖（split panel chart）
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.font_manager as fm
import numpy as np
import os
import sys
from pathlib import Path

# ── 路徑 ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
OUTPUT_DIR = ROOT / 'output' / 'charts'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 配色系統 ──────────────────────────────────────────────────────────────────
BG_MAIN   = '#1e2224'
BG_SUB    = '#111c20'
DIVIDER   = '#2a3336'

AC_BRIGHT = '#f5c842'
AC_DIM    = '#8a7020'
AC_ZERO   = '#3a4448'

SH_BRIGHT = '#e05555'
SH_DIM    = '#7a2a2a'

TEXT_MAIN = '#dce8ec'
TEXT_SUB  = '#7a9298'
TEXT_FADE = '#3e5258'

# ── 字型（嘗試系統字型，fallback DejaVu）─────────────────────────────────────
def get_font():
    candidates = [
        'Noto Sans CJK TC', 'Microsoft JhengHei', 'PingFang TC',
        'STHeiti', 'Arial Unicode MS', 'DejaVu Sans'
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return 'DejaVu Sans'

FONT = get_font()
plt.rcParams['font.family'] = FONT
plt.rcParams['axes.unicode_minus'] = False


def dot_size_aircraft(n, n_max):
    """log scale dot size for aircraft"""
    if n == 0:
        return 1500
    if n_max <= 0:
        return 1500
    log_n = np.log1p(n)
    log_max = np.log1p(n_max)
    return 1500 + (14000 - 1500) * (log_n / log_max)


def dot_size_ships(n, n_min, n_max):
    """linear scale diamond size for ships"""
    if n_max == n_min:
        return (2500 + 5500) / 2
    return 2500 + (5500 - 2500) * (n - n_min) / (n_max - n_min)


def adaptive_fs(base_fs, n_points, threshold=14):
    """n 點超過 threshold 時縮小字體"""
    if n_points <= threshold:
        return base_fs
    return max(base_fs * threshold / n_points, base_fs * 0.45)


def make_streak_chart(df, today_date=None, out_path=None):
    """
    雙Y軸 streak chart：左=飛機，右=艦艇
    today_date: str 'YYYY-MM-DD'，若 None 則用最後一筆
    """
    if today_date is None:
        today_date = df['date'].iloc[-1]

    today_idx = df[df['date'] == today_date].index
    if len(today_idx) == 0:
        print(f"[WARN] date {today_date} not found, using last row")
        today_idx = [df.index[-1]]
    today_i = today_idx[0]

    # 只顯示當月或最近30天
    df_plot = df.copy().reset_index(drop=True)
    today_pos = df_plot[df_plot['date'] == today_date].index[0]

    ac_max = df_plot['aircraft_total'].max()
    sh_min = df_plot['ships_total'].min()
    sh_max = df_plot['ships_total'].max()

    n = len(df_plot)

    fig = plt.figure(figsize=(30, 18), facecolor=BG_MAIN)
    ax  = fig.add_axes([0.09, 0.13, 0.85, 0.62])
    ax2 = ax.twinx()

    ax.set_facecolor(BG_MAIN)
    ax2.set_facecolor(BG_MAIN)

    for spine in ax.spines.values():
        spine.set_color(DIVIDER)
    for spine in ax2.spines.values():
        spine.set_color(DIVIDER)

    # 自適應字體大小
    fs_today_num  = adaptive_fs(42, n)
    fs_other_num  = adaptive_fs(37, n)
    fs_today_xlab = adaptive_fs(47, n)
    fs_other_xlab = adaptive_fs(42, n)

    # ── 飛機 bars（Y1）──
    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        color = AC_BRIGHT if is_today else (AC_ZERO if row['aircraft_total'] == 0 else AC_DIM)
        alpha = 1.0 if is_today else 0.75
        ax.bar(i, row['aircraft_total'], color=color, alpha=alpha, width=0.6, zorder=3)
        if row['aircraft_total'] > 0:
            fs = fs_today_num if is_today else fs_other_num
            fw = 'bold' if is_today else 'normal'
            ax.text(i, row['aircraft_total'] + ac_max * 0.02, str(int(row['aircraft_total'])),
                    ha='center', va='bottom', color=AC_BRIGHT if is_today else AC_DIM,
                    fontsize=fs, fontweight=fw, fontfamily=FONT)

    # ── 艦艇 scatter（Y2）──
    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        sz = dot_size_ships(row['ships_total'], sh_min, sh_max)
        ax2.scatter(i, row['ships_total'], c=color, alpha=alpha,
                    s=sz, marker='D', zorder=4)
        fs = fs_today_num if is_today else fs_other_num
        fw = 'bold' if is_today else 'normal'
        ax2.text(i, row['ships_total'] + (sh_max - sh_min) * 0.05,
                 str(int(row['ships_total'])),
                 ha='center', va='bottom', color=SH_BRIGHT if is_today else SH_DIM,
                 fontsize=fs, fontweight=fw, fontfamily=FONT)

    # ── X 軸：Day N（上）＋日期（下）──
    date_labels = [pd.to_datetime(row['date']).strftime('%m/%d').lstrip('0').replace('/0', '/')
                   for _, row in df_plot.iterrows()]

    ax.set_xticks(range(n))
    ax.set_xticklabels([f'Day {i+1}' for i in range(n)],
                       fontsize=fs_other_xlab, color=TEXT_FADE, fontfamily=FONT)
    for i, row in enumerate(df_plot.itertuples()):
        is_today = (row.date == today_date)
        ax.get_xticklabels()[i].set_color(TEXT_MAIN if is_today else TEXT_FADE)
        ax.get_xticklabels()[i].set_fontsize(fs_today_xlab if is_today else fs_other_xlab)
        ax.get_xticklabels()[i].set_fontweight('bold' if is_today else 'normal')

    # 日期第二行
    ax.tick_params(axis='x', pad=10, length=0)
    for i, (dl, row) in enumerate(zip(date_labels, df_plot.itertuples())):
        is_today = (row.date == today_date)
        color = TEXT_MAIN if is_today else TEXT_FADE
        fs = fs_today_xlab if is_today else fs_other_xlab
        fw = 'bold' if is_today else 'normal'
        ax.text(i, -ac_max * 0.18, dl,
                ha='center', va='top', color=color,
                fontsize=fs, fontweight=fw, fontfamily=FONT,
                transform=ax.transData, clip_on=False)

    # ── Y 軸──
    ylim_top = ac_max * 1.8
    ax.set_ylim(0, ylim_top)
    ax2.set_ylim(0, sh_max * 2.0)

    ax.tick_params(axis='y', colors=AC_BRIGHT, labelsize=27, length=0)
    ax2.tick_params(axis='y', colors=SH_BRIGHT, labelsize=27, length=0)

    labelpad = int(1.5 * 25 * 0.6)
    ax.set_ylabel('SORTIES', color=AC_BRIGHT, fontsize=25, labelpad=labelpad, fontfamily=FONT)
    ax2.set_ylabel('SHIPS', color=SH_BRIGHT, fontsize=25, labelpad=labelpad, fontfamily=FONT)

    ax.yaxis.label.set_color(AC_BRIGHT)
    ax2.yaxis.label.set_color(SH_BRIGHT)

    ax.grid(axis='y', color=DIVIDER, linewidth=0.8, zorder=0)
    ax.set_xlim(-0.7, n - 0.3)

    # ── 標題區 ──
    today_row = df_plot[df_plot['date'] == today_date].iloc[0]
    today_dt  = pd.to_datetime(today_date)
    title_str = f"PLA ACTIVITY — {today_dt.strftime('%B %Y').upper()}"
    subtitle_str = (f"Day {today_pos+1}  ·  {today_dt.strftime('%Y-%m-%d')}  ·  "
                    f"Aircraft: {int(today_row['aircraft_total'])}  ·  "
                    f"Cross Line: {int(today_row['median_line_cross'])}  ·  "
                    f"Ships: {int(today_row['ships_total'])}")

    fig.text(0.04, 0.96, title_str, ha='left', va='top',
             color=TEXT_MAIN, fontsize=45, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.895, subtitle_str, ha='left', va='top',
             color=TEXT_SUB, fontsize=27, fontfamily=FONT)

    # 圖例
    fig.text(0.04, 0.833,
             '● AIRCRAFT SORTIES (left)   ◆ PLAN SHIPS (right)',
             ha='left', va='top', color=TEXT_SUB, fontsize=25, fontfamily=FONT)
    fig.text(0.04, 0.793,
             'Bright = today highlight   |   Source: ROC MND daily release',
             ha='left', va='top', color=TEXT_FADE, fontsize=23, fontfamily=FONT)

    fig.text(0.04, 0.02,
             'Data: ROC Ministry of National Defense  |  github.com/yi-tienpan/pla-tracker',
             ha='left', va='bottom', color=TEXT_FADE, fontsize=20, fontfamily=FONT)

    if out_path is None:
        out_path = OUTPUT_DIR / f"streak_{today_date}.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG_MAIN)
    plt.close(fig)
    print(f"[OK] Streak chart saved: {out_path}")
    return str(out_path)


def make_split_panel_chart(df, today_date=None, out_path=None):
    """
    雙面板圖：上=AIRCRAFT SORTIES，下=PLAN SHIPS
    """
    if today_date is None:
        today_date = df['date'].iloc[-1]

    df_plot = df.copy().reset_index(drop=True)
    today_pos = df_plot[df_plot['date'] == today_date].index[0]

    ac_max = df_plot['aircraft_total'].max()
    sh_min = df_plot['ships_total'].min()
    sh_max = df_plot['ships_total'].max()
    n = len(df_plot)

    fig = plt.figure(figsize=(30, 23), facecolor=BG_MAIN)
    gs  = gridspec.GridSpec(2, 1, left=0.10, right=0.92,
                            top=0.80, bottom=0.05, hspace=0.52)
    ax_ac = fig.add_subplot(gs[0])
    ax_sh = fig.add_subplot(gs[1])

    for ax in [ax_ac, ax_sh]:
        ax.set_facecolor(BG_MAIN)
        for spine in ax.spines.values():
            spine.set_color(DIVIDER)
        ax.tick_params(colors=TEXT_SUB, length=0)
        ax.grid(axis='y', color=DIVIDER, linewidth=0.8, zorder=0)
        ax.set_xlim(-0.7, n - 0.3)

    # 自適應字體
    fs_today_num  = adaptive_fs(42, n)
    fs_other_num  = adaptive_fs(37, n)
    fs_today_xlab = adaptive_fs(47, n)
    fs_other_xlab = adaptive_fs(42, n)

    # ── 上面板：飛機 ──
    ylim_ac = ac_max * 1.8
    ax_ac.set_ylim(0, ylim_ac)

    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        color = AC_BRIGHT if is_today else (AC_ZERO if row['aircraft_total'] == 0 else AC_DIM)
        alpha = 1.0 if is_today else 0.75
        ax_ac.bar(i, row['aircraft_total'], color=color, alpha=alpha, width=0.6, zorder=3)
        if row['aircraft_total'] > 0:
            fs = fs_today_num if is_today else fs_other_num
            fw = 'bold' if is_today else 'normal'
            ax_ac.text(i, row['aircraft_total'] + ac_max * 0.02, str(int(row['aircraft_total'])),
                       ha='center', va='bottom',
                       color=AC_BRIGHT if is_today else AC_DIM,
                       fontsize=fs, fontweight=fw, fontfamily=FONT)

    ax_ac.set_xticks(range(n))
    ax_ac.set_xticklabels(
        [f'Day {i+1}' for i in range(n)],
        fontsize=fs_other_xlab, color=TEXT_FADE, fontfamily=FONT)
    for i, row in enumerate(df_plot.itertuples()):
        is_today = (row.date == today_date)
        ax_ac.get_xticklabels()[i].set_color(TEXT_MAIN if is_today else TEXT_FADE)
        ax_ac.get_xticklabels()[i].set_fontsize(fs_today_xlab if is_today else fs_other_xlab)
        ax_ac.get_xticklabels()[i].set_fontweight('bold' if is_today else 'normal')
    ax_ac.tick_params(axis='y', colors=AC_BRIGHT, labelsize=27)

    # 面板標題：錨定在 ylim 頂部
    ax_ac.text(0.01, 1.0, 'AIRCRAFT SORTIES',
               transform=ax_ac.transAxes, ha='left', va='bottom',
               color=AC_BRIGHT, fontsize=45, fontweight='bold', fontfamily=FONT)

    # ── 下面板：艦艇 ──
    ylim_sh = sh_max * 1.8
    ax_sh.set_ylim(0, ylim_sh)

    for i, row in df_plot.iterrows():
        is_today = (row['date'] == today_date)
        color = SH_BRIGHT if is_today else SH_DIM
        alpha = 0.95 if is_today else 0.7
        sz = dot_size_ships(row['ships_total'], sh_min, sh_max)
        ax_sh.scatter(i, row['ships_total'], c=color, alpha=alpha,
                      s=sz, marker='D', zorder=4)
        fs = fs_today_num if is_today else fs_other_num
        fw = 'bold' if is_today else 'normal'
        ax_sh.text(i, row['ships_total'] + sh_max * 0.04, str(int(row['ships_total'])),
                   ha='center', va='bottom',
                   color=SH_BRIGHT if is_today else SH_DIM,
                   fontsize=fs, fontweight=fw, fontfamily=FONT)

    ax_sh.set_xticks(range(n))
    ax_sh.set_xticklabels(
        [f'Day {i+1}' for i in range(n)],
        fontsize=fs_other_xlab, color=TEXT_FADE, fontfamily=FONT)
    for i, row in enumerate(df_plot.itertuples()):
        is_today = (row.date == today_date)
        ax_sh.get_xticklabels()[i].set_color(TEXT_MAIN if is_today else TEXT_FADE)
        ax_sh.get_xticklabels()[i].set_fontsize(fs_today_xlab if is_today else fs_other_xlab)
        ax_sh.get_xticklabels()[i].set_fontweight('bold' if is_today else 'normal')
    ax_sh.tick_params(axis='y', colors=SH_BRIGHT, labelsize=27)

    ax_sh.text(0.01, 1.0, 'PLAN SHIPS',
               transform=ax_sh.transAxes, ha='left', va='bottom',
               color=SH_BRIGHT, fontsize=45, fontweight='bold', fontfamily=FONT)

    # ── 標題區 ──
    today_row = df_plot[df_plot['date'] == today_date].iloc[0]
    today_dt  = pd.to_datetime(today_date)
    title_str    = f"PLA ACTIVITY — {today_dt.strftime('%B %Y').upper()}"
    subtitle_str = (f"Day {today_pos+1}  ·  {today_dt.strftime('%Y-%m-%d')}  ·  "
                    f"Aircraft: {int(today_row['aircraft_total'])}  ·  "
                    f"Cross Line: {int(today_row['median_line_cross'])}  ·  "
                    f"Ships: {int(today_row['ships_total'])}")

    fig.text(0.04, 0.96, title_str, ha='left', va='top',
             color=TEXT_MAIN, fontsize=45, fontweight='bold', fontfamily=FONT)
    fig.text(0.04, 0.895, subtitle_str, ha='left', va='top',
             color=TEXT_SUB, fontsize=27, fontfamily=FONT)
    fig.text(0.04, 0.872,
             '● AIRCRAFT SORTIES (top)   ◆ PLAN SHIPS (bottom)',
             ha='left', va='top', color=TEXT_SUB, fontsize=25, fontfamily=FONT)
    fig.text(0.04, 0.840,
             'Bright = today highlight   |   Source: ROC MND daily release',
             ha='left', va='top', color=TEXT_FADE, fontsize=23, fontfamily=FONT)
    fig.text(0.04, 0.01,
             'Data: ROC Ministry of National Defense  |  github.com/yi-tienpan/pla-tracker',
             ha='left', va='bottom', color=TEXT_FADE, fontsize=20, fontfamily=FONT)

    if out_path is None:
        out_path = OUTPUT_DIR / f"split_{today_date}.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor=BG_MAIN)
    plt.close(fig)
    print(f"[OK] Split panel chart saved: {out_path}")
    return str(out_path)


def load_data(month=None):
    df = pd.read_csv(DATA_FILE)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    if month:
        df = df[df['date'].str.startswith(month)].reset_index(drop=True)
    return df


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=None, help='YYYY-MM-DD，預設最新一筆')
    parser.add_argument('--month', default=None, help='YYYY-MM，只顯示該月')
    parser.add_argument('--type', choices=['streak', 'split', 'both'], default='both')
    args = parser.parse_args()

    month_filter = args.month or (args.date[:7] if args.date else None)
    df = load_data(month=month_filter)

    if args.type in ('streak', 'both'):
        make_streak_chart(df, today_date=args.date)
    if args.type in ('split', 'both'):
        make_split_panel_chart(df, today_date=args.date)
