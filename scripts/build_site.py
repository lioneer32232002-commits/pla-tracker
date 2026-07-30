"""
build_site.py — 讀取 records.csv，產出靜態網站（中英雙語）
圖表使用 Chart.js 瀏覽器端渲染，不需要 matplotlib 或字型安裝。
en/ 子目錄由本腳本自動產生，禁止手動修改。
"""
import html
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
import pandas as pd

ROOT      = Path(__file__).parent.parent
DATA_FILE = ROOT / 'data' / 'records.csv'
ARSENAL_FILE = ROOT / 'data' / 'arsenal.csv'          # 軍購案主表（49 案）
PEERS_FILE   = ROOT / 'data' / 'arsenal_peers.csv'    # 國際買家對比
SITE_DIR  = ROOT
SITE_DIR.mkdir(exist_ok=True)

# 正式部署網域（canonical / OG / sitemap / robots 的絕對網址基準）
BASE_URL = 'https://pla-tracker.pages.dev'
# Skyfaring 作品集主站（頁尾回連）
HUB_URL  = 'https://skyfaring.net/'
# 相關發布（部落格）
BLOG_URL = 'https://yi-tienpan.blogspot.com'


# ── 嚴重日自動配色 ────────────────────────────────────────────────────────────
# 顏色本身即資訊：平常日整站淺色、嚴重日整站深色，訪客一開頁就從色調得知態勢。
# 門檻由 203 天歷史分布決定（aircraft_total 與 median_line_cross 的聯合分布，
# 落在 P86 附近 → 約 14% 的日子被判為「嚴重」）。嚴重＝當日 aircraft_total ≥
# SEVERE_AC 且 median_line_cross ≥ SEVERE_ML；零架次日必為淺色。
SEVERE_AC = 15   # 當日共機總架次門檻
SEVERE_ML = 10   # 當日逾越中線架次門檻

# theme-color meta：深/淺各一（深色沿用原值，淺色為淺主題背景）
THEME_COLOR = {'dark': '#090d0f', 'light': '#f5f4f0'}

# 圖表注入色（既有 __XX__ 佔位符機制）：深色維持原設計，淺色為對應可讀色。
_CHART_COLORS = {
    'dark':  {'tick': '#96b0b8', 'zero': '#3a4448',
              'ac_line': '#f5c842', 'sh_line': '#e05555',
              'cr_line': '#ff9933', 'pt_ring': '#1e2224',
              'ac_today': '#f5c842', 'ac_other': '#8a7020',
              'sh_today': '#e05555', 'sh_other': '#7a2a2a'},
    'light': {'tick': '#6b7a84', 'zero': '#cfc9ba',
              'ac_line': '#d99f00', 'sh_line': '#c74040',
              'cr_line': '#cc7a1f', 'pt_ring': '#fbfaf6',
              'ac_today': '#d99f00', 'ac_other': '#d6c79b',
              'sh_today': '#c74040', 'sh_other': '#e0b9b9'},
}

# 地圖注入色（直接以裸 hex 取代，因同一顏色在 _MAP_JS 中同時出現於 JS 字串與
# 內嵌 CSS/SVG 兩種引號情境，裸 hex→裸 hex 可保留各自既有引號）。
# tiles：淺色改用 CARTO light_all 底圖，讓深色地圖標籤文字在淺主題下仍可讀。
_MAP_COLORS = {
    'dark':  {'tiles': 'dark_all',  'ml_hi': '#e05555', 'ml_lo': '#3a6070',
              'zone': '#f5c842', 'nm': '#4dba6a',
              'zlbl_sh': '0 1px 4px #000,0 0 8px #000'},
    'light': {'tiles': 'light_all', 'ml_hi': '#c23a3a', 'ml_lo': '#8196a1',
              'zone': '#c98f00', 'nm': '#2f8f4f',
              'zlbl_sh': '0 1px 3px #fff,0 0 6px #fff'},
}

# ── 軍購儀表板列舉對照 ────────────────────────────────────────────────────────
# category / delivery_status 皆為 CSV 內受控列舉；此處集中翻譯與顯示順序，
# validate.py 另有同名列舉檢查，兩邊須一致。
ARSENAL_CATEGORIES = {  # category enum → (zh, en)
    'aircraft':    ('戰機',   'Aircraft'),
    'missile':     ('飛彈',   'Missiles'),
    'ground':      ('地面',   'Ground'),
    'naval':       ('海軍',   'Naval'),
    'uas':         ('無人系統', 'Unmanned'),
    'c4isr':       ('指管情監', 'C4ISR'),
    'sustainment': ('後勤支援', 'Sustainment'),
}
ARSENAL_STATUS = {  # delivery_status enum → (zh, en, css class)
    'completed':  ('已完成', 'Completed',  'completed'),
    'delivering': ('交付中', 'Delivering', 'delivering'),
    'announced':  ('已公告', 'Announced',  'announced'),
    'unknown':    ('進度未確認', 'Unconfirmed','unknown'),
    'cancelled':  ('已終止', 'Cancelled',  'cancelled'),
}
# 主要裝備進度矩陣的名目填充比例（僅「狀態示意」，非精確交付比例；
# 精確批次數量以各案展開的 delivered_note＋來源為準）。
ARSENAL_FILL = {
    'completed':  1.00,
    'delivering': 0.35,
    'announced':  0.00,
    'unknown':    0.00,
    'cancelled':  0.00,
}

# 延宕理由對照（案 → 官方／半官方理由 → 來源）。內容逐案取自 data/arsenal.csv 的
# notes/delivered_note 欄所引來源，於此結構化。tag：official＝官方或官員對外說明；
# semi＝業界／媒體報導未經官方逐點證實；none＝查無官方說明（誠實標註，不臆測）。
ARSENAL_DELAYS = {
    '19-50': ('洛克希德馬丁因台灣客製組態的軟體開發延遲，加上供應鏈與勞動力短缺，'
              '生產進度落後，66 架全數交付恐延至 2027 年後。',
              'Lockheed Martin fell behind on software for Taiwan’s customized configuration, '
              'compounded by supply-chain and labor shortages; full delivery of all 66 jets may slip past 2027.',
              'https://www.flightglobal.com/fixed-wing/taiwan-f-16-block-70-deliveries-slip-into-2027/165025.article',
              'official'),
    '20-68': ('美方通知因作業與產能因素，Boeing 最快自 2025 年起才能開始交付，'
              '較原訂時程延後約 1 至 2 年。',
              'The US notified that, due to production and workload factors, Boeing could begin deliveries '
              'from 2025 at the earliest — roughly 1–2 years later than planned.',
              'https://navalpost.com/taiwan-harpoon-coastal-defense-system-delivery-delays/',
              'official'),
    '19-21': ('美方將約四分之一刺針飛彈庫存移撥援助烏克蘭，雷神被迫重啟已停產的生產線，'
              '對台交付延後，分批交付估延至 2031 年。',
              'The US diverted about a quarter of its Stinger inventory to Ukraine, forcing Raytheon to '
              'restart a closed line; Taiwan deliveries are pushed back, with batches estimated through 2031.',
              'https://www.scmp.com/news/china/military/article/3176376/ukraine-war-could-delay-us-stinger-missile-delivery-taiwan',
              'semi'),
    '22-70': ('國防部官員向媒體表示延遲係「美方作業延遲及其他因素」所致，未提供具體技術原因。',
              'An MND official told the press the delay was due to “US-side processing delays and other '
              'factors,” without specifying a technical cause.',
              'https://www.taiwannews.com.tw/news/5940023',
              'official'),
    '21-44': ('美方通知因俄烏戰爭排擠美國自走砲產能、優先順序調整，最快 2026 年後才能交付；'
              '台灣遂於 2022-05 終止本案，預算改增購 HIMARS。',
              'The US notified that the Russia–Ukraine war had squeezed US howitzer capacity and shifted '
              'priorities, pushing delivery past 2026; Taiwan cancelled the case in May 2022 and bought more HIMARS.',
              'https://www.taiwannews.com.tw/news/4525635',
              'official'),
    '20-07': ('據業界媒體報導（非官方直接證實），該型魚雷產線長期停產、雷神須重啟產線，完成期程遞延；'
              '台灣國防部僅證實時程遞延，未說明原因。',
              'Per trade-press reports (not directly confirmed officially), the torpedo line had long been idle '
              'and Raytheon must restart it, delaying completion; Taiwan’s MND confirmed the slip but gave no reason.',
              'https://thedefensepost.com/2025/09/01/taiwan-mk-48-torpedoes-us/',
              'semi'),
    '20-87': ('截至查證時未見官方對延遲的明確說明；僅知 2025-05 完成美方測考後，'
              '原訂 2025 年 Q4 交付之首批仍未見到貨報導。',
              'No official statement on the delay was found as of verification; after US testing completed in '
              'May 2025, the first batch due Q4 2025 still had no reported arrival.',
              '',
              'none'),
}
# 延宕對照表列出順序（依裝備重要性／案值）

# 準時／如期交付的反例（案 → 說明 → 來源；來源取自 arsenal.csv 的 source_delivery）

# ── 武器內頁（drill-down）內容 ────────────────────────────────────────────────
# 三個系統的深度頁：採購時間軸／實戰紀錄／國際買家排名／台海角色／來源。
# 內容取自已審核研究稿 output/research_2026-07-23/arsenal_{harpoon,patriot,himars}.md，
# 內容紀律：研究稿中標「查無權威來源」「建議人工核實」「非官方直接證實」者不上頁面
# （被排除的內容清單見該 session 回報）。每條實戰紀錄與時間軸節點皆附來源 URL。
ARS_DETAIL_PAGES = ['harpoon', 'patriot', 'himars']

# 同盟標籤：notes 關鍵字 → (zh, en, css)。判斷順序見 _ars_alliance_tag（先 MNNA 後北約，
# 因「主要非北約盟友」含「北約」子字串——避免 judgment.md 記載的子字串誤判坑）。
_ALLIANCE_TAG = {
    'treaty':  ('條約盟邦', 'Treaty ally', 'treaty'),
    'nato':    ('北約',     'NATO',        'nato'),
    'mnna':    ('MNNA',     'MNNA',        'mnna'),
    'partner': ('夥伴',     'Partner',     'partner'),
    'aid':     ('美援',     'US aid',      'aid'),
}

ARSENAL_DETAIL = {
    'harpoon': {
        'name_zh': '魚叉反艦飛彈', 'name_en': 'Harpoon Anti-Ship Missile',
        'variant': 'RGM-84L-4 / AGM-84L-1 Harpoon Block II',
        'has_rank': True, 'rank_key': 'harpoon',
        'teaser_zh': '1988 年螳螂行動，美軍以魚叉飛彈重創並擊沉伊朗巡防艦 Sahand——這型反艦飛彈有真實擊沉軍艦的戰史。',
        'teaser_en': 'In Operation Praying Mantis (1988) US Harpoons helped sink the Iranian frigate Sahand — a missile with a real record of sinking warships.',
        'hero': [
            ('台灣採購量', 'Taiwan quantity', '460 枚 ＋ 100 套發射系統', '460 missiles + 100 launcher sets'),
            ('案值', 'Value', '約 27.3 億美元', 'US$2.73B'),
            ('交付狀態', 'Delivery', '交付中', 'Delivering'),
        ],
        'timeline': [
            ('2020-10-26', '2020-10-26',
             'DSCA 通知國會：最多 100 套岸置防禦系統、400 枚 RGM-84L-4 Harpoon Block II 陸射飛彈，案值約 23.7 億美元，主承包商 Boeing。',
             'DSCA notifies Congress: up to 100 coastal-defense systems and 400 RGM-84L-4 Harpoon Block II land-launched missiles, ~US$2.37B, prime contractor Boeing.',
             'https://news.usni.org/2020/10/26/state-department-authorizes-2-37b-harpoon-missile-sale-to-taiwan'),
            ('2022-09-02', '2022-09-02',
             'DSCA 另核准空射型：60 枚 AGM-84L-1 Harpoon Block II，供 F-16V 使用，案值約 3.55 億美元（與岸置案不同案號）。',
             'DSCA approves an air-launched batch: 60 AGM-84L-1 Harpoon Block II for the F-16V, ~US$355M (a separate case from the coastal system).',
             'https://media.defense.gov/2024/Dec/18/2003615445/-1/-1/0/PRESS%20RELEASE%20-%20TECRO%2022-45%20CN.PDF'),
            ('2024 下半年', 'Late 2024',
             '首批裝備（發射車、搜索雷達車）運抵台灣，由海軍海鋒大隊接裝訓練。',
             'The first equipment (launch vehicles, search-radar vehicles) arrives in Taiwan; the Navy’s Hai Feng group begins fielding.',
             'https://theaviationist.com/2024/10/02/taiwan-receives-harpoon-block-ii/'),
            ('2025 起', 'From 2025',
             '岸置系統分批交付，規劃 2026 年底前取得 32 套、2028 年完成全數 400 枚飛彈交付，供新編濱海作戰指揮部使用。',
             'Coastal systems are delivered in batches; the plan calls for 32 systems by end-2026 and all 400 missiles by 2028, for the new Littoral Combat Command.',
             'https://focustaiwan.tw/politics/202510200015'),
        ],
        'combat': [
            ('1986 錫德拉灣 — 魚叉首次實戰', '1986 Gulf of Sidra — the Harpoon’s combat debut',
             '1986 年 3 月 24 日錫德拉灣航行自由行動（Attain Document III）中，美國海軍 A-6E 攻擊機以 AGM-84 魚叉飛彈擊中利比亞飛彈快艇 Waheed，該艇最終沉沒——這是魚叉飛彈史上首次實戰使用。',
             'On 24 March 1986, during freedom-of-navigation operations in the Gulf of Sidra, US Navy A-6E aircraft struck the Libyan missile boat Waheed with an AGM-84 Harpoon; the boat later sank — the Harpoon’s first combat use.',
             'https://theaviationist.com/2024/09/21/a-6-agm-84/'),
            ('1988 螳螂行動 — 擊沉伊朗巡防艦', '1988 Operation Praying Mantis — sinking an Iranian frigate',
             '1988 年 4 月 18 日螳螂行動中，美軍對伊朗海軍展開報復打擊；伊朗巡防艦 Sahand 遭包含 3 枚魚叉飛彈在內的多枚飛彈與炸彈命中，甲板大火引發彈藥殉爆而沉沒，是美國海軍二戰以來最大規模水面戰之一。（同役伊朗快艇 Joshan 主要為標準飛彈 SM-1 擊沉，非魚叉。）',
             'During Operation Praying Mantis on 18 April 1988, the Iranian frigate Sahand was hit by multiple weapons including three Harpoon missiles and sank after its magazines detonated — one of the US Navy’s largest surface actions since WWII. (In the same action the boat Joshan was sunk mainly by Standard SM-1 missiles, not Harpoon.)',
             'https://navyhistory.au/operation-praying-mantis/'),
        ],
        'combat_note_zh': '綜合多家專業軍事媒體的戰史回顧，魚叉飛彈有權威來源記載的美軍實戰使用僅 1986、1988 兩次；查無權威來源佐證的其他戰例不列入本頁。',
        'combat_note_en': 'Reviews by multiple defense outlets record only two authoritatively sourced US combat uses of the Harpoon (1986 and 1988); cases lacking authoritative sources are not listed here.',
        'role_zh': [
            '魚叉是美軍現役反艦飛彈中少數有真實戰史的型號，1986、1988 兩次行動已證明其擊沉軍艦的能力。',
            '台灣自 2020 年起採購 100 套、400 枚陸射型岸置系統，加上 60 枚空射型，案值合計逾 27 億美元。',
            '這批岸基機動飛彈與國造雄風二、三型整合後，是反登陸作戰中攔截共軍艦艇的核心一環。',
            '目前仍處分批交機與部隊整編階段（規劃 2028 年前完成全數交付），屬「戰場實績已驗證、在台仍在部署」的系統。',
        ],
        'role_en': [
            'The Harpoon is one of the few in-service US anti-ship missiles with a real combat record; the 1986 and 1988 actions proved it can sink warships.',
            'Since 2020 Taiwan has bought 100 coastal systems with 400 land-launched missiles, plus 60 air-launched rounds — over US$2.7B combined.',
            'Integrated with the indigenous Hsiung Feng II/III, these mobile coastal missiles are a core element for intercepting PLA ships in an anti-invasion fight.',
            'Fielding and unit reorganization are still under way (full delivery planned by 2028) — a system whose battlefield record is proven while its Taiwan deployment is still in progress.',
        ],
    },
    'patriot': {
        'name_zh': '愛國者防空飛彈系統', 'name_en': 'Patriot Air-Defense System',
        'variant': 'MIM-104 Patriot · PAC-2 GEM / PAC-3 / PAC-3 MSE',
        'has_rank': False, 'rank_key': 'patriot',
        'teaser_zh': '2023 年 5 月，烏克蘭以愛國者擊落俄軍號稱「無法攔截」的匕首極音速飛彈，五角大廈正式證實。',
        'teaser_en': 'In May 2023 Ukraine used a Patriot to down Russia’s “uninterceptable” Kinzhal hypersonic missile — confirmed by the Pentagon.',
        'hero': [
            ('台灣採購量', 'Taiwan quantity', 'PAC-3 330 枚（2008）＋ MSE 增購中', '330 PAC-3 (2008) + MSE on order'),
            ('案值', 'Value', '部分未公開', 'Partly undisclosed'),
            ('交付狀態', 'Delivery', '服役／持續增購', 'In service / expanding'),
        ],
        'timeline': [
            ('2008-10-03', '2008-10-03',
             '布希政府對台軍售包裹含 330 枚 PAC-3 飛彈（整體包裹約 64 億美元）。',
             'The 2008 Bush-administration arms package to Taiwan included 330 PAC-3 missiles (overall package ~US$6.4B).',
             'https://www.armscontrol.org/act/2008-11/long-delayed-arms-sales-taiwan-announced'),
            ('2010-01-29', '2010-01-29',
             'DSCA 通知國會：114 枚 PAC-3 飛彈與 3 套火力單位，約 28.1 億美元。',
             'DSCA notifies Congress of 114 PAC-3 missiles and 3 fire units, ~US$2.81B.',
             'https://www.everycrsreport.com/files/20150105_RL30957_02fd3b35f8b5350b67bd637e2e9421cb108c1f9b.html'),
            ('2020-07-09', '2020-07-09',
             'DSCA 通知國會：PAC-3 飛彈維修暨延壽認證，約 6.2 億美元。',
             'DSCA notifies Congress of PAC-3 missile refurbishment and recertification, ~US$620M.',
             'https://www.govconwire.com/articles/taiwan-requests-lockheed-pac-3-missile-recertification-via-potential-620m-fms-deal'),
            ('2019 起', 'From 2019',
             '台美確定增購愛三增程型（PAC-3 MSE），射程與攔截高度提升，規劃 2025–2026 年分批交運部署。',
             'Taiwan confirms procurement of PAC-3 MSE (greater range and intercept altitude), with phased delivery planned for 2025–2026.',
             'https://www.cna.com.tw/news/firstnews/202103310114.aspx'),
            ('2025-10', '2025-10',
             '首批 PAC-3 MSE 預計年底前交運，第 4 個愛國者營籌組中（部署細節官方列為機密）。',
             'The first PAC-3 MSE deliveries are expected by year-end; a fourth Patriot battalion is forming (deployment details withheld as classified).',
             'https://www.cna.com.tw/news/aipl/202510040208.aspx'),
        ],
        'combat': [
            ('1991 波灣戰爭 — 宣稱與檢討的落差', '1991 Gulf War — claims vs. review',
             '波灣戰爭是愛國者「宣傳成功率」與「官方事後檢討」落差最大的案例。美國政府審計署（GAO）1992 年提交國會的證詞指出，陸軍宣稱愛國者「成功攔截 70% 飛毛腿飛彈」的說法「未獲支持」。',
             'The Gulf War is where Patriot’s publicized success rate diverged most from later official review: 1992 GAO testimony to Congress found the Army’s claim of intercepting 70% of Scuds “not supported.”',
             'https://www.gao.gov/assets/t-nsiad-92-27.pdf'),
            ('達蘭慘劇 — 軟體缺陷致 28 死', 'Dhahran — a software flaw kills 28',
             '1991 年 2 月 25 日，一套連續運作逾 100 小時的愛國者因系統時脈換算累積誤差未能攔截一枚飛毛腿，該彈命中達蘭美軍營房，28 名美軍陣亡；修正軟體事發隔日才送達。這是後續美軍全面檢討系統可靠度的直接導火線。',
             'On 25 Feb 1991 a Patriot running over 100 hours failed — due to a clock-conversion rounding error — to intercept a Scud that hit a US barracks in Dhahran, killing 28; the fix arrived the next day. It directly triggered a full US review of the system’s reliability.',
             'https://www.gao.gov/products/imtec-92-26'),
            ('2003 伊拉克戰爭 — 攔截成功但友軍誤擊', '2003 Iraq War — intercepts, but fratricide',
             '2003 年愛國者成功攔截敵方彈道飛彈，但也誤擊落一架英國龍捲風戰機與一架美國 F/A-18，3 名飛行員陣亡；美方檢討歸因於系統高度自動化與敵我識別可靠度不足（國防科學委員會完整報告為機密，此處引公開摘要）。',
             'In 2003 Patriot intercepted enemy ballistic missiles but also shot down a British Tornado and a US F/A-18 in fratricide, killing three aircrew; reviews cited heavy automation and poor IFF reliability (the full Defense Science Board report is classified; a public summary is cited here).',
             'https://spacenews.com/report-cites-patriot-autonomy-factor-friendly-fire-incidents/'),
            ('2022 阿聯 — 美軍官方確認', '2022 UAE — confirmed by US forces',
             '2022 年 1 月，美軍中央司令部證實在阿聯阿爾達夫拉基地以愛國者攔截兩枚來襲飛彈，無美軍傷亡——這是美軍自 2003 年以來首次實戰發射愛國者。',
             'In January 2022 US CENTCOM confirmed Patriots intercepted two incoming missiles at Al Dhafra Air Base, UAE, with no US casualties — the first US combat firing of Patriot since 2003.',
             'https://www.centcom.mil/MEDIA/PRESS-RELEASES/Press-Release-View/Article/2909334/us-central-command-statement-on-use-of-patriots-to-defend-us-forces/'),
            ('2023 烏克蘭 — 首次證實攔截極音速飛彈', '2023 Ukraine — first confirmed hypersonic intercept',
             '2023 年 5 月，烏克蘭以愛國者於基輔近郊擊落一枚俄羅斯「匕首」（Kinzhal）極音速飛彈，五角大廈發言人於 5 月 9 日正式證實——這是俄方長期宣稱「無法攔截」的該型飛彈首次被證實擊落。',
             'In May 2023 Ukraine downed a Russian Kh-47 “Kinzhal” hypersonic missile with a Patriot near Kyiv; a Pentagon spokesman confirmed it on 9 May — the first confirmed intercept of a missile Russia had long called “uninterceptable.”',
             'https://theaviationist.com/2023/05/10/kinzhal-vs-patriot/'),
        ],
        'combat_note_zh': '沙烏地阿拉伯長期的高攔截率宣稱主要來自廠商公關與零星媒體回報，缺乏官方逐案證實，本頁不列為已證實戰果。',
        'combat_note_en': 'Saudi Arabia’s long-running high-interception claims come mainly from manufacturer PR and scattered media reports, without case-by-case official confirmation, and are not listed here as verified results.',
        'role_zh': [
            '愛國者三型（PAC-3）依公開報導部署於大台北、台中、雲嘉南高、屏東等地，估計涵蓋全台約七成人口，是台灣多層次防空反飛彈架構的核心，與國造天弓系統互補。',
            '實戰史上唯一被美國政府正式證實攔截極音速威脅的紀錄，是 2023 年烏克蘭擊落俄軍匕首飛彈一案，對評估愛國者因應解放軍精準彈道飛彈有參考價值，但戰場條件與台海未必對應。',
            '波灣戰爭的教訓提醒：任何單一武器系統的「保護傘」效果，應同時參考官方事後檢討，而非僅憑初期宣傳數字。',
            '台灣自 2019 年起增購 PAC-3 MSE，射程與攔截高度提升，顯示政府持續投資、更新這套服役逾 25 年的系統。',
        ],
        'role_en': [
            'PAC-3 units are reportedly deployed across Greater Taipei, Taichung, the Yunlin-Chiayi-Tainan-Kaohsiung belt and Pingtung, covering an estimated 70% of the population — the core of Taiwan’s layered air-and-missile defense, complementing the indigenous Tien Kung.',
            'The only combat record of a US-confirmed hypersonic intercept is Ukraine’s 2023 downing of a Russian Kinzhal — a useful reference for gauging Patriot against PLA precision ballistic missiles, though battlefield conditions differ from the Strait.',
            'The Gulf War is a caution: the “umbrella” effect of any single system should be judged against official after-action reviews, not early publicity figures.',
            'Taiwan has been adding PAC-3 MSE since 2019, with greater range and intercept altitude — a sign of continued investment in a system now more than 25 years in service.',
        ],
    },
    'himars': {
        'name_zh': '海馬斯多管火箭系統', 'name_en': 'HIMARS Rocket Artillery',
        'variant': 'M142 HIMARS · ATACMS / GMLRS',
        'has_rank': True, 'rank_key': 'himars',
        'teaser_zh': '美方官員稱 HIMARS 對俄軍後勤的打擊「等同於一次空襲」——烏克蘭戰場驗證的機動精準火力。',
        'teaser_en': 'US officials called HIMARS strikes on Russian logistics “the equivalent of an airstrike” — mobile precision fires proven in Ukraine.',
        'hero': [
            ('台灣採購量', 'Taiwan quantity', '111 套發射系統（分三批）', '111 launcher systems (three batches)'),
            ('案值', 'Value', '約 44.9 億美元', 'US$4.49B'),
            ('交付狀態', 'Delivery', '交付中', 'Delivering'),
        ],
        'timeline': [
            ('2020-10-21', '2020-10-21',
             'DSCA 通知國會首批：11 套 M142 HIMARS 發射器與 64 枚 ATACMS 等，約 4.361 億美元。',
             'First DSCA notice: 11 M142 HIMARS launchers plus 64 ATACMS and related gear, ~US$436M.',
             'https://www.cato.org/blog/taiwan-arms-backlog-november-2024-update-himars-delivery-second-trump-administration'),
            ('2024-11', '2024-11',
             '首批 11 套 HIMARS 全數運抵台灣，由陸軍第 58 砲兵指揮部接裝訓練；同批含射程約 300 公里的 ATACMS。',
             'The first 11 HIMARS arrive in Taiwan; the Army’s 58th Artillery Command begins fielding, with ~300 km-range ATACMS in the same batch.',
             'https://www.cna.com.tw/news/aipl/202411040036.aspx'),
            ('第二批 18 套', 'Second batch: 18',
             '台灣追加 18 套，規劃 2027 年交運完成（總量達 29 套）。',
             'Taiwan adds 18 more launchers, planned for delivery by 2027 (bringing the total to 29).',
             'https://def.ltn.com.tw/article/breakingnews/4292058'),
            ('2025-12-17', '2025-12-17',
             'DSCA 通知第三批：82 套 HIMARS 發射器、420 枚 ATACMS、逾千套 GMLRS 火箭，約 40.5 億美元，規劃自 2030 年起交運。',
             'Third batch (17 Dec 2025): 82 HIMARS launchers, 420 ATACMS and 1,000+ GMLRS rockets, ~US$4.05B, deliveries from 2030.',
             'https://media.defense.gov/2025/Dec/17/2003844312/-1/-1/0/PRESS%20RELEASE%20-%20TECRO%2026-01%20CN.PDF'),
        ],
        'combat': [
            ('烏克蘭（2022 起）— 美方評價', 'Ukraine (from 2022) — the US assessment',
             '2022 年 6 月美國國防部宣布提供烏克蘭 HIMARS，官員稱其 GPS 導引精準火箭對俄軍後勤節點的打擊「等同於一次空襲」、效果顯著；截至 2024 年美方累計提供逾 40 套。烏方宣稱的具體殲敵／摧毀數字未經美方逐項證實，本頁以美方評價為準。',
             'In June 2022 the US began supplying HIMARS to Ukraine; officials called its GPS-guided precision strikes on Russian logistics “the equivalent of an airstrike,” with 40+ systems provided by 2024. Ukraine’s specific destruction claims are not itemized-confirmed by the US, so this page relies on the US assessment.',
             'https://www.defensenews.com/pentagon/2022/06/01/us-will-send-himars-precision-rockets-to-ukraine/'),
            ('阿富汗（2017）— 美軍官方確認', 'Afghanistan (2017) — confirmed by US forces',
             '2017 年美國海軍陸戰隊將 HIMARS 部署至阿富汗赫爾曼德省，執行十餘次任務支援阿富汗部隊，摧毀塔利班戰鬥人員、簡易爆炸裝置製造設施與毒品加工廠。',
             'In 2017 US Marines deployed HIMARS to Helmand, Afghanistan, flying a dozen-plus missions supporting Afghan forces that destroyed Taliban fighters, IED facilities and drug labs.',
             'https://www.dvidshub.net/news/259043/himars-providing-vital-fire-support-afghan-forces-helmand'),
            ('敘利亞打擊 ISIS（2016 及 2025–26）— 美軍官方確認', 'Syria vs. ISIS (2016 & 2025–26) — confirmed by US forces',
             '2016 年美軍首次在敘利亞境內以 HIMARS 打擊 ISIS；2025 年 12 月的 Operation Hawkeye Strike，CENTCOM 明確以 HIMARS 動用逾百枚精準彈藥打擊 ISIS 通訊與後勤設施。',
             'The US first fired HIMARS in Syria against ISIS in 2016; in Operation Hawkeye Strike (Dec 2025) CENTCOM explicitly used HIMARS among 100+ precision munitions against ISIS comms and logistics nodes.',
             'https://www.dvidshub.net/video/991472/operation-hawkeye-strike-centcom-launches-operation-against-isis-syria'),
        ],
        'combat_note_zh': '2017 年拉卡戰役著名的「五個月 35,000 發」砲擊使用的是 M777 榴彈砲、非 HIMARS，已排除以免誤植戰果。',
        'combat_note_en': 'The famous “35,000 rounds in five months” at Raqqa (2017) used M777 howitzers, not HIMARS, and is excluded to avoid misattribution.',
        'role_zh': [
            'HIMARS 核心價值在「射後即走」：發射車兩分鐘內完成射擊並轉移陣地，配合輪型高機動底盤，降低共軍反砲兵偵蒐與飽和打擊的命中機率。',
            '台灣採購的 ATACMS 射程約 300 公里，可涵蓋部分中國東南沿海機場與後勤集結地，形成學者所稱「源頭打擊」能力的一環。',
            '在反登陸想定中，GMLRS 精準火箭可對灘岸集結區、臨時碼頭等目標實施精準壓制，是不對稱戰力中負責縱深打擊的一塊。',
            '分批交運意味這項能力要到 2027、2030 年後才全面到位，短期仍需與現役火砲、既有多管火箭協同運用。',
            '烏克蘭經驗顯示 HIMARS 戰力高度依賴即時目獲與情報鏈，台灣本身的偵蒐、指管能否跟得上同樣關鍵。',
        ],
        'role_en': [
            'HIMARS’ core value is “shoot-and-scoot”: a launcher can fire and displace within two minutes, and its wheeled mobility lowers the odds of PLA counter-battery detection and saturation strikes.',
            'Taiwan’s ATACMS reach ~300 km, covering some airfields and logistics hubs along China’s southeast coast — part of what analysts call a “left-of-launch” deep-strike capability.',
            'In an anti-landing fight, GMLRS precision rockets can suppress beachhead assembly areas and temporary piers — the deep-strike piece of an asymmetric, porcupine strategy.',
            'Batched deliveries mean the capability is not fully in place until after 2027 and 2030; near-term it must work alongside existing tube and rocket artillery.',
            'Ukraine shows HIMARS depends heavily on timely targeting and an intelligence chain — whether Taiwan’s own ISR and command systems keep pace is just as decisive.',
        ],
    },
}

# 全站主題（'dark' | 'light'）；由 __main__ 依當日資料呼叫 resolve_theme() 設定。
THEME = 'dark'


def resolve_theme(df):
    """決定全站主題：嚴重日 → dark，平常日（含零架次）→ light。
    嚴重＝當日 aircraft_total ≥ SEVERE_AC 且 median_line_cross ≥ SEVERE_ML。
    PLA_THEME_OVERRIDE=light|dark 可強制覆蓋——僅供本機視覺測試，CI 不設此變數。"""
    override = os.environ.get('PLA_THEME_OVERRIDE', '').strip().lower()
    if override in ('light', 'dark'):
        return override
    latest = df.iloc[-1]
    ac = int(latest['aircraft_total'])    if pd.notna(latest['aircraft_total'])    else 0
    ml = int(latest['median_line_cross']) if pd.notna(latest['median_line_cross']) else 0
    return 'dark' if (ac >= SEVERE_AC and ml >= SEVERE_ML) else 'light'


# ── 字串對照表（UI 文字全部抽在這裡）────────────────────────────────────────────

STRINGS = {
    'zh': {
        'html_lang': 'zh-Hant',
        'page_titles': {
            'index':   '中國擾台趨勢數據分析｜共機架次・海峽中線・每日更新',
            'records': '每日紀錄 — 中國擾台趨勢數據分析',
            'monthly': '月統計 — 中國擾台趨勢數據分析',
            'about':   '方法論與資料來源 — 中國擾台趨勢數據分析',
            'arsenal': '台灣對美軍購交付追蹤 — 中國擾台趨勢數據分析',
            'ars_harpoon': '魚叉反艦飛彈：台灣採購與實戰檔案 — 中國擾台趨勢數據分析',
            'ars_patriot': '愛國者防空飛彈：台灣採購與實戰檔案 — 中國擾台趨勢數據分析',
            'ars_himars':  '海馬斯多管火箭：台灣採購與實戰檔案 — 中國擾台趨勢數據分析',
        },
        'meta_descs': {
            'index':   '每日追蹤中國解放軍在台灣周邊的軍事活動：共機架次、逾越海峽中線比例、共艦數量與趨勢圖。資料來源：中華民國國防部每日公布。',
            'records': '解放軍擾台每日紀錄表：逐日共機架次、逾越中線數、機型、共艦艘數。資料來源：國防部，每日更新。',
            'monthly': '解放軍擾台月統計：每月共機總架次、逾越中線數、越線率與共艦日均。資料來源：國防部。',
            'about':   '本站方法論：資料來源（國防部每日公布）、更新頻率、海峽中線與12浬領海線的定義差異、數據整理流程與引用授權。',
            'arsenal': '2019 年以來台灣對美軍購交付追蹤：49 案、逐案案值、交付進度、延宕與官方理由，每一筆都可溯源到美國國防安全合作署（DSCA）官方公告。',
            'ars_harpoon': '魚叉反艦飛彈（Harpoon Block II）台灣採購時間軸、國際買家排名，與 1986、1988 兩次美軍實戰紀錄，逐條附來源。',
            'ars_patriot': '愛國者防空飛彈（PAC-3／MSE）台灣採購脈絡、PAC-3 使用國，以及波灣、伊拉克、烏克蘭實戰與爭議史，誠實附來源。',
            'ars_himars':  '海馬斯多管火箭（M142 HIMARS）台灣採購時間軸、國際買家排名，與烏克蘭、阿富汗、敘利亞實戰紀錄，逐條附來源。',
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
        'nav_arsenal': '軍購',
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
        'ars': {
            'topbar':      'ARMS PROCUREMENT TRACKER',
            'h1':          '台灣對美軍購追蹤',
            'sub':         '{n} 案、約 {total} 億美元，每一筆都可溯源到美國官方公告',
            'kpi_value':   '總案值',
            'kpi_cases':   '軍售案數',
            'kpi_deliver': '交付中',
            'kpi_done':    '已完成',
            'kpi_cancel':  '已終止',
            'kpi_latest':  '資料更新',
            'kpi_unit_case': '案',
            'matrix_title':  '主要裝備交付進度',
            'matrix_note':   '每張卡是一個武器系統，卡內每列是一筆採購案（同系統的多筆案子已合併在一起）。進度條只表示交付狀態（已交付／待交付／終止），交付中的案子一律畫成固定長度，不代表實際已交付的比例。標有「延宕」的卡展開後可看延宕原因與來源；其餘卡展開後是各批次明細與出處。',
            'matrix_expand': '展開明細與來源',
            'matrix_delay':  '交付進度：',
            'matrix_delay_chip': '延宕',
            'chart_title':   '歷年軍售公告金額',
            'chart_sub':     '單位：億美元 · 依 DSCA 公告年',
            'chart_top':     '當年最大三案：',
            'read_title':    '這些軍售說明什麼',
            'read_intro':    '把台灣放進「美國賣給誰、賣多少」的國際脈絡裡，可以看出美國願意把哪一級的武器交給台灣。以下每個判讀都附國際買家對比資料的來源。',
            'table_title':   '全部軍售案',
            'table_sub':     '{n} 案 · 2019 → 今',
            'th_date':   '公告日',
            'th_system': '系統',
            'th_cat':    '類別',
            'th_value':  '案值',
            'th_status': '狀態',
            'th_src':    '來源',
            'src_announce': '公告',
            'src_delivery': '交付報導',
            'card_value':  '案值',
            'card_qty':    '數量',
            'card_status': '狀態',
            'scope_title': '這頁算什麼、不算什麼',
            'scope_body': ('本頁追蹤自 2019 年起、經美國國防安全合作署（DSCA）通知國會的對台軍售案（FMS）。'
                           '<strong>公告 ≠ 已簽約 ≠ 已交付</strong>：DSCA 公告是「國會通知」階段，實際簽署發價書（LOA）與交付時程另計。'
                           '本頁不含商售案與美軍自用移撥。案值為公告上限金額，實際簽約金額常較低。'
                           '資料來源＝DSCA 官方公告與網路檔案館快照，交付進度輔以中央社／國防部／專業軍事媒體報導，逐案人工整理、逐案附來源。'
                           '武器影像為美國國防部 DVIDS 檔案照（公有領域，攝影者見各武器頁）；縮圖為同型系統示意，非台灣接裝之裝備。'),
            'divert_label': '軍購交付追蹤',
            'divert_pending': '待交付',
            'divert_yi': '億美元',
            'wcards_title':  '武器內頁 · 實戰檔案',
            'wcards_cta':    '看實戰檔案 →',
            'detail_back':   '← 軍購總覽',
            'more_title':    '更多美製武器實戰檔案',
            'tl_title':      '採購時間軸',
            'combat_title':  '實戰紀錄',
            'combat_intro':  '每一條都附來源；查無權威來源佐證者不列入本頁。',
            'rank_title':    '國際買家排名',
            'rank_intro':    '同一系統，美國賣給誰、賣多少。台灣那一列標成黃色；各國與美國的同盟關係用文字標籤標出，不只靠顏色分辨。',
            'rank_note':     '烏克蘭為美國軍援（非付費軍售 FMS），以虛線框另計。',
            'rank_q':        '數量 ',
            'rank_year':     '訂購年：',
            'rank_src':      '來源：',
            'users_title':   'PAC-3 使用國',
            'users_intro':   'PAC-3 有 CRI、MSE 等不同世代，各國採購口徑不一，數量不宜直接排名；以下列出主要使用國與其型號。',
            'role_title':    '台海防衛角色',
            'src_title':     '來源清單',
        },
    },
    'en': {
        'html_lang': 'en',
        'page_titles': {
            'index':   'PLA Activity Tracker — Taiwan Strait',
            'records': 'Daily Records — PLA Activity Tracker',
            'monthly': 'Monthly Stats — PLA Activity Tracker',
            'about':   'Methodology & Data Sources — PLA Activity Tracker',
            'arsenal': 'Taiwan–US Arms Delivery Tracker — PLA Activity Tracker',
            'ars_harpoon': 'Harpoon Missile: Taiwan Procurement & Combat Record — PLA Activity Tracker',
            'ars_patriot': 'Patriot Air-Defense: Taiwan Procurement & Combat Record — PLA Activity Tracker',
            'ars_himars':  'HIMARS: Taiwan Procurement & Combat Record — PLA Activity Tracker',
        },
        'meta_descs': {
            'index':   'Daily tracking of PLA military activity around Taiwan: aircraft sorties, Taiwan Strait median-line crossings, naval vessels and trends. Source: ROC Ministry of National Defense daily releases.',
            'records': 'Daily log of PLA activity around Taiwan: per-day sorties, median-line crossings, aircraft type and vessel counts. Source: ROC MND, updated daily.',
            'monthly': 'Monthly PLA activity statistics for the Taiwan Strait: total sorties, median-line crossings, crossing rate and average vessels per day. Source: ROC MND.',
            'about':   'Methodology: data source (ROC MND daily releases), update frequency, the difference between the Taiwan Strait median line and the 12 NM territorial sea, data compilation and citation/licensing.',
            'arsenal': 'Tracking Taiwan\'s US arms procurement since 2019: 49 cases, per-case value, delivery progress, delays and their official reasons — every entry traceable to an official US DSCA notification.',
            'ars_harpoon': 'Harpoon Block II: Taiwan\'s procurement timeline, international buyer ranking, and the two US combat uses (1986, 1988) — each entry sourced.',
            'ars_patriot': 'Patriot (PAC-3/MSE): Taiwan procurement, PAC-3 user nations, and combat and controversy history from the Gulf War to Ukraine — honestly sourced.',
            'ars_himars':  'M142 HIMARS: Taiwan\'s procurement timeline, international buyer ranking, and combat record in Ukraine, Afghanistan and Syria — each entry sourced.',
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
        'nav_arsenal': 'Arms',
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
        'ars': {
            'topbar':      'ARMS PROCUREMENT TRACKER',
            'h1':          'Taiwan–US Arms Delivery Tracker',
            'sub':         '{n} cases, {total} — every entry traceable to an official US notification',
            'kpi_value':   'Total value',
            'kpi_cases':   'Cases',
            'kpi_deliver': 'Delivering',
            'kpi_done':    'Completed',
            'kpi_cancel':  'Cancelled',
            'kpi_latest':  'Data updated',
            'kpi_unit_case': '',
            'matrix_title':  'Major Systems — Delivery Progress',
            'matrix_note':   'Each card is one weapon system; every row within it is a procurement case (multiple cases of the same system are consolidated). Bars show delivery status only (delivered / pending / cancelled); in-progress cases are drawn at a fixed length and do not represent the share actually delivered. Cards marked "Delayed" expand to the delay reason and its source; the rest expand to batch details and citations.',
            'matrix_expand': 'Details & sources',
            'matrix_delay':  'Delivery progress: ',
            'matrix_delay_chip': 'Delayed',
            'chart_title':   'Arms Sales by Year',
            'chart_sub':     'US$ billion · by DSCA notice year',
            'chart_top':     'Top 3 cases: ',
            'read_title':    'What These Sales Tell Us',
            'read_intro':    'Placing Taiwan in the international context of who the US sells to, and how much, shows what tier of weapon the US is willing to hand Taiwan. Each reading below cites the peer-buyer comparison data.',
            'table_title':   'All Arms Sales Cases',
            'table_sub':     '{n} cases · 2019 → now',
            'th_date':   'Date',
            'th_system': 'System',
            'th_cat':    'Category',
            'th_value':  'Value',
            'th_status': 'Status',
            'th_src':    'Source',
            'src_announce': 'Notice',
            'src_delivery': 'Delivery',
            'card_value':  'Value',
            'card_qty':    'Qty',
            'card_status': 'Status',
            'scope_title': 'Scope & Caveats',
            'scope_body': ('This page tracks US Foreign Military Sales (FMS) to Taiwan notified to Congress by the '
                           'Defense Security Cooperation Agency (DSCA) since 2019. '
                           '<strong>A notification is not a signed contract, and neither is a delivery.</strong> '
                           'A DSCA notice is the congressional-notification stage; the actual Letter of Offer and Acceptance (LOA) '
                           'and delivery schedule come later. Direct commercial sales and US-forces transfers are excluded. '
                           'Values are notified ceilings; signed amounts are often lower. Sources are official DSCA notices and web-archive '
                           'snapshots, with delivery progress cross-checked against CNA / MND / defense-trade press, compiled case by case with a source for each. '
                           'Weapon photos are US Department of Defense DVIDS archive images (public domain, photographer credited on each weapon page); '
                           'thumbnails depict the same system type as a representative image, not equipment as delivered to Taiwan.'),
            'divert_label': 'Arms Delivery Tracker',
            'divert_pending': 'Pending',
            'divert_yi': '',
            'wcards_title':  'Weapon Files · Combat Record',
            'wcards_cta':    'View combat file →',
            'detail_back':   '← Arms overview',
            'more_title':    'More US weapon files',
            'tl_title':      'Procurement Timeline',
            'combat_title':  'Combat Record',
            'combat_intro':  'Every entry is sourced; cases without authoritative sources are omitted.',
            'rank_title':    'International Buyers',
            'rank_intro':    'For the same system, who the US sells to and how much. Taiwan is highlighted; alliance ties are shown as text tags, not by color.',
            'rank_note':     'Ukraine is US military aid (not paid FMS) and is shown separately with a dashed outline.',
            'rank_q':        'Qty ',
            'rank_year':     'Order year: ',
            'rank_src':      'Source: ',
            'users_title':   'PAC-3 User Nations',
            'users_intro':   'PAC-3 spans generations (CRI, MSE) with non-comparable procurement scopes, so a straight quantity ranking is misleading; below are the major user nations and their variants.',
            'role_title':    'Role in Taiwan’s Defense',
            'src_title':     'Sources',
        },
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


def load_arsenal():
    """讀取軍購案主表（49 案）。value_usd_m 轉數值，其餘欄位保持字串。"""
    df = pd.read_csv(ARSENAL_FILE, dtype=str).fillna('')
    df['value_usd_m'] = pd.to_numeric(df['value_usd_m'], errors='coerce').fillna(0.0)
    return df


def load_peers():
    """讀取國際買家對比表。qty 轉數值。"""
    df = pd.read_csv(PEERS_FILE, dtype=str).fillna('')
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
    return df


def fmt_money(value_usd_m, lang):
    """金額顯示：zh 用「億」（≥10億→1位小數、以下→2位小數）；en 用 US$ 十億。"""
    if lang == 'en':
        bn = value_usd_m / 1000.0
        num = f'{bn:.1f}' if bn >= 10 else f'{bn:.2f}'
        return f'US${num}B'
    yi = value_usd_m / 100.0
    num = f'{yi:.1f}' if yi >= 10 else f'{yi:.2f}'
    return f'{num}億'


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
  --nav-active:#1c2a33;
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
nav{display:flex;gap:.15rem;align-items:center;background:var(--sur);
  border:1px solid var(--bdr);border-radius:999px;padding:.22rem}
nav a{color:var(--sub);text-decoration:none;font-size:.72rem;
  font-weight:700;letter-spacing:.07em;text-transform:uppercase;white-space:nowrap;
  padding:.34em .85em;border-radius:999px;transition:color .15s,background .15s}
nav a:hover{color:var(--tx)}
nav a.active{color:var(--tx);background:var(--nav-active)}
nav a.lang-toggle{border:0;border-left:1px solid var(--bdr);border-radius:0;
  margin-left:.15rem;padding-left:.9em}

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

/* ── Arsenal dashboard ── */
.ars-hero{margin:.5rem 0 1.5rem}
.ars-h1{font-size:1.7rem;font-weight:800;letter-spacing:-.02em;color:var(--tx);line-height:1.15}
html[lang="zh-Hant"] .ars-h1{font-size:1.85rem}
.ars-sub{font-size:.9rem;color:var(--sub);line-height:1.6;margin-top:.5rem;max-width:640px}
.ars-section{margin-bottom:2.25rem}
.ars-sec-title{font-size:.8rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;
  color:var(--sub);white-space:normal;padding-bottom:.5rem;margin-bottom:1rem;border-bottom:1px solid var(--bdr)}
html[lang="zh-Hant"] .ars-sec-title{font-size:.95rem;letter-spacing:.12em}
.ars-sec-title .sub{font-weight:600;letter-spacing:.04em;color:var(--sub);opacity:.75;margin-left:.6rem;text-transform:none}
.ars-lead{font-size:.88rem;color:var(--sub);line-height:1.7;margin:-.3rem 0 1rem;max-width:680px}
html[lang="zh-Hant"] .ars-lead{font-size:.9rem}

/* KPI grid */
.ars-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin-bottom:2rem}
.ars-kpi{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);padding:.85rem 1rem}
.ars-kpi-n{font-size:1.9rem;font-weight:800;line-height:1;letter-spacing:-.03em;
  font-variant-numeric:tabular-nums;color:var(--tx)}
.ars-kpi-n.y{color:var(--y)}
.ars-kpi-n small{font-size:.9rem;font-weight:700;margin-left:.15rem}
.ars-kpi-l{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--sub);margin-top:.4rem;white-space:nowrap}
html[lang="zh-Hant"] .ars-kpi-l{font-size:.78rem;letter-spacing:.04em}

/* System card wall (裝備系統卡片牆) */
.ars-syscards{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.ars-syscard{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);overflow:hidden;
  display:flex;flex-direction:column}
.ars-syscard>summary{list-style:none;cursor:pointer;display:flex;flex-direction:column}
.ars-syscard>summary::-webkit-details-marker{display:none}
.ars-scard-img{width:100%;aspect-ratio:16/9;overflow:hidden;background:var(--bg);
  border-bottom:1px solid var(--bdr)}
.ars-scard-img img{width:100%;height:100%;object-fit:cover;display:block}
.ars-scard-band{display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:.35rem;background:var(--sur) repeating-linear-gradient(45deg,
  transparent 0 14px,var(--bdr) 14px 15px)}
.ars-scard-band .band-word{font-size:1.05rem;font-weight:800;letter-spacing:.35em;
  color:var(--sub);opacity:.55;padding-left:.35em}
.ars-scard-band .band-note{font-size:.62rem;letter-spacing:.08em;color:var(--sub);opacity:.5}
.ars-scard-body{padding:.75rem .85rem;display:flex;flex-direction:column;flex:1;min-width:0}
.ars-scard-head{display:flex;gap:.6rem;align-items:flex-start;justify-content:space-between}
.ars-scard-ph{width:40px;height:40px;border-radius:8px;border:1px solid var(--bdr);background:var(--bg);
  display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.72rem;font-weight:700;flex-shrink:0}
.ars-scard-titles{min-width:0;flex:1}
.ars-scard-name{font-size:.9rem;font-weight:800;color:var(--tx);line-height:1.3}
.ars-scard-name .en{display:block;font-size:.7rem;font-weight:600;color:var(--sub);margin-top:.15rem;letter-spacing:.01em;line-height:1.35}
.ars-scard-agg{font-size:.78rem;font-weight:700;color:var(--tx);font-variant-numeric:tabular-nums;
  white-space:nowrap;text-align:right;flex-shrink:0;line-height:1.3}
.ars-scard-agg .brk{display:block;font-size:.66rem;font-weight:600;color:var(--sub);opacity:.9;white-space:normal;margin-top:.15rem}
.ars-scard-rows{display:flex;flex-direction:column;gap:.55rem;margin-top:.7rem}
.ars-scard-row-top{display:flex;align-items:center;gap:.45rem;margin-bottom:.32rem}
.ars-scard-case{font-size:.64rem;font-weight:700;color:var(--sub);font-variant-numeric:tabular-nums;
  background:var(--bg);border:1px solid var(--bdr);border-radius:4px;padding:.1em .4em;flex-shrink:0}
.ars-scard-qty{font-size:.74rem;color:var(--tx);font-variant-numeric:tabular-nums;flex:1;min-width:0;font-weight:600}
.ars-st{font-size:.62rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;
  padding:.16em .55em;border-radius:999px;white-space:nowrap;flex-shrink:0}
.ars-st.completed {background:#123016;color:#5fce77}
.ars-st.delivering{background:#2a2408;color:var(--y)}
.ars-st.announced {background:#0d1d2e;color:#6aaee0}
.ars-st.unknown   {background:var(--sur);color:var(--sub);border:1px solid var(--bdr)}
.ars-st.cancelled {background:#2c1414;color:#e08585}
.ars-bar{display:flex;gap:2px;height:12px;border-radius:6px;overflow:hidden;background:var(--bg)}
.ars-seg{height:100%}
.ars-seg-d{background:var(--y)}
.ars-seg-p{background:rgba(245,200,66,.26)}
.ars-seg-c{flex:1;background:repeating-linear-gradient(45deg,#3a4448 0 5px,#222a2e 5px 10px)}
.ars-scard-foot{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin-top:.7rem}
.ars-delaychip{font-size:.62rem;font-weight:800;letter-spacing:.05em;padding:.14em .5em;border-radius:999px;
  white-space:nowrap;flex-shrink:0;color:var(--y);border:1px solid var(--y);background:transparent}
.ars-caret{color:var(--sub);font-size:.7rem;display:inline-flex;align-items:center;gap:.3rem}
.ars-syscard[open] .ars-caret .tri{transform:rotate(90deg)}
.ars-caret .tri{transition:transform .15s;display:inline-block}
.ars-scard-detail{padding:0 .85rem .8rem}
.ars-scard-seg{margin-top:.6rem}
.ars-scard-seg-h{font-size:.72rem;font-weight:700;color:var(--tx);margin-bottom:.2rem;font-variant-numeric:tabular-nums}
.ars-detail{padding:0;font-size:.8rem;color:var(--sub);line-height:1.7}
html[lang="zh-Hant"] .ars-detail{font-size:.84rem}
.ars-detail .lbl{font-weight:700;color:var(--tx)}
.ars-detail a{color:var(--y);text-decoration:none;border-bottom:1px solid #4a3f12;word-break:break-all}
.ars-detail a:hover{color:#fff}
.ars-note{font-size:.72rem;color:var(--sub);line-height:1.6;margin-top:.75rem;opacity:.85}
html[lang="zh-Hant"] .ars-note{font-size:.76rem}

/* Annual chart */
.ars-chart-wrap{background:#1e2224;border-radius:var(--rad);padding:12px 12px 8px}
.ars-chart-canvas{position:relative;height:240px}

/* Qualitative reads */
.ars-reads{display:flex;flex-direction:column;gap:.7rem}
.ars-point{background:var(--sur);border:1px solid var(--bdr);border-left:3px solid var(--y);
  border-radius:0 var(--rad) var(--rad) 0;padding:.75rem 1rem}
.ars-point h3{font-size:.9rem;font-weight:800;color:var(--tx);margin-bottom:.35rem;letter-spacing:.01em}
.ars-point p{font-size:.83rem;color:var(--sub);line-height:1.7}
html[lang="zh-Hant"] .ars-point p{font-size:.87rem}
.ars-point .caveat{color:var(--y);font-weight:600}
.ars-src{font-size:.72rem;margin-top:.45rem}
.ars-src a{color:var(--sub);text-decoration:none;border-bottom:1px solid var(--bdr);margin-right:.7rem;word-break:break-word}
.ars-src a:hover{color:var(--y);border-bottom-color:var(--y)}

/* Delay table + counter cards */

/* Category badge */
.ars-cat{display:inline-block;padding:.15em .55em;border-radius:999px;font-size:.68rem;font-weight:700;white-space:nowrap}
.ars-cat.aircraft   {background:#0d1d2e;color:#6aaee0}
.ars-cat.missile    {background:#2c1414;color:#e08585}
.ars-cat.ground     {background:#272008;color:var(--y)}
.ars-cat.naval      {background:#07231f;color:#4fc7ad}
.ars-cat.uas        {background:#20143a;color:#b898dc}
.ars-cat.c4isr      {background:#08262b;color:#4fc2d0}
.ars-cat.sustainment{background:var(--sur);color:var(--sub);border:1px solid var(--bdr)}

/* All-cases: desktop table (mobile → cards) */
.ars-cases .ars-cards{display:none}
.ars-cases a.src{color:var(--sub);text-decoration:none;border-bottom:1px solid var(--bdr)}
.ars-cases a.src:hover{color:var(--y);border-bottom-color:var(--y)}
.ars-card{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);overflow:hidden;margin-bottom:.5rem}
.ars-card>summary{list-style:none;cursor:pointer;padding:.7rem .9rem}
.ars-card>summary::-webkit-details-marker{display:none}
.ars-card-top{display:flex;justify-content:space-between;gap:.6rem;align-items:baseline}
.ars-card-sys{font-size:.85rem;font-weight:700;color:var(--tx);line-height:1.3}
.ars-card-meta{display:flex;flex-wrap:wrap;gap:.4rem .9rem;margin-top:.5rem;font-size:.74rem;color:var(--sub);
  font-variant-numeric:tabular-nums;align-items:center}
.ars-card-body{padding:0 .9rem .8rem;font-size:.8rem;color:var(--sub);line-height:1.7}
html[lang="zh-Hant"] .ars-card-body{font-size:.84rem}

/* Scope note */
.ars-scope{font-size:.72rem;color:var(--sub);line-height:1.75;margin-top:1rem;
  padding:.85rem 1rem;background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad)}
html[lang="zh-Hant"] .ars-scope{font-size:.76rem}
.ars-scope strong{color:var(--tx)}
.ars-scope .st{display:block;font-size:.7rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--sub);margin-bottom:.45rem}

/* Homepage → arsenal diversion card */
.ars-divert{display:block;text-decoration:none;background:var(--sur);border:1px solid var(--bdr);
  border-left:3px solid var(--y);border-radius:0 var(--rad) var(--rad) 0;padding:.7rem 1rem;
  margin:0 0 2rem;transition:border-color .15s,background .15s}
.ars-divert:hover{background:#12201a;border-left-color:var(--y)}
html[data-theme="light"] .ars-divert:hover{background:#f3f0e6}
.ars-divert .row{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;font-size:.82rem}
.ars-divert .lab{font-weight:800;color:var(--y);letter-spacing:.02em}
.ars-divert .txt{color:var(--sub);line-height:1.5}
.ars-divert .arr{color:var(--sub)}
html[lang="zh-Hant"] .ars-divert .row{font-size:.86rem}

/* ── Arsenal weapon detail pages ── */
.ars-back{display:inline-block;font-size:.75rem;font-weight:700;letter-spacing:.04em;
  color:var(--sub);text-decoration:none;margin-bottom:.55rem}
.ars-back:hover{color:var(--y)}
/* weapon-page hero banner (only rendered when assets/arsenal/hero-{page}.jpg exists) */
.ars-hero-imgwrap{position:relative;max-height:260px;overflow:hidden;border-radius:var(--rad);margin-bottom:1rem}
.ars-hero-img{display:block;width:100%;max-height:260px;object-fit:cover}
.ars-hero-courtesy{position:absolute;right:.6rem;bottom:.5rem;font-size:.62rem;color:#fff;
  background:rgba(0,0,0,.55);padding:.15em .55em;border-radius:999px;letter-spacing:.02em}
/* vertical procurement timeline */
.ars-tl{position:relative;margin-left:.4rem;padding-left:1.1rem;border-left:2px solid var(--bdr)}
.ars-tl-item{position:relative;padding:0 0 1.05rem}
.ars-tl-item:last-child{padding-bottom:0}
.ars-tl-item::before{content:'';position:absolute;left:calc(-1.1rem - 5px);top:.3rem;
  width:9px;height:9px;border-radius:50%;background:var(--y);border:2px solid var(--bg)}
.ars-tl-date{font-size:.74rem;font-weight:800;letter-spacing:.04em;color:var(--y);
  font-variant-numeric:tabular-nums;margin-bottom:.18rem}
.ars-tl-body{font-size:.84rem;color:var(--sub);line-height:1.7}
html[lang="zh-Hant"] .ars-tl-body{font-size:.88rem}
.ars-tl-body a{color:var(--y);text-decoration:none;border-bottom:1px solid #4a3f12;
  font-size:.72rem;margin-left:.25rem;white-space:nowrap}
.ars-tl-body a:hover{color:#fff}
/* ranking chart wrap (variable height set inline) */
.ars-rank-canvas{position:relative;width:100%}
/* PAC-3 user wall */
.ars-userwall{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}
.ars-usercard{background:var(--sur);border:1px solid var(--bdr);border-radius:var(--rad);padding:.75rem .9rem}
.ars-uc-top{display:flex;justify-content:space-between;align-items:center;gap:.5rem;margin-bottom:.32rem}
.ars-uc-country{font-size:.9rem;font-weight:800;color:var(--tx)}
.ars-uc-var{font-size:.76rem;color:var(--y);font-weight:600;margin-bottom:.3rem}
.ars-uc-meta{font-size:.72rem;color:var(--sub);line-height:1.5;font-variant-numeric:tabular-nums}
.ars-uc-meta a.src{color:var(--sub);text-decoration:none;border-bottom:1px solid var(--bdr)}
.ars-uc-meta a.src:hover{color:var(--y);border-bottom-color:var(--y)}
/* alliance tag chip (text label, not color-only) */
.ars-atag{display:inline-block;padding:.12em .5em;border-radius:999px;font-size:.62rem;
  font-weight:800;letter-spacing:.03em;white-space:nowrap}
.ars-atag.treaty {background:#123016;color:#5fce77}
.ars-atag.nato   {background:#0d1d2e;color:#6aaee0}
.ars-atag.mnna   {background:#20143a;color:#b898dc}
.ars-atag.partner{background:#2a2408;color:var(--y)}
.ars-atag.aid    {background:#2c1414;color:#e08585}
/* Taiwan-defense role list */
.ars-role{list-style:none;display:flex;flex-direction:column;gap:.55rem}
.ars-role li{position:relative;padding-left:1.1rem;font-size:.86rem;color:var(--sub);line-height:1.75}
html[lang="zh-Hant"] .ars-role li{font-size:.9rem}
.ars-role li::before{content:'\\25b8';position:absolute;left:0;top:0;color:var(--y);font-weight:800}
/* source list */
.ars-srclist{list-style:none;display:flex;flex-direction:column;gap:.35rem}
.ars-srclist li{font-size:.76rem;line-height:1.5}
.ars-srclist a{color:var(--sub);text-decoration:none;border-bottom:1px solid var(--bdr);word-break:break-all}
.ars-srclist a:hover{color:var(--y);border-bottom-color:var(--y)}
/* weapon internal-page cards (on arsenal index) */
.ars-wcards{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}
.ars-wcard{display:flex;flex-direction:column;background:var(--sur);border:1px solid var(--bdr);
  border-radius:var(--rad);overflow:hidden;text-decoration:none;border-top:3px solid var(--y);
  transition:background .15s,transform .15s}
.ars-wcard:hover{background:#12201a;transform:translateY(-2px)}
html[data-theme="light"] .ars-wcard:hover{background:#f3f0e6}
.ars-wcard-img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}
.ars-wcard-body{display:flex;flex-direction:column;flex:1;padding:.9rem 1rem}
.ars-wcard-name{font-size:.95rem;font-weight:800;color:var(--tx);line-height:1.25}
.ars-wcard-var{font-size:.68rem;color:var(--sub);margin-top:.2rem;letter-spacing:.02em}
.ars-wcard-teaser{font-size:.8rem;color:var(--sub);line-height:1.65;margin:.55rem 0 .7rem;flex:1}
html[lang="zh-Hant"] .ars-wcard-teaser{font-size:.84rem}
.ars-wcard-cta{font-size:.72rem;font-weight:800;color:var(--y);letter-spacing:.03em}
/* source chip (arsenal only — replaces default blue browser links).
   selector uses a.src-chip so it wins over the earlier .ars-detail/.ars-src/
   .ars-tl-body/.ars-srclist context link rules (same specificity, later in source). */
a.src-chip{display:inline-flex;align-items:center;gap:.25em;font-size:.68rem;font-weight:600;
  color:var(--sub);text-decoration:none;border:1px solid var(--bdr);border-radius:999px;
  padding:.12em .6em;background:var(--sur);letter-spacing:.02em;white-space:nowrap;
  transition:color .15s,border-color .15s;vertical-align:middle}
a.src-chip:hover{color:var(--tx);border-color:var(--y)}
a.src-chip::after{content:'\\2197';font-size:.85em;opacity:.7}
.ars-srclist li{display:flex;align-items:baseline;gap:.45rem;flex-wrap:wrap}
.src-full{font-size:.7rem;color:var(--sub);opacity:.68;word-break:break-all;line-height:1.5}

/* ── Mobile ── */
@media(max-width:640px){
  .top-bar{display:none}
  .site-header{padding:.7rem 1rem}
  .header-inner{gap:.5rem}
  nav{gap:.05rem;padding:.18rem;flex-wrap:nowrap}
  nav a{padding:.3em .5em;letter-spacing:.03em;font-size:.66rem}
  main{padding:.6rem 1rem 1rem}
  /* en 導覽新增「Arms」後手機寬度超出 343px 預算 → 壓字級至 .62rem 保持單行 */
  html[lang="en"] nav a{font-size:.62rem;letter-spacing:.02em;padding:.3em .42em}
  .alert{margin-bottom:1rem}
  .sitrep{padding:.55rem .9rem .6rem;margin-bottom:.55rem}
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
  /* arsenal mobile */
  .ars-kpis{grid-template-columns:repeat(2,1fr);gap:.5rem}
  .ars-kpi-n{font-size:1.6rem}
  .ars-h1{font-size:1.5rem}
  html[lang="zh-Hant"] .ars-h1{font-size:1.55rem}
  .ars-cases .ars-cards{display:block}
  .ars-cases .ars-tbl-wrap{display:none}
  .ars-chart-canvas{height:220px}
  .ars-wcards{grid-template-columns:1fr}
  .ars-userwall{grid-template-columns:1fr}
  .ars-syscards{grid-template-columns:1fr}
}
@media(max-width:380px){
  .stat-n{font-size:1.9rem}
  nav{gap:.05rem}
  html[lang="zh-Hant"] nav a{font-size:.78rem;letter-spacing:.03em}
}

/* ── 淺色主題（平常日）── :root 即深色主題，維持不動；以下僅覆蓋顏色/邊框色/陰影，
   絕不改動任何 padding / margin / font-size，版面高度與深色版一致 ── */
html[data-theme="light"]{
  --bg:#f5f4f0; --sur:#ffffff; --bdr:#e3dfd4;
  --tx:#20262b; --sub:#5d6b75; --y:#9a7500; --r:#c23a3a; --grn:#2f8f4f;
  --nav-active:#eee9db;
}
html[data-theme="light"] .top-bar{background:#eceadf}
html[data-theme="light"] .alert{background:#fdf6dd;border-color:#eadfae;
  border-left-color:#6f5600;color:#6f5600}
html[data-theme="light"] .badge.manned    {background:#e4f3dc;color:#2f7a1e}
html[data-theme="light"] .badge.uav       {background:#dbeaf6;color:#1f6fa8}
html[data-theme="light"] .badge.mixed     {background:#f3ecc9;color:#8a6a00}
html[data-theme="light"] .badge.helicopter{background:#ece1f7;color:#7a4fb0}
html[data-theme="light"] .delta-up,html[data-theme="light"] .delta-dn{color:var(--tx)}
html[data-theme="light"] th{background:#f0eee6}
html[data-theme="light"] tr:hover td{background:#f7f5ee}
/* 深色版 .split-panels 無邊框；淺色改用 inset box-shadow 模擬 1px 描邊，
   不佔版面寬高（符合「版面高度不得改變」硬約束，box-shadow 為允許變更項）。 */
html[data-theme="light"] .split-panels{background:#fbfaf6;
  box-shadow:inset 0 0 0 1px var(--bdr)}
html[data-theme="light"] .prose a{border-bottom-color:#d9c98a}
html[data-theme="light"] .prose a:hover{color:var(--tx);border-bottom-color:var(--y)}
html[data-theme="light"] .map-wrap{background:#fbfaf6}
html[data-theme="light"] .leaflet-tile-pane{filter:saturate(.9) contrast(1.02)}
html[data-theme="light"] .leaflet-control-attribution{
  background:rgba(255,255,255,0.85)!important;color:#5d6b75!important;
  border-top-color:#e3dfd4!important}
html[data-theme="light"] .leaflet-control-attribution a{color:#5d6b75!important}
html[data-theme="light"] .leaflet-control-zoom a{
  background:#ffffff!important;color:var(--sub)!important}
html[data-theme="light"] .leaflet-control-zoom a:hover{
  background:#eee9db!important;color:var(--tx)!important}
html[data-theme="light"] .map-lbl{color:#33454f;
  text-shadow:0 1px 4px #fff,0 0 8px rgba(255,255,255,.9)}
html[data-theme="light"] .map-lbl-sm{color:#5d7079;
  text-shadow:0 1px 3px #fff,0 0 6px #fff}
html[data-theme="light"] .map-info{background:rgba(255,255,255,0.9)}
html[data-theme="light"] .map-ml-label{color:#5a7280}
html[data-theme="light"] .map-note{background:#eef4ee;border-left-color:#2f8f4f}

/* ── Arsenal 淺色覆蓋（僅顏色，不動版面尺寸）── */
html[data-theme="light"] .ars-chart-wrap{background:#fbfaf6;box-shadow:inset 0 0 0 1px var(--bdr)}
html[data-theme="light"] .ars-seg-p{background:rgba(154,117,0,.20)}
html[data-theme="light"] .ars-seg-c{background:repeating-linear-gradient(45deg,#cfc9ba 0 5px,#e7e2d6 5px 10px)}
html[data-theme="light"] .ars-st.completed {background:#dff0e0;color:#227a35}
html[data-theme="light"] .ars-st.delivering{background:#f3ecc9;color:#7a5c00}
html[data-theme="light"] .ars-st.announced {background:#dbeaf6;color:#1f6fa8}
html[data-theme="light"] .ars-st.cancelled {background:#f5dede;color:#b23a3a}
html[data-theme="light"] .ars-cat.aircraft   {background:#dbeaf6;color:#1f6fa8}
html[data-theme="light"] .ars-cat.missile    {background:#f5dede;color:#b23a3a}
html[data-theme="light"] .ars-cat.ground     {background:#f3ecc9;color:#8a6a00}
html[data-theme="light"] .ars-cat.naval      {background:#d6efe8;color:#1f8a72}
html[data-theme="light"] .ars-cat.uas        {background:#ece1f7;color:#7a4fb0}
html[data-theme="light"] .ars-cat.c4isr      {background:#d8eef2;color:#1f8496}
html[data-theme="light"] .ars-detail a{border-bottom-color:#d9c98a}
html[data-theme="light"] .ars-point{border-left-color:var(--y)}
html[data-theme="light"] .ars-tl-body a{border-bottom-color:#d9c98a}
html[data-theme="light"] .ars-atag.treaty {background:#dff0e0;color:#227a35}
html[data-theme="light"] .ars-atag.nato   {background:#dbeaf6;color:#1f6fa8}
html[data-theme="light"] .ars-atag.mnna   {background:#ece1f7;color:#7a4fb0}
html[data-theme="light"] .ars-atag.partner{background:#f3ecc9;color:#7a5c00}
html[data-theme="light"] .ars-atag.aid    {background:#f5dede;color:#b23a3a}
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
var xA={grid:{display:false},ticks:{color:__TICK__,font:{size:10},maxRotation:0},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?__ZERO__:'transparent';}},ticks:{color:__TICK__,font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var animDelay=function(c){return c.type==='data'&&c.mode==='default'?c.dataIndex*40+c.datasetIndex*120:0;};
var baseOpts={animation:{delay:animDelay,duration:800,easing:'easeOutQuart'},transitions:{active:{animation:{duration:0}}},responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'line',data:AC,borderColor:__ACLINE__,backgroundColor:gfill(__ACLINE__),fill:true,tension:0.35,borderWidth:2.5,pointRadius:3,pointHoverRadius:5,pointBackgroundColor:ACbg,pointBorderColor:__PTRING__,pointBorderWidth:1.5,order:2},
  {type:'line',data:CR,borderColor:__CRLINE__,borderDash:[5,4],borderWidth:1.5,pointBackgroundColor:__CRLINE__,pointRadius:0,pointHoverRadius:4,tension:0.35,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'line',data:SH,borderColor:__SHLINE__,backgroundColor:gfill(__SHLINE__),fill:true,tension:0.35,borderWidth:2.5,pointRadius:3,pointHoverRadius:5,pointBackgroundColor:SHbg,pointBorderColor:__PTRING__,pointBorderWidth:1.5}
]},options:baseOpts});
})();"""

_CHART_JS_YTD = """\
(function(){
var L=__L__,AC=__AC__,CR=__CR__,SH=__SH__,ACbg=__ACbg__,SHbg=__SHbg__;
var xA={grid:{display:false},ticks:{color:__TICK__,font:{size:10},maxRotation:0,autoSkip:false,callback:function(v,i){return L[i]&&L[i].endsWith('/1')?L[i]:''}},border:{display:false}};
var yA={grid:{color:function(ctx){return ctx.tick.value===0?__ZERO__:'transparent';}},ticks:{color:__TICK__,font:{size:10},maxTicksLimit:4},border:{display:false},beginAtZero:true};
var animDelay=function(c){return c.type==='data'&&c.mode==='default'?c.dataIndex*15+c.datasetIndex*60:0;};
var baseOpts={animation:{delay:animDelay,duration:600,easing:'easeOutExpo'},transitions:{active:{animation:{duration:0}}},responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__-ac'),{data:{labels:L,datasets:[
  {type:'bar',data:AC,backgroundColor:ACbg,borderRadius:2,order:2},
  {type:'line',data:CR,borderColor:__CRLINE__,borderDash:[4,3],pointBackgroundColor:__CRLINE__,pointRadius:2,tension:0,fill:false,order:1}
]},options:baseOpts});
new Chart(document.getElementById('__UID__-sh'),{data:{labels:L,datasets:[
  {type:'bar',data:SH,backgroundColor:SHbg,borderRadius:2}
]},options:baseOpts});
})();"""

# 軍購年度金額直條（單系列＝站內黃）；tooltip 附該年最大三案名稱。
_CHART_JS_ARSENAL = """\
(function(){
var Y=__YEARS__,V=__VALS__,TOP=__TOPS__;
var xA={grid:{display:false},ticks:{color:__TICK__,font:{size:11},maxRotation:0},border:{display:false}};
var yA={grid:{color:function(c){return c.tick.value===0?__ZERO__:'transparent';}},ticks:{color:__TICK__,font:{size:10},maxTicksLimit:5,callback:function(v){return v;}},border:{display:false},beginAtZero:true};
var opts={animation:{duration:700,easing:'easeOutQuart'},responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{callbacks:{
    label:function(c){return __CURLABEL__+c.parsed.y.toFixed(1)+__UNIT__;},
    afterBody:function(items){var i=items[0].dataIndex;return TOP[i]||[];}
  }}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__'),{type:'bar',data:{labels:Y,datasets:[
  {data:V,backgroundColor:__BAR__,hoverBackgroundColor:__BARH__,borderRadius:3,maxBarThickness:54}
]},options:opts});
})();"""

# 國際買家排名（橫條，同色相強調）：台灣＝accent、美援＝虛線框、其他＝暗階。
# 直接標籤：y 軸 tick＝國名＋同盟標籤；bar 端＝數量（自訂 plugin 繪製，右緣自動內縮）。
# tooltip＝訂購年＋來源網域。國家數×34px 高度由 wrap 內嵌 style 控制。
_CHART_JS_RANK = """\
(function(){
var C=__COUNTRIES__,V=__VALS__,COL=__COLORS__,INFO=__INFO__,TW=__TWIDX__,AID=__AIDIDX__;
var lbl={id:'arslbl',afterDatasetsDraw:function(ch){
  var ctx=ch.ctx,a=ch.chartArea,m=ch.getDatasetMeta(0);
  ctx.save();ctx.font='700 11px "Noto Sans TC",sans-serif';ctx.textBaseline='middle';
  m.data.forEach(function(b,i){
    var t=V[i].toLocaleString(),x=b.x+6;ctx.textAlign='left';
    if(x+ctx.measureText(t).width>a.right){x=b.x-6;ctx.textAlign='right';}
    ctx.fillStyle=__LBLCOL__;ctx.fillText(t,x,b.y);
  });
  if(AID>=0){var bar=m.data[AID],h=bar.height,x0=Math.min(bar.base,bar.x),w=Math.abs(bar.x-bar.base);
    ctx.strokeStyle=__AIDCOL__;ctx.lineWidth=1.5;ctx.setLineDash([4,3]);
    ctx.strokeRect(x0+0.75,bar.y-h/2+0.75,Math.max(w-1.5,1),h-1.5);}
  ctx.restore();
}};
var xA={grid:{color:function(c){return c.tick.value===0?__ZERO__:'transparent';}},ticks:{color:__TICK__,font:{size:10},maxTicksLimit:5},border:{display:false},beginAtZero:true,grace:'12%'};
var yA={grid:{display:false},ticks:{color:function(c){return c.index===TW?__ACCENT__:__TICK__;},font:{size:11},autoSkip:false,crossAlign:'far'},border:{display:false}};
var opts={indexAxis:'y',animation:{duration:700,easing:'easeOutQuart'},responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{callbacks:{
    title:function(it){return C[it[0].dataIndex];},
    label:function(c){return __QLABEL__+c.parsed.x.toLocaleString();},
    afterBody:function(it){return INFO[it[0].dataIndex]||[];}
  }}},scales:{x:xA,y:yA}};
new Chart(document.getElementById('__UID__'),{type:'bar',data:{labels:C,datasets:[
  {data:V,backgroundColor:COL,borderRadius:3,maxBarThickness:30}
]},options:opts,plugins:[lbl]});
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

    tc = _CHART_COLORS[THEME]
    ac_bg = [tc['ac_today'] if i == today_idx else tc['ac_other'] for i in range(n)]
    sh_bg = [tc['sh_today'] if i == today_idx else tc['sh_other'] for i in range(n)]

    js = (template
          .replace('__L__',      json.dumps(labels))
          .replace('__AC__',     json.dumps(aircraft))
          .replace('__CR__',     json.dumps(crosses))
          .replace('__SH__',     json.dumps(ships))
          .replace('__ACbg__',   json.dumps(ac_bg))
          .replace('__SHbg__',   json.dumps(sh_bg))
          .replace('__TICK__',   json.dumps(tc['tick']))
          .replace('__ZERO__',   json.dumps(tc['zero']))
          .replace('__ACLINE__', json.dumps(tc['ac_line']))
          .replace('__SHLINE__', json.dumps(tc['sh_line']))
          .replace('__CRLINE__', json.dumps(tc['cr_line']))
          .replace('__PTRING__', json.dumps(tc['pt_ring']))
          .replace('__UID__',    uid))

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
    # 地圖主題色注入（裸 hex→裸 hex，保留各自既有引號情境；tiles 換底圖）
    m = _MAP_COLORS[THEME]
    js = (_MAP_JS
          .replace('dark_all',    m['tiles'])
          .replace('#e05555',     m['ml_hi'])
          .replace('#3a6070',     m['ml_lo'])
          .replace('#f5c842',     m['zone'])
          .replace('#4dba6a',     m['nm'])
          .replace('0 1px 4px #000,0 0 8px #000', m['zlbl_sh'])
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


def make_head(lang, page_name, s, head_extra='', page_path=None, abs_assets=False):
    """Build complete <head> block for the given lang and page.

    head_extra: optional raw HTML (e.g. JSON-LD) injected just before </head>.
    page_path:  override URL path (e.g. '/arsenal/' for nested pages); default
                '/{page_name}.html'.
    abs_assets: force absolute asset paths (needed for nested zh pages whose
                relative refs would otherwise resolve into the subdirectory).
    """
    title    = s['page_titles'][page_name]
    html_lng = s['html_lang']
    desc     = s['meta_descs'][page_name]

    # Absolute URLs for canonical / hreflang / OG (full domain, per SEO best practice)
    path     = page_path if page_path else f'/{page_name}.html'
    canon_zh = f'{BASE_URL}{path}'
    canon_en = f'{BASE_URL}/en{path}'
    canonical = canon_en if lang == 'en' else canon_zh

    # Asset paths: en/ pages (and nested zh pages) use absolute paths to avoid
    # subdirectory issues.
    if lang == 'en' or abs_assets:
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

    # /arsenal/ 全系列頁（index＋3 內頁，中英）用專屬 OG 圖，尺寸同為 1200×630，
    # 沿用上面已固定的 og:image:width/height，不需另外改。
    if page_name in ARSENAL_OG_PAGES:
        og_image = f'{BASE_URL}/{ARSENAL_OG_IMG}'
    og_alt = title if page_name in ARSENAL_OG_PAGES else s['site_title']

    return f"""\
<!DOCTYPE html>
<html lang="{html_lng}" data-theme="{THEME}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="alternate" hreflang="zh-Hant" href="{canon_zh}">
<link rel="alternate" hreflang="en" href="{canon_en}">
<link rel="alternate" hreflang="x-default" href="{canon_zh}">
<meta name="theme-color" content="{THEME_COLOR[THEME]}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{s['site_title']}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{og_alt}">
<meta property="og:locale" content="{og_locale}">
<meta property="og:locale:alternate" content="{og_locale_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{og_image}">
<meta name="twitter:image:alt" content="{og_alt}">
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


# ── /arsenal/ 結構化資料（BreadcrumbList；目錄頁另加 ItemList、內頁加 TechArticle）──

ARS_PUBLISHED = '2026-07-23'   # /arsenal/ 內容區上線日（TechArticle datePublished）


def arsenal_jsonld(lang, s, df_ars, weapon_key=None):
    """arsenal 系列頁的 JSON-LD head_extra。"""
    pfx  = '/en' if lang == 'en' else ''
    home = f'{BASE_URL}{pfx}/index.html'
    ars  = f'{BASE_URL}{pfx}/arsenal/'
    ars_label = 'US Arms Deliveries to Taiwan' if lang == 'en' else '對美軍購交付追蹤'
    crumbs = [
        {"@type": "ListItem", "position": 1,
         "name": 'Home' if lang == 'en' else '首頁', "item": home},
        {"@type": "ListItem", "position": 2, "name": ars_label, "item": ars},
    ]
    # 內容更新日：與 /arsenal/ KPI 同源（arsenal_updated.txt，缺檔退回最新公告日）
    upd_file = DATA_FILE.parent / 'arsenal_updated.txt'
    upd = (upd_file.read_text(encoding='utf-8').strip() if upd_file.exists()
           else str(df_ars['announce_date'].max()))

    blocks = []
    if weapon_key:
        w    = ARSENAL_DETAIL[weapon_key]
        name = w['name_en'] if lang == 'en' else w['name_zh']
        url  = f'{BASE_URL}{pfx}/arsenal/{weapon_key}.html'
        crumbs.append({"@type": "ListItem", "position": 3, "name": name, "item": url})
        blocks.append({
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": name,
            "description": s['meta_descs'][f'ars_{weapon_key}'],
            "mainEntityOfPage": url,
            "image": f'{BASE_URL}/{ARSENAL_OG_IMG}',
            "inLanguage": 'en' if lang == 'en' else 'zh-Hant',
            "datePublished": ARS_PUBLISHED,
            "dateModified": upd,
            "author": {"@type": "Person", "name": "Adam Pan"},
        })
    else:
        blocks.append({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": ars_label,
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "name": (d['name_en'] if lang == 'en' else d['name_zh']),
                 "url": f'{BASE_URL}{pfx}/arsenal/{k}.html'}
                for i, (k, d) in enumerate(ARSENAL_DETAIL.items())
            ],
        })
    blocks.append({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "itemListElement": crumbs})
    return ''.join('\n<script type="application/ld+json">'
                   + json.dumps(b, ensure_ascii=False) + '</script>' for b in blocks)


def nav_html(active, lang, page_name, s):
    """Navigation bar with language toggle. 'arsenal' is a nested page (/arsenal/)."""
    base = '/en' if lang == 'en' else ''

    # 語言切換連結：arsenal 為 /arsenal/ 目錄式路徑；武器內頁為 /arsenal/{w}.html；
    # 其餘為 /{page}.html。
    if page_name == 'arsenal':
        toggle = '/arsenal/' if lang == 'en' else '/en/arsenal/'
    elif page_name.startswith('ars_'):
        w = page_name[4:]
        toggle = f'/arsenal/{w}.html' if lang == 'en' else f'/en/arsenal/{w}.html'
    else:
        toggle = f'/{page_name}.html' if lang == 'en' else f'/en/{page_name}.html'

    pages = [
        ('index',   f'{base}/index.html',   s['nav_index']),
        ('records', f'{base}/records.html', s['nav_records']),
        ('monthly', f'{base}/monthly.html', s['nav_monthly']),
        ('arsenal', f'{base}/arsenal/',     s['nav_arsenal']),
        ('about',   f'{base}/about.html',   s['nav_about']),
    ]
    items = ''.join(
        f'<a href="{href}"{"" if active != p else " class=active"}>{label}</a>'
        for p, href, label in pages
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
        f'<div class="sitrep anim-ready">'
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
setTimeout(function(){animCount(s,t,900);},i*100);});});},{threshold:0});
// threshold 0：任何一像素進入視野即觸發。0.15 會讓「高度超過視窗 6.7 倍」的長區塊
// （如 21 張卡的卡片牆在手機上）永遠達不到門檻而永久隱形——2026-07-24 實際踩過。
document.querySelectorAll('.anim-ready').forEach(function(el){io.observe(el);});
// 保險絲：無論 IntersectionObserver 是否正常（舊瀏覽器/省流模式/任何異常），
// 2.5 秒後強制顯示所有尚未觸發的區塊。動畫是加分項，內容可見是底線。
// 數字也要補：第 1 行已把 [data-count] 清成 '0'，若 IO 從未觸發，區塊會「顯示但數字全是 0」
// ——比隱形更糟（讀者會以為當日零架次）。所以保險絲一併把未跑動畫的數字直接寫回真值。
setTimeout(function(){
document.querySelectorAll('.anim-ready:not(.visible)').forEach(function(el){el.classList.add('visible');});
document.querySelectorAll('[data-count]').forEach(function(el){
if(el.textContent==='0'&&el.dataset.count!=='0')el.textContent=el.dataset.count;});
},2500);
})();</script>"""


def build_index(df, lang, out_dir, s, df_ars=None):
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

  {chart_section_html(s['chart_recent'], recent_html, split_ac, split_sh)}
  {chart_section_html(s['chart_ytd'], ytd_html, streak_ac, streak_sh)}

  {arsenal_divert_html(df_ars, lang, s) if df_ars is not None else ''}

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
    <p class="lead">This site tracks daily PLA military activity around Taiwan. Every figure is
      transcribed verbatim from the daily public releases of the Republic of China (Taiwan)
      Ministry of National Defense (MND) — nothing is estimated or inferred.</p>
    <div class="about-meta">
      <span>Coverage: {start} – {end}</span>
      <span>{n} daily records</span>
      <span>License: CC BY 4.0</span>
    </div>

    <h2>Source &amp; updates</h2>
    <ul>
      <li>Single source: the <a href="{MND}" target="_blank" rel="noopener">ROC MND "Real-time
        Military Activity" bulletins</a> and their flight-path graphics. This site only
        transcribes, structures and visualizes that data; nothing unconfirmed by the MND is added.</li>
      <li>Fetched automatically once a day after the MND publishes around midday Taiwan time
        (≈ 12:00–14:00), with backup retry runs.</li>
      <li>If the MND does not publish on a given day, that day stays blank — never filled with an
        estimate. Records are append-only and never rewritten, so cited figures stay stable.</li>
      <li>Checked before writing: median-line crossings may not exceed total sorties; the crossing
        rate must match the computed value (±1%); no duplicate dates; aircraft-type values must be
        valid. Pages are not regenerated unless the checks pass.</li>
    </ul>

    <h2>Lines &amp; terms</h2>
    <div class="def-card">
      <div class="term">Taiwan Strait median line <span class="en">/ Davis Line</span></div>
      <p>An informal line down the centre of the strait, never recognized by any treaty between
        the two sides. For decades aircraft and vessels largely refrained from crossing it, so a
        crossing is a strong political and military signal — but crossing it <strong>does not
        constitute a violation of territory or sovereign airspace under international law</strong>
        and does not trigger the right of self-defense. "Median-line crossings" here means the PLA
        sorties that crossed this line that day.</p>
    </div>
    <div class="def-card">
      <div class="term">12 NM territorial sea</div>
      <p>Under UNCLOS, the 12 nautical miles from the baseline are a state's territorial sea and
        the airspace above it is sovereign airspace — the boundary that actually carries legal
        weight. Once PLA aircraft or vessels come inside this line, Taiwan may take defensive
        action under international law and its Defense Act. A different order of event from a
        median-line crossing.</p>
    </div>
    <div class="def-card">
      <div class="term">ADIZ <span class="en">Air Defense Identification Zone</span></div>
      <p>Declared for the early identification of airborne objects, and far larger than sovereign
        airspace. Entering an ADIZ is not a violation of sovereignty; it is used to gauge intensity.</p>
    </div>
    <div class="def-card">
      <div class="term">Sorties &amp; vessels</div>
      <p>"Sorties" is the number of PLA aircraft missions detected that day, per the MND's own
        count; "vessels" is the number of PLA Navy ships detected that day. Other activity such as
        surveillance balloons is noted in the notes column of the daily records.</p>
    </div>

    <h2>The arms dataset</h2>
    <p>The <a href="/en/arsenal/">Arms Delivery Tracker</a> is a separate dataset covering US
      Foreign Military Sales to Taiwan notified to Congress by the Defense Security Cooperation
      Agency (DSCA) since 2019. A DSCA notification is the congressional-notification stage only:
      it is <strong>not</strong> a signed contract and not a delivery, and notified values are
      ceilings that signed amounts often fall below. Direct commercial sales and US-forces
      transfers are excluded; every case is compiled by hand and carries its own source link.</p>

    <h2>Citation &amp; license</h2>
    <p>The underlying figures are public information from the MND. This site's compilation, field
      structure and charts are released under <a href="{CC}" target="_blank" rel="noopener">CC
      BY 4.0</a>. Please credit:</p>
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
    <p class="lead">本站每日追蹤解放軍在台灣周邊的軍事活動。數字全部逐字取自中華民國國防部
      每日公告，不推估、不加工。</p>
    <div class="about-meta">
      <span>資料區間：{start} ～ {end}</span>
      <span>{n} 筆每日紀錄</span>
      <span>授權：CC BY 4.0</span>
    </div>

    <h2>資料來源與更新</h2>
    <ul>
      <li>唯一來源：<a href="{MND}" target="_blank" rel="noopener">國防部「即時軍事動態」</a>
        的每日公告與航跡圖。本站只做轉錄、結構化與視覺化，不引用未經國防部證實的訊息。</li>
      <li>每天國防部中午公布後自動擷取一次（台灣時間約 12:00–14:00），另有備援班次重試。</li>
      <li>國防部當日沒發布就留空，不用估計值補；歷史資料只新增、不改寫，所以引用過的數字不會變。</li>
      <li>寫入前自動檢查：逾越中線數不得大於總架次、越線率與計算值相符（±1%）、日期不重複、
        機型值合法。檢查沒過就不會產生新頁面。</li>
    </ul>

    <h2>界線與名詞</h2>
    <div class="def-card">
      <div class="term">海峽中線 <span class="en">Taiwan Strait median line / Davis Line</span></div>
      <p>海峽中央一條沒有任何條約承認的默契界線。長年雙方軍機艦多半不越線，所以越線是強烈的
        政治與軍事訊號；但越線<strong>不構成國際法上的領土或領空侵犯</strong>，也不會觸發自衛權。
        本站「逾越中線」＝當日越過此線的共機架次。</p>
    </div>
    <div class="def-card">
      <div class="term">12 浬領海線 <span class="en">12 NM territorial sea</span></div>
      <p>依《聯合國海洋法公約》，自基線起算 12 浬為領海、其上空為領空，這才是有法律效力的邊界。
        共機艦進到這條線以內，台灣依國際法與《國防法》可採取防衛行動——與越中線是兩個不同
        層級的事件。</p>
    </div>
    <div class="def-card">
      <div class="term">防空識別區 <span class="en">ADIZ</span></div>
      <p>為早期識別空中目標而劃設，範圍遠大於領空。進入 ADIZ 不等於侵犯主權，只用來看活動強度。</p>
    </div>
    <div class="def-card">
      <div class="term">架次與共艦 <span class="en">sorties &amp; vessels</span></div>
      <p>「架次」＝當日偵獲的共機出動次數（以國防部計數為準）；「共艦」＝當日偵獲的解放軍艦艇
        艘數。空飄氣球等其他活動另記在每日紀錄的備註欄。</p>
    </div>

    <h2>軍購資料</h2>
    <p><a href="/arsenal/">軍購交付追蹤</a>是另一組獨立資料，收 2019 年起由美國國防安全合作署
      （DSCA）通知美國國會的對台軍售案。DSCA 公告只是「通知國會」，<strong>不等於簽約、
      也不等於交付</strong>，公告金額是上限、實際簽約常較低。不含商售案與美軍自用移撥；
      每案人工整理、逐案附來源。</p>

    <h2>引用與授權</h2>
    <p>底層數字屬國防部公開資訊。本站的整理、欄位結構與圖表以
      <a href="{CC}" target="_blank" rel="noopener">CC BY 4.0</a> 釋出，歡迎引用，請註明：</p>
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


# ── /arsenal/ 軍購交付追蹤儀表板 ──────────────────────────────────────────────

# 國別中→英（質性判讀區與對比引用；未列者維持原字，validate 會抓 en 頁殘留中文）
COUNTRY_EN = {
    '台灣': 'Taiwan', '土耳其': 'Turkey', '摩洛哥': 'Morocco', '保加利亞': 'Bulgaria',
    '巴林': 'Bahrain', '斯洛伐克': 'Slovakia', '約旦': 'Jordan', '印度': 'India',
    '埃及': 'Egypt', '南韓': 'South Korea', '菲律賓': 'Philippines', '波蘭': 'Poland',
    '澳洲': 'Australia', '羅馬尼亞': 'Romania', '阿聯': 'UAE', '烏克蘭': 'Ukraine',
    '愛沙尼亞': 'Estonia', '拉脫維亞': 'Latvia', '立陶宛': 'Lithuania', '新加坡': 'Singapore',
    '克羅埃西亞': 'Croatia', '德國': 'Germany', '沙烏地阿拉伯': 'Saudi Arabia', '英國': 'UK',
    '突尼西亞': 'Tunisia', '加拿大': 'Canada', '日本': 'Japan', '比利時': 'Belgium',
    '伊拉克': 'Iraq', '科威特': 'Kuwait',
}
UNIT_EN = {'架': 'aircraft', '枚': 'units', '套': 'systems', '輛': 'vehicles', '座': 'mounts'}
_CJK = re.compile(r'[一-鿿]')


def _ars_clean_en(v):
    """把日期/期程欄的少量中文字（後/年/起）轉成 ASCII，殘留 CJK 則回空字串。"""
    v = v.replace('後', '+').replace('年', '').replace('起', '+')
    return '' if _CJK.search(v) else v


# ── 武器影像資產（assets/arsenal/，DVIDS 公有領域照片；圖片本身 untracked 但
#    build 邏輯必須固定寫在此處，禁止手改產出 HTML）───────────────────────────
ARSENAL_ASSET_DIR = ROOT / 'assets' / 'arsenal'
ARSENAL_OG_IMG     = 'assets/arsenal/og-arsenal.jpg'   # 相對路徑；make_head 另補 BASE_URL
# /arsenal/ 系列頁（index＋3 內頁）共用專屬 og:image；page_name 需與 make_head()
# 呼叫時傳入的值一致（build_arsenal 用 'arsenal'，build_arsenal_detail 用 'ars_{key}'）
ARSENAL_OG_PAGES = {'arsenal', 'ars_harpoon', 'ars_patriot', 'ars_himars'}

# 系統卡片牆：主要裝備矩陣（category≠sustainment 且 qty 非空，共 23 案）歸併為
# 「武器系統」卡。case_id → system_card_key；同一系統多案共用一張卡，卡圖為
# assets/arsenal/card-{key}.jpg（條件式渲染：檔案存在才掛圖，否則退無圖版）。
# 目前定義的合併：HIMARS（20-77 已交付＋26-01 已公告）、魚叉（20-68 岸置＋22-45
# 空射）；其餘一案一卡。約 21 張卡。
ARSENAL_SYSCARD = {
    '19-21': 'stinger',   '19-22': 'm1a2',     '19-50': 'f16v',
    '20-07': 'mk48',      '20-69': 'slamer',   '20-75': 'ms110',
    '20-77': 'himars',    '26-01': 'himars',
    '20-68': 'harpoon',   '22-45': 'harpoon',
    '20-74': 'mq9b',      '21-44': 'm109a6',   '22-46': 'aim9x',
    '22-70': 'volcano',   '24-47': 'switchblade', '24-56': 'altius600',
    '24-48': 'nasams',    '25-01': 'mk75',     '25-04': 'c4mod',
    '25-108': 'm109a7',   '26-02': 'tow',      '26-06': 'javelin',
    '26-09': 'altius700',
}
# 合併卡的顯示名稱（key → (zh, en)）；未列出的單案卡沿用該案 system_zh/system_en。
ARSENAL_SYSCARD_NAME = {
    'himars':  ('海馬斯多管火箭系統', 'M142 HIMARS Rocket System'),
    'harpoon': ('魚叉飛彈（岸置＋空射）', 'Harpoon Missiles (Coastal + Air-launched)'),
}
# 無圖案的類別占位單字。zh 頁用單字，en 頁需避免殘留中文（validate.py 的 en 頁
# 中文檢查會攔到），改用對應類別代碼。
ARSENAL_CAT_GLYPH = {
    'aircraft': '機', 'missile': '彈', 'ground': '陸',
    'naval': '艦', 'uas': '無', 'c4isr': '訊', 'sustainment': '',
}
# 無圖卡的「設計化占位帶」用詞（與圖帶同高，類別大字＋斜紋底，取代單獨空白）。
ARSENAL_CAT_WORD = {
    'aircraft': '航空系統', 'missile': '飛彈系統', 'ground': '地面系統',
    'naval': '艦載系統', 'uas': '無人系統', 'c4isr': '通訊指管',
}
ARSENAL_CAT_WORD_EN = {
    'aircraft': 'AIRCRAFT', 'missile': 'MISSILE', 'ground': 'GROUND',
    'naval': 'NAVAL', 'uas': 'UNMANNED', 'c4isr': 'C4ISR',
}
ARSENAL_CAT_GLYPH_EN = {
    'aircraft': 'AC', 'missile': 'MSL', 'ground': 'GRD',
    'naval': 'NAV', 'uas': 'UAS', 'c4isr': 'C4I', 'sustainment': '',
}
# 武器內頁代表影像（三頁固定對應；hero-{key}.jpg 若存在則優先於此表，見
# _ars_detail_hero_html）。卡片圖帶與頁尾 credit 皆由此表決定。
ARSENAL_WEAPON_IMAGE = {
    'himars': 'hero-himars.jpg',
    'harpoon': 'hero-harpoon.jpg',
    'patriot': 'hero-patriot.jpg',
}

_ars_credits_cache = None


def _ars_credits():
    """讀 assets/arsenal/credits.json（每檔攝影者/單位/來源頁），快取一次。
    檔案不存在時回空 dict（不擋 build，圖片與 credits 是選配資產）。"""
    global _ars_credits_cache
    if _ars_credits_cache is None:
        p = ARSENAL_ASSET_DIR / 'credits.json'
        _ars_credits_cache = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    return _ars_credits_cache


def _ars_credit_line(filename, lang):
    """回傳「影像：{photographer}, {unit}（DVIDS）」一行；查無 credits 則回空字串。
    unit 欄位少數含中文附注（例：「支援 African Lion 24」），en 頁需轉英文避免
    殘留 CJK（validate.py 的 en 頁中文檢查會攔到）。"""
    if not filename:
        return ''
    c = _ars_credits().get(filename)
    if not c:
        return ''
    photographer = c.get('photographer', '')
    unit = c.get('unit', '')
    if lang == 'en':
        unit = unit.replace('支援 ', 'in support of ').replace('支援', 'in support of ')
    who = ', '.join(x for x in (photographer, unit) if x)
    if not who:
        return ''
    return (f'Image: {who} (DVIDS)' if lang == 'en' else f'影像：{who}（DVIDS）')


def _ars_qty_label(qty, unit, lang):
    if not qty:
        return ''
    try:
        n = f'{int(float(qty)):,}'
    except ValueError:
        n = qty
    if lang == 'en':
        u = UNIT_EN.get(unit, '')
        return f'{n} {u}'.strip()
    return f'{n} {unit}'.strip()


def _ars_status_badge(status, s):
    zh, en, cls = ARSENAL_STATUS[status]
    return f'<span class="ars-st {cls}">{en if s["html_lang"] == "en" else zh}</span>'


def _ars_cat_badge(cat, s):
    zh, en = ARSENAL_CATEGORIES[cat]
    return f'<span class="ars-cat {cat}">{en if s["html_lang"] == "en" else zh}</span>'


def _ars_bar(status):
    if status == 'cancelled':
        segs = '<span class="ars-seg ars-seg-c"></span>'
    elif status == 'completed':
        segs = '<span class="ars-seg ars-seg-d" style="flex:1"></span>'
    elif status == 'delivering':
        d = int(round(ARSENAL_FILL['delivering'] * 100))
        segs = (f'<span class="ars-seg ars-seg-d" style="flex:{d}"></span>'
                f'<span class="ars-seg ars-seg-p" style="flex:{100 - d}"></span>')
    else:  # announced / unknown
        segs = '<span class="ars-seg ars-seg-p" style="flex:1"></span>'
    return f'<div class="ars-bar">{segs}</div>'


def _ars_srcs(row, s):
    lang = 'en' if s['html_lang'] == 'en' else 'zh'
    out = []
    if row['source_announce']:
        out.append(_src_chip(row['source_announce'], lang))
    if row['source_delivery']:
        out.append(_src_chip(row['source_delivery'], lang))
    return ' '.join(out)


_DELAY_TAG = {
    'official': ('官方說明', 'Official'),
    'semi':     ('半官方／媒體', 'Semi-official'),
    'none':     ('未見官方說明', 'No official statement'),
}


def _ars_delay_html(cid, lang):
    """回傳某案的延宕理由 HTML（含 tag 與來源）；無登錄則回空字串。"""
    if cid not in ARSENAL_DELAYS:
        return ''
    zh, en, src, tag = ARSENAL_DELAYS[cid]
    txt = en if lang == 'en' else zh
    tl = _DELAY_TAG[tag][1] if lang == 'en' else _DELAY_TAG[tag][0]
    brk = f'[{tl}] ' if lang == 'en' else f'〔{tl}〕'
    out = brk + html.escape(txt)
    if src:
        out += ' ' + _src_chip(src, lang)
    return out


def _ars_matrix_detail(row, s, lang):
    a = s['ars']
    parts = []
    if lang == 'en':
        prog = []
        fd = _ars_clean_en(row['first_delivery'])
        ec = _ars_clean_en(row['expected_complete'])
        if fd:
            prog.append(f'first delivery {fd}')
        if ec:
            prog.append(f'expected complete {ec}')
        if prog:
            parts.append(f'<span class="lbl">{a["matrix_delay"]}</span>' + ', '.join(prog) + '.')
    else:
        if row['delivered_note']:
            parts.append(f'<span class="lbl">{a["matrix_delay"]}</span>'
                         + html.escape(row['delivered_note']))
    delay = _ars_delay_html(row['case_id'], lang)
    if delay:
        parts.append(delay)
    srcs = _ars_srcs(row, s)
    if srcs:
        parts.append(srcs)
    return '<div class="ars-detail">' + '<br>'.join(parts) + '</div>'


def _ars_key_ranking(df_peers, key):
    """回傳 (台灣總量, 全部排名, FMS付費排名)；美援（notes 含『美援』）另計。"""
    sub = df_peers[df_peers['system_key'] == key]
    agg, aid = {}, set()
    for _, r in sub.iterrows():
        c = r['buyer_country']
        agg[c] = agg.get(c, 0) + int(r['qty'])
        # 美援標記＝「美援（」或「美援(」開頭句；避免誤中台灣列的「非美援」子字串
        if '美援（' in r['notes'] or '美援(' in r['notes']:
            aid.add(c)
    tw = agg.get('台灣', 0)
    all_sorted = sorted(agg.items(), key=lambda x: -x[1])
    rank_all = [c for c, _ in all_sorted].index('台灣') + 1
    fms_sorted = sorted([(c, q) for c, q in agg.items() if c not in aid], key=lambda x: -x[1])
    rank_fms = [c for c, _ in fms_sorted].index('台灣') + 1
    return tw, rank_all, rank_fms


def _ars_peer_src(df_peers, key):
    m = df_peers[(df_peers['system_key'] == key) & (df_peers['buyer_country'] == '台灣')]
    return m.iloc[0]['source'] if len(m) else ''


def arsenal_divert_html(df_ars, lang, s):
    """首頁導流卡：待交付金額＋當期亮點，整卡連向 /arsenal/。數字全由 CSV 計算。"""
    a = s['ars']
    pend_m = df_ars[df_ars['delivery_status'].isin(['delivering', 'announced'])]['value_usd_m'].sum()
    amt = fmt_money(pend_m, lang)
    deliv = df_ars[(df_ars['delivery_status'] == 'delivering') & (df_ars['first_delivery'] != '')]
    if len(deliv):
        r = deliv.sort_values('first_delivery').iloc[-1]
        name = r['system_en'] if lang == 'en' else r['system_zh']
        fd = r['first_delivery']
        hi = (f'{html.escape(name)} — first units delivered {html.escape(fd)}'
              if lang == 'en' else f'{html.escape(name)}首批已於 {html.escape(fd)} 交付')
    else:
        r = df_ars.sort_values('announce_date').iloc[-1]
        name = r['system_en'] if lang == 'en' else r['system_zh']
        hi = (f'latest notice: {html.escape(name)}'
              if lang == 'en' else f'最近公告：{html.escape(name)}')
    if lang == 'en':
        txt = f'{a["divert_pending"]} {amt} | {hi}'
    else:
        txt = f'{a["divert_pending"]} {amt}美元 ｜ {hi}'
    href = '/en/arsenal/' if lang == 'en' else '/arsenal/'
    return (f'<a class="ars-divert" href="{href}">'
            f'<span class="row"><span class="lab">{a["divert_label"]}</span>'
            f'<span class="arr">→</span><span class="txt">{txt}</span></span></a>')


def _ars_reads_html(df_ars, df_peers, lang, s):
    """質性判讀區塊（5 個論點，每個附來源）。數字取自 peers，敘事為策展文字。"""
    f16_tw, f16_r, _ = _ars_key_ranking(df_peers, 'f16v')
    hp_tw, hp_r, _   = _ars_key_ranking(df_peers, 'harpoon')
    hm_tw, hm_r, _   = _ars_key_ranking(df_peers, 'himars')
    jv_tw, _, jv_rf  = _ars_key_ranking(df_peers, 'javelin')
    src_f16 = _ars_peer_src(df_peers, 'f16v')
    src_hp  = _ars_peer_src(df_peers, 'harpoon')
    src_hm  = _ars_peer_src(df_peers, 'himars')
    src_jv  = _ars_peer_src(df_peers, 'javelin')
    m26 = df_ars[df_ars['case_id'] == '26-01']
    src_at = m26.iloc[0]['source_announce'] if len(m26) else src_hm

    if lang == 'en':
        pts = [
            ('F-16V — the world’s largest single buyer',
             f'Taiwan is buying {f16_tw} newly built F-16 Block 70/72 jets — the largest single buyer '
             f'worldwide, ahead of Turkey (40), Morocco (25), Bulgaria and Bahrain (16 each). Selling the '
             f'latest F-16 and letting Taiwan be the top buyer is itself a marker of capability and trust.',
             '', src_f16),
            ('Harpoon — an order no one else matches',
             f'Taiwan’s {hp_tw} Harpoon missiles (400 coastal-defense in 100 launcher sets, plus 60 '
             f'air-launched) dwarf every other buyer (India 43, Egypt 20, South Korea 19, Philippines 12) — '
             f'the largest single Harpoon order in years, and the core weapon for anti-invasion defense.',
             '', src_hp),
            ('HIMARS — the world’s second-largest buyer',
             f'Taiwan’s {hm_tw} HIMARS launchers rank second worldwide, behind only Poland (506) and ahead '
             f'of Australia (90) and Romania (54). HIMARS proved the value of mobile precision fires in Ukraine.',
             '', src_hm),
            ('Javelin — second only to Poland among paying buyers',
             f'Taiwan’s ~{jv_tw:,} Javelin missiles rank second among Foreign Military Sales buyers, behind '
             f'Poland (2,506) and ahead of Australia (1,308); Ukraine’s 10,000+ are US military aid and counted separately.',
             '', src_jv),
            ('ATACMS — a marker of the trust tier',
             'The December 2025 HIMARS package (case 26-01) includes 420 M57 ATACMS — deep-strike missiles with '
             'roughly 300 km range. Willingness to sell a weapon that can strike deep across the strait signals a '
             'higher tier of trust in Taiwan.',
             'This is our own contextual reading, not an official position: the only citable document is the '
             'DSCA notice itself, and Washington has made no corresponding statement about a "trust tier".',
             src_at),
        ]
    else:
        pts = [
            ('F-16V：全球最大單一買家',
             f'台灣採購 {f16_tw} 架 F-16 Block 70/72 新造機，是全球最大的單一買家——超過土耳其（40）、'
             f'摩洛哥（25）、保加利亞與巴林（各 16）。願意出售最新型 F-16 並讓台灣成為最大買家，'
             f'本身即是能力與信任的指標。',
             '', src_f16),
            ('魚叉反艦飛彈：無人能及的訂單規模',
             f'台灣岸置型 400 枚（100 套發射系統）加空射型 60 枚，合計 {hp_tw} 枚，遠超其他所有國際買家'
             f'（印度 43、埃及 20、南韓 19、菲律賓 12），是近年最大的單一魚叉訂單，也是反登陸作戰的核心武器。',
             '', src_hp),
            ('HIMARS 多管火箭：全球第二大買家',
             f'台灣累計 {hm_tw} 套 HIMARS，規模僅次於波蘭（506），高於澳洲（90）、羅馬尼亞（54）等'
             f'北約與盟邦，位居全球第二。HIMARS 已在烏克蘭戰場證明機動精準火力的價值。',
             '', src_hm),
            ('標槍反裝甲飛彈：付費買家中僅次波蘭',
             f'台灣累計約 {jv_tw:,} 枚標槍，在付費採購（FMS）買家中僅次於波蘭（2,506）、高於澳洲（1,308）；'
             f'烏克蘭逾 10,000 枚屬美國軍援、另計。',
             '', src_jv),
            ('ATACMS 陸軍戰術飛彈：信任層級的指標',
             '2025 年 12 月的 HIMARS 大案（案號 26-01）包含 420 枚 M57 ATACMS——射程約 300 公里的縱深'
             '打擊武器。美國願意出售此級可打擊對岸縱深的武器，象徵對台信任層級的提升。',
             '這一段是本站的脈絡判讀，不是官方說法：目前可引的只有 DSCA 公告本身，'
             '美方並未就「信任層級」做過對應表述。',
             src_at),
        ]

    blocks = []
    for title, body, caveat, src in pts:
        cav = f' <span class="caveat">{html.escape(caveat)}</span>' if caveat else ''
        srch = f'<div class="ars-src">{_src_chip(src, lang)}</div>' if src else ''
        blocks.append(f'<div class="ars-point"><h3>{title}</h3><p>{body}{cav}</p>{srch}</div>')
    return '<div class="ars-reads">' + ''.join(blocks) + '</div>'


def _ars_chart_html(df_ars, lang, s):
    a = s['ars']
    df = df_ars.copy()
    df['year'] = df['announce_date'].str[:4]
    years = sorted(df['year'].unique())
    divisor = 1000.0 if lang == 'en' else 100.0
    vals, tops = [], []
    for y in years:
        yr = df[df['year'] == y]
        vals.append(round(yr['value_usd_m'].sum() / divisor, 2))
        top3 = yr.sort_values('value_usd_m', ascending=False).head(3)
        labels = []
        for _, r in top3.iterrows():
            nm = r['system_en'] if lang == 'en' else r['system_zh']
            labels.append(f'{nm} {fmt_money(r["value_usd_m"], lang)}')
        tops.append(labels)
    tc = _CHART_COLORS[THEME]
    js = (_CHART_JS_ARSENAL
          .replace('__YEARS__', json.dumps(years))
          .replace('__VALS__',  json.dumps(vals))
          .replace('__TOPS__',  json.dumps(tops, ensure_ascii=False))
          .replace('__TICK__',  json.dumps(tc['tick']))
          .replace('__ZERO__',  json.dumps(tc['zero']))
          .replace('__BAR__',   json.dumps(tc['ac_today']))
          .replace('__BARH__',  json.dumps(tc['ac_line']))
          .replace('__CURLABEL__', json.dumps('US$' if lang == 'en' else ''))
          .replace('__UNIT__',  json.dumps('B' if lang == 'en' else '億'))
          .replace('__UID__',   'ars-year'))
    return (f'<div class="ars-chart-wrap"><div class="ars-chart-canvas">'
            f'<canvas id="ars-year"></canvas></div></div><script>{js}</script>')


def _ars_cases_html(df_ars, lang, s):
    a = s['ars']
    df = df_ars.sort_values('announce_date', ascending=False)
    # desktop table
    rows = []
    for _, r in df.iterrows():
        name = html.escape(r['system_en'] if lang == 'en' else r['system_zh'])
        rows.append(
            f'<tr><td class="num">{html.escape(r["announce_date"])}</td>'
            f'<td style="white-space:normal;max-width:280px">{name}</td>'
            f'<td>{_ars_cat_badge(r["category"], s)}</td>'
            f'<td class="num">{fmt_money(r["value_usd_m"], lang)}</td>'
            f'<td>{_ars_status_badge(r["delivery_status"], s)}</td>'
            f'<td>{_ars_srcs(r, s) or "—"}</td></tr>')
    table = (f'<div class="ars-tbl-wrap tbl-wrap"><table><thead><tr>'
             f'<th>{a["th_date"]}</th><th>{a["th_system"]}</th><th>{a["th_cat"]}</th>'
             f'<th class="num">{a["th_value"]}</th><th>{a["th_status"]}</th>'
             f'<th>{a["th_src"]}</th></tr></thead><tbody>'
             + ''.join(rows) + '</tbody></table></div>')
    # mobile cards
    cards = []
    for _, r in df.iterrows():
        name = html.escape(r['system_en'] if lang == 'en' else r['system_zh'])
        qtyl = _ars_qty_label(r['qty'], r['qty_unit'], lang)
        meta = (f'<span>{html.escape(r["announce_date"])}</span>'
                f'<span>{_ars_cat_badge(r["category"], s)}</span>'
                f'<span>{fmt_money(r["value_usd_m"], lang)}</span>'
                f'<span>{_ars_status_badge(r["delivery_status"], s)}</span>')
        if lang == 'en':
            body_parts = []
            if qtyl:
                body_parts.append(f'{a["card_qty"]}: {qtyl}')
            fd = _ars_clean_en(r['first_delivery'])
            ec = _ars_clean_en(r['expected_complete'])
            if fd:
                body_parts.append(f'first delivery {fd}')
            if ec:
                body_parts.append(f'expected {ec}')
            body_parts.append(_ars_srcs(r, s))
            body = ' · '.join(p for p in body_parts if p)
        else:
            note = html.escape(r['delivered_note'] or r['notes'].split('；')[0])
            body = (f'{a["card_qty"]}：{qtyl}<br>' if qtyl else '') + note
            srcs = _ars_srcs(r, s)
            if srcs:
                body += f'<br>{srcs}'
        cards.append(
            f'<details class="ars-card"><summary>'
            f'<div class="ars-card-top"><span class="ars-card-sys">{name}</span></div>'
            f'<div class="ars-card-meta">{meta}</div></summary>'
            f'<div class="ars-card-body">{body}</div></details>')
    return (f'<div class="ars-cases">{table}'
            f'<div class="ars-cards">' + ''.join(cards) + '</div></div>')


_ARS_ST_ORDER = {'completed': 0, 'delivering': 1, 'announced': 2, 'unknown': 3, 'cancelled': 4}


def _ars_base_unit(u):
    """去掉單位的括號附注（『套(發射系統)』→『套』），供合併卡判斷單位是否一致。"""
    for sep in ('(', '（'):
        if sep in u:
            u = u.split(sep)[0]
    return u.strip()


def _ars_agg_label(cases, lang):
    """回傳 (主數字標, 括號分項)。單案＝該案數量標，無分項；多案且單位一致＝加總＋
    按案分項（含狀態）；單位不一致＝並列各案數量，無分項。"""
    if len(cases) == 1:
        r = cases[0]
        return _ars_qty_label(r['qty'], r['qty_unit'], lang), ''
    units = {_ars_base_unit(r['qty_unit']) for r in cases}
    join = ' + ' if lang == 'en' else '＋'
    if len(units) == 1:
        total = sum(int(float(r['qty'])) for r in cases)
        main = _ars_qty_label(str(total), _ars_base_unit(cases[0]['qty_unit']), lang)
        parts = []
        for r in cases:
            zh, en, _ = ARSENAL_STATUS[r['delivery_status']]
            lbl = en if lang == 'en' else zh
            parts.append(f'{int(float(r["qty"])):,} {lbl}')
        brk = ('(' + join.join(parts) + ')') if lang == 'en' else '（' + join.join(parts) + '）'
        return main, brk
    main = join.join(_ars_qty_label(r['qty'], r['qty_unit'], lang) for r in cases)
    return main, ''


def _ars_syscards_html(df_ars, lang, s):
    """系統卡片牆：主要裝備（category≠sustainment 且 qty 非空）依 ARSENAL_SYSCARD
    歸併為系統卡。有 card-{key}.jpg 掛 16:9 圖帶，否則退無圖緊湊版（類別占位磚）。
    卡片依系統內最高進度排序，同組依系統合計案值由大到小。"""
    a = s['ars']
    major = df_ars[(df_ars['category'] != 'sustainment') & (df_ars['qty'] != '')]
    # 依 ARSENAL_SYSCARD 分組，保留每案原始 dict
    groups = {}
    for _, r in major.iterrows():
        key = ARSENAL_SYSCARD.get(r['case_id'], r['case_id'])
        groups.setdefault(key, []).append(r)
    cards = []
    for key, rows in groups.items():
        rows = sorted(rows, key=lambda r: (_ARS_ST_ORDER.get(r['delivery_status'], 3),
                                           -float(r['value_usd_m'])))
        top_st = min(_ARS_ST_ORDER.get(r['delivery_status'], 3) for r in rows)
        tot_val = sum(float(r['value_usd_m']) for r in rows)
        cards.append((top_st, -tot_val, key, rows))
    cards.sort(key=lambda c: (c[0], c[1]))

    out = []
    for _, _, key, rows in cards:
        first = rows[0]
        if key in ARSENAL_SYSCARD_NAME:
            name_zh, name_en = ARSENAL_SYSCARD_NAME[key]
        else:
            name_zh, name_en = first['system_zh'], first['system_en']
        name = html.escape(name_en if lang == 'en' else name_zh)
        # zh 頁附 en 副標；en 頁主名已是英文，不重複
        sub = f'<span class="en">{html.escape(name_en)}</span>' if lang != 'en' else ''
        main_agg, brk = _ars_agg_label(rows, lang)
        agg_html = (f'<span class="ars-scard-agg">{html.escape(main_agg)}'
                    + (f'<span class="brk">{html.escape(brk)}</span>' if brk else '')
                    + '</span>')
        # 進度列（每案一條）
        prows = []
        for r in rows:
            qtyl = _ars_qty_label(r['qty'], r['qty_unit'], lang)
            prows.append(
                f'<div class="ars-scard-row">'
                f'<div class="ars-scard-row-top">'
                f'<span class="ars-scard-case">{html.escape(r["case_id"])}</span>'
                f'<span class="ars-scard-qty">{html.escape(qtyl)}</span>'
                f'{_ars_status_badge(r["delivery_status"], s)}</div>'
                f'{_ars_bar(r["delivery_status"])}</div>')
        rows_html = '<div class="ars-scard-rows">' + ''.join(prows) + '</div>'
        # 展開內容：按案分段（案號＋名稱＋既有延宕/來源明細）
        segs = []
        for r in rows:
            seg_name = html.escape(r['system_en'] if lang == 'en' else r['system_zh'])
            segs.append(f'<div class="ars-scard-seg">'
                        f'<div class="ars-scard-seg-h">{html.escape(r["case_id"])} · {seg_name}</div>'
                        f'{_ars_matrix_detail(r, s, lang)}</div>')
        detail_html = '<div class="ars-scard-detail">' + ''.join(segs) + '</div>'
        # 延宕標記只掛在「真的有登錄延宕理由」的卡上（ARSENAL_DELAYS）。展開提示一律中性，
        # 否則 49 案中僅 7 案延宕、卡卡都寫「展開延宕理由」會讓讀者誤以為每案都延宕
        # （2026-07-30 使用者回報）。
        has_delay = any(r['case_id'] in ARSENAL_DELAYS for r in rows)
        chip = (f'<span class="ars-delaychip">{a["matrix_delay_chip"]}</span>'
                if has_delay else '')
        caret = (f'<span class="ars-scard-foot">'
                 f'<span class="ars-caret"><span class="tri">▸</span>{a["matrix_expand"]}</span>'
                 f'{chip}</span>')
        # 圖帶條件式渲染
        card_file = f'card-{key}.jpg'
        if (ARSENAL_ASSET_DIR / card_file).exists():
            img_html = (f'<div class="ars-scard-img">'
                        f'<img src="/assets/arsenal/{card_file}" alt="{name}" loading="lazy"></div>')
            head_html = (f'<div class="ars-scard-head">'
                         f'<div class="ars-scard-titles">'
                         f'<span class="ars-scard-name">{name}{sub}</span></div>'
                         f'{agg_html}</div>')
        else:
            # 設計化占位帶：與圖帶同高的斜紋底＋類別大字，避免無圖卡顯得殘缺
            word_map = ARSENAL_CAT_WORD_EN if lang == 'en' else ARSENAL_CAT_WORD
            word = word_map.get(first['category'], '')
            noimg_note = 'No public-domain archive photo' if lang == 'en' else '暫無公開檔案照'
            img_html = (f'<div class="ars-scard-img ars-scard-band" aria-hidden="true">'
                        f'<span class="band-word">{word}</span>'
                        f'<span class="band-note">{noimg_note}</span></div>')
            head_html = (f'<div class="ars-scard-head">'
                         f'<div class="ars-scard-titles">'
                         f'<span class="ars-scard-name">{name}{sub}</span></div>'
                         f'{agg_html}</div>')
        out.append(
            f'<details class="ars-syscard"><summary>{img_html}'
            f'<div class="ars-scard-body">{head_html}{rows_html}{caret}</div>'
            f'</summary>{detail_html}</details>')
    return '<div class="ars-syscards">' + ''.join(out) + '</div>'


def build_arsenal(df_ars, df_peers, lang, out_dir, s):
    """/arsenal/index.html（zh 於 SITE_DIR/arsenal，en 於 SITE_DIR/en/arsenal）。"""
    a = s['ars']
    total_m = df_ars['value_usd_m'].sum()
    n_cases = len(df_ars)
    n_deliver = int((df_ars['delivery_status'] == 'delivering').sum())
    n_done    = int((df_ars['delivery_status'] == 'completed').sum())
    n_cancel  = int((df_ars['delivery_status'] == 'cancelled').sum())
    latest    = df_ars['announce_date'].max()
    total_disp = f'{total_m / 100:.0f}' if lang != 'en' else fmt_money(total_m, lang)
    # 資料更新日：讀 data/arsenal_updated.txt——只在軍購資料實際調整時由編修流程
    # 更新該檔（見 project-reference「軍購資料更新流程」），每日 CI 重建不會動它。
    upd_file = DATA_FILE.parent / 'arsenal_updated.txt'
    data_updated = upd_file.read_text(encoding='utf-8').strip() if upd_file.exists() else latest

    # KPI 卡（2×3）
    unit_case = a['kpi_unit_case']
    kpis = [
        (fmt_money(total_m, lang), a['kpi_value'], 'y'),
        (f'{n_cases}<small>{unit_case}</small>' if unit_case else f'{n_cases}', a['kpi_cases'], ''),
        (str(n_deliver), a['kpi_deliver'], 'y'),
        (str(n_done), a['kpi_done'], ''),
        (str(n_cancel), a['kpi_cancel'], ''),
        (f'<span style="font-size:1.2rem">{data_updated}</span>', a['kpi_latest'], ''),
    ]
    kpi_html = ''.join(
        f'<div class="ars-kpi"><div class="ars-kpi-n {cls}">{val}</div>'
        f'<div class="ars-kpi-l">{lab}</div></div>'
        for val, lab, cls in kpis)

    # 主要裝備系統卡片牆（category≠sustainment 且 qty 非空 → 歸併為系統卡）
    matrix_html = _ars_syscards_html(df_ars, lang, s)

    reads_html   = _ars_reads_html(df_ars, df_peers, lang, s)
    # 延宕對照表已移除（2026-07-24 使用者裁定）：與系統卡展開內容重複；
    # _ars_delay_table_html 一併移除，延宕資訊唯一入口＝卡片展開區。
    chart_html   = _ars_chart_html(df_ars, lang, s)
    cases_html   = _ars_cases_html(df_ars, lang, s)
    wcards_html  = _ars_weapon_cards_html(lang, s)
    divert_link  = '/en/arsenal/' if lang == 'en' else '/arsenal/'

    today_label = fmt_date_display(df_ars['announce_date'].max(), lang)
    head = make_head(lang, 'arsenal', s, head_extra=arsenal_jsonld(lang, s, df_ars),
                     page_path='/arsenal/', abs_assets=True)
    html_doc = f"""{head}
<body>
<div class="top-bar">
  <span>{a['topbar']}</span>
  <span>2019 → {latest[:4]}</span>
</div>
<header class="site-header">
  <div class="header-inner">
    <div class="site-brand">
      <div class="site-title">{s['site_title']}</div>
      <div class="site-sub">{s['site_sub']}</div>
    </div>
    {nav_html('arsenal', lang, 'arsenal', s)}
  </div>
</header>

<main>
  <div class="ars-hero anim-ready">
    <h1 class="ars-h1">{a['h1']}</h1>
    <p class="ars-sub">{a['sub'].format(n=n_cases, total=total_disp)}</p>
  </div>

  <div class="ars-kpis anim-ready">{kpi_html}</div>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['matrix_title']}</div>
    {matrix_html}
    <p class="ars-note">{a['matrix_note']}</p>
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['chart_title']}<span class="sub">{a['chart_sub']}</span></div>
    {chart_html}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['read_title']}</div>
    <p class="ars-lead">{a['read_intro']}</p>
    {reads_html}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['table_title']}<span class="sub">{a['table_sub'].format(n=n_cases)}</span></div>
    {cases_html}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['wcards_title']}</div>
    {wcards_html}
  </section>

  <div class="ars-scope"><span class="st">{a['scope_title']}</span>{a['scope_body']}</div>
</main>

{_ANIM_JS}
{footer_html(today_label, s)}
</body></html>"""

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'index.html').write_text(html_doc, encoding='utf-8')
    rel = 'arsenal' if out_dir.parent == SITE_DIR else 'en/arsenal'
    print(f'[OK] {rel}/index.html')


# ── /arsenal/{harpoon,patriot,himars}.html 武器內頁 ──────────────────────────

def _domain(url):
    m = re.match(r'https?://([^/]+)', url or '')
    d = m.group(1) if m else ''
    return d[4:] if d.startswith('www.') else d


# 來源機構短名（chip 文字）：exact 網域對應優先，其餘取可註冊網域主標籤（如 flightglobal）。
# 含中文短名者提供 (zh, en)，供 en 頁改用英文縮寫（en 頁不得含中文）。
_SRC_LABEL_EXACT = {
    'media.defense.gov': ('DSCA', 'DSCA'),
    'dsca.mil':          ('DSCA', 'DSCA'),
    'web.archive.org':   ('DSCA·檔案館', 'DSCA·Archive'),
    'cna.com.tw':        ('中央社', 'CNA'),
    'focustaiwan.tw':    ('Focus Taiwan', 'Focus Taiwan'),
    'tsm.schar.gmu.edu': ('TSM', 'TSM'),
    'gao.gov':           ('GAO', 'GAO'),
    'news.usni.org':     ('USNI', 'USNI'),
    'defense.gov':       ('DoD', 'DoD'),
    'mnd.gov.tw':        ('國防部', 'MND'),
    'cato.org':          ('Cato', 'Cato'),
    'ltn.com.tw':        ('自由時報', 'LTN'),
    'def.ltn.com.tw':    ('自由軍武', 'LTN Defense'),
    'dvidshub.net':      ('DVIDS', 'DVIDS'),
    'defensenews.com':   ('Defense News', 'Defense News'),
    'flightglobal.com':  ('FlightGlobal', 'FlightGlobal'),
    'breakingdefense.com': ('Breaking Defense', 'Breaking Defense'),
    'armyrecognition.com': ('Army Recognition', 'Army Recognition'),
    'taiwannews.com.tw': ('Taiwan News', 'Taiwan News'),
    'rfa.org':           ('自由亞洲電台', 'RFA'),
    'centcom.mil':       ('CENTCOM', 'CENTCOM'),
    'crsreports.congress.gov': ('CRS', 'CRS'),
    'everycrsreport.com': ('CRS', 'CRS'),
    'armscontrol.org':   ('Arms Control Assn', 'Arms Control Assn'),
    'thedefensepost.com': ('Defense Post', 'Defense Post'),
    'scmp.com':          ('SCMP', 'SCMP'),
    'navalpost.com':     ('Naval Post', 'Naval Post'),
    'navalnews.com':     ('Naval News', 'Naval News'),
    'congress.gov':      ('Congress.gov', 'Congress.gov'),
    'army-technology.com': ('Army Technology', 'Army Technology'),
    'globalsecurity.org': ('GlobalSecurity', 'GlobalSecurity'),
}
# 多段公共後綴：主標籤取 parts[-3]（如 taiwannews.com.tw → taiwannews）
_MULTI_SUFFIX = {'com.tw', 'gov.tw', 'org.tw', 'net.tw', 'com.au', 'org.uk',
                 'co.uk', 'gov.uk', 'com.ua'}


def _src_label(url, lang='zh'):
    """由網域回傳來源機構短名（chip 文字）。"""
    host = _domain(url)                       # 已去 www.
    parts = host.split('.')
    # 依序試：完整 host → 尾三段 → 尾兩段（讓 news.ltn.com.tw 也命中 ltn.com.tw）
    for cand in (host, '.'.join(parts[-3:]), '.'.join(parts[-2:])):
        pair = _SRC_LABEL_EXACT.get(cand)
        if pair:
            return pair[1] if lang == 'en' else pair[0]
    if len(parts) >= 3 and '.'.join(parts[-2:]) in _MULTI_SUFFIX:
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return host


def _src_chip(url, lang='zh'):
    """來源徽章：機構短名＋外連箭頭（樣式見 .src-chip）。取代預設藍色超連結。"""
    if not url:
        return ''
    return (f'<a class="src-chip" href="{html.escape(url)}" target="_blank" rel="noopener">'
            f'{html.escape(_src_label(url, lang))}</a>')


def _ars_alliance_tag(notes, lang):
    """由 peers.notes 判斷同盟標籤。先移除否定字串（『非美援』『非條約盟邦』），
    再依 MNNA→aid→treaty→nato→partner 順序判斷——避免『非條約盟邦』⊂『條約盟邦』、
    『非美援』⊂『美援』、『主要非北約盟友』⊂『北約』等子字串誤判（judgment.md 記載坑）。"""
    n = (notes.replace('非美援', '').replace('非條約盟邦', '')
              .replace('非北約盟友', '').replace('非MNNA', '').replace('非NATO', ''))
    if 'MNNA' in n or '主要非北約盟友' in notes:
        k = 'mnna'
    elif '美援' in n:
        k = 'aid'
    elif '條約盟邦' in n:
        k = 'treaty'
    elif '北約' in n:
        k = 'nato'
    else:
        k = 'partner'
    zh, en, cls = _ALLIANCE_TAG[k]
    return (en if lang == 'en' else zh), cls, k


def _ars_rank_data(df_peers, key, lang):
    """依 qty 由大到小的買家列表（同國多列彙總）。每列含國名、數量、同盟標籤、訂購年、來源。"""
    sub = df_peers[df_peers['system_key'] == key]
    agg = {}
    for _, r in sub.iterrows():
        c = r['buyer_country']
        e = agg.setdefault(c, {'qty': 0, 'notes': '', 'year': '', 'src': ''})
        e['qty'] += int(r['qty'])
        e['notes'] += ' ' + r['notes']
        if not e['src']:
            e['src'] = r['source']
        if not e['year']:
            e['year'] = r['order_year']
    rows = []
    for c, e in agg.items():
        disp = COUNTRY_EN.get(c, c) if lang == 'en' else c
        tag, cls, k = _ars_alliance_tag(e['notes'], lang)
        rows.append({'country': disp, 'qty': e['qty'], 'tag': tag, 'tagcls': cls,
                     'is_tw': c == '台灣', 'is_aid': k == 'aid',
                     'year': e['year'], 'src': e['src']})
    rows.sort(key=lambda x: -x['qty'])
    return rows


def _ars_rank_chart_html(df_peers, key, lang, s):
    """國際買家橫條排名圖（同色相強調）。y tick＝國名＋同盟；bar 端＝數量；tooltip＝年＋來源。"""
    a = s['ars']
    rows = _ars_rank_data(df_peers, key, lang)
    tc = _CHART_COLORS[THEME]
    accent, dark = tc['ac_today'], tc['ac_other']
    countries = [(f"{r['country']} [{r['tag']}]" if lang == 'en' else f"{r['country']} 〔{r['tag']}〕")
                 for r in rows]
    vals   = [r['qty'] for r in rows]
    colors = [accent if r['is_tw'] else dark for r in rows]
    tw_idx  = next((i for i, r in enumerate(rows) if r['is_tw']), -1)
    aid_idx = next((i for i, r in enumerate(rows) if r['is_aid']), -1)
    info = [[f"{a['rank_year']}{r['year']}", f"{a['rank_src']}{_domain(r['src'])}"] for r in rows]
    height = max(len(rows) * 34, 170)
    js = (_CHART_JS_RANK
          .replace('__COUNTRIES__', json.dumps(countries, ensure_ascii=False))
          .replace('__VALS__',   json.dumps(vals))
          .replace('__COLORS__', json.dumps(colors))
          .replace('__INFO__',   json.dumps(info, ensure_ascii=False))
          .replace('__TWIDX__',  json.dumps(tw_idx))
          .replace('__AIDIDX__', json.dumps(aid_idx))
          .replace('__TICK__',   json.dumps(tc['tick']))
          .replace('__ZERO__',   json.dumps(tc['zero']))
          .replace('__ACCENT__', json.dumps(accent))
          .replace('__LBLCOL__', json.dumps(tc['tick']))
          .replace('__AIDCOL__', json.dumps(tc['sh_line']))
          .replace('__QLABEL__', json.dumps(a['rank_q']))
          .replace('__UID__',    'ars-rank'))
    return (f'<div class="ars-chart-wrap"><div class="ars-rank-canvas" style="height:{height}px">'
            f'<canvas id="ars-rank"></canvas></div></div><script>{js}</script>')


# PAC-3 使用國型號（世代不可比，故不做排名圖；zh 用全形＋、en 用半形 +）
_PAC3_VARIANT = {
    '台灣':         ('PAC-3 CRI', 'PAC-3 CRI'),
    '德國':         ('PAC-3 MSE', 'PAC-3 MSE'),
    '沙烏地阿拉伯': ('PAC-3 MSE', 'PAC-3 MSE'),
    '波蘭':         ('PAC-3 MSE', 'PAC-3 MSE'),
    '羅馬尼亞':     ('PAC-3 MSE ＋ PAC-2 GEM-T', 'PAC-3 MSE + PAC-2 GEM-T'),
    '阿聯':         ('PAC-3 ＋ PAC-2 GEM-T', 'PAC-3 + PAC-2 GEM-T'),
}


def _ars_pac3_wall_html(df_peers, lang, s):
    """PAC-3 使用國卡片牆（愛國者頁專用，取代排名圖）。每卡：國名＋型號＋數量＋同盟＋來源。"""
    a = s['ars']
    sub = df_peers[df_peers['system_key'] == 'patriot'].copy()
    sub = sub.sort_values('qty', ascending=False)
    cards = []
    for _, r in sub.iterrows():
        cc = r['buyer_country']
        country = COUNTRY_EN.get(cc, cc) if lang == 'en' else cc
        tag, cls, _k = _ars_alliance_tag(r['notes'], lang)
        vz, ve = _PAC3_VARIANT.get(cc, (r['variant_tier'], r['variant_tier']))
        variant = ve if lang == 'en' else vz
        qtyl = _ars_qty_label(r['qty'], '枚', lang)
        srch = _src_chip(r['source'], lang)
        cards.append(
            f'<div class="ars-usercard">'
            f'<div class="ars-uc-top"><span class="ars-uc-country">{html.escape(country)}</span>'
            f'<span class="ars-atag {cls}">{html.escape(tag)}</span></div>'
            f'<div class="ars-uc-var">{html.escape(variant)}</div>'
            f'<div class="ars-uc-meta">{html.escape(qtyl)} · {html.escape(r["order_year"])} · {srch}</div>'
            f'</div>')
    return '<div class="ars-userwall">' + ''.join(cards) + '</div>'


def _ars_detail_hero_img_html(weapon_key, name, lang):
    """武器內頁 H1 下方橫幅：僅當 assets/arsenal/hero-{weapon_key}.jpg 實際存在才渲染
    （目前尚無 hero 檔，回空字串；資產補上後重 build 即生效，無需再改程式）。"""
    fname = f'hero-{weapon_key}.jpg'
    if not (ARSENAL_ASSET_DIR / fname).exists():
        return ''
    credit = _ars_credit_line(fname, lang)
    courtesy = f'<span class="ars-hero-courtesy">{html.escape(credit)}</span>' if credit else ''
    return (f'<div class="ars-hero-imgwrap"><img class="ars-hero-img" '
            f'src="/assets/arsenal/{fname}" alt="{html.escape(name)}" loading="lazy">{courtesy}</div>')


def _ars_detail_credit_li(weapon_key, lang):
    """頁尾來源清單追加一行「影像：{photographer}, {unit}（DVIDS）」。
    優先用實際存在的 hero-{weapon_key}.jpg 的 credits；沒有 hero 檔則退回該武器
    的代表影像（ARSENAL_WEAPON_IMAGE，patriot 暫無 → 不輸出）。"""
    hero_file = f'hero-{weapon_key}.jpg'
    fname = hero_file if (ARSENAL_ASSET_DIR / hero_file).exists() else ARSENAL_WEAPON_IMAGE.get(weapon_key)
    credit = _ars_credit_line(fname, lang)
    return f'<li>{html.escape(credit)}</li>' if credit else ''


def _ars_hero_stats_html(weapon, lang):
    cells = []
    for lz, le, vz, ve in weapon['hero']:
        lab = le if lang == 'en' else lz
        val = ve if lang == 'en' else vz
        cells.append(
            f'<div class="ars-kpi"><div class="ars-kpi-n y" style="font-size:1.1rem;line-height:1.25">'
            f'{html.escape(val)}</div><div class="ars-kpi-l">{html.escape(lab)}</div></div>')
    return '<div class="ars-kpis">' + ''.join(cells) + '</div>'


def _ars_timeline_html(weapon, lang, s):
    a = s['ars']
    items = []
    for dz, de, bz, be, src in weapon['timeline']:
        date = de if lang == 'en' else dz
        body = be if lang == 'en' else bz
        srch = (' ' + _src_chip(src, lang)) if src else ''
        items.append(
            f'<div class="ars-tl-item"><div class="ars-tl-date">{html.escape(date)}</div>'
            f'<div class="ars-tl-body">{html.escape(body)}{srch}</div></div>')
    return '<div class="ars-tl">' + ''.join(items) + '</div>'


def _ars_combat_html(weapon, lang, s):
    a = s['ars']
    blocks = []
    for tz, te, bz, be, src in weapon['combat']:
        title = te if lang == 'en' else tz
        body  = be if lang == 'en' else bz
        srch = f'<div class="ars-src">{_src_chip(src, lang)}</div>' if src else ''
        blocks.append(f'<div class="ars-point"><h3>{html.escape(title)}</h3>'
                      f'<p>{html.escape(body)}</p>{srch}</div>')
    note = weapon.get('combat_note_en' if lang == 'en' else 'combat_note_zh')
    note_html = f'<p class="ars-note">{html.escape(note)}</p>' if note else ''
    return '<div class="ars-reads">' + ''.join(blocks) + '</div>' + note_html


def _ars_role_html(weapon, lang):
    items = weapon['role_en' if lang == 'en' else 'role_zh']
    return '<ul class="ars-role">' + ''.join(f'<li>{html.escape(t)}</li>' for t in items) + '</ul>'


def _ars_srclist_html(weapon, df_peers, lang):
    urls = []
    for row in weapon['timeline']:
        if row[4]:
            urls.append(row[4])
    for row in weapon['combat']:
        if row[4]:
            urls.append(row[4])
    if weapon['has_rank']:
        for r in _ars_rank_data(df_peers, weapon['rank_key'], lang):
            if r['src']:
                urls.append(r['src'])
    else:
        for _, r in df_peers[df_peers['system_key'] == weapon['rank_key']].iterrows():
            if r['source']:
                urls.append(r['source'])
    seen, items = set(), []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        desc = u.split('://', 1)[-1]
        items.append(f'<li>{_src_chip(u, lang)} '
                     f'<span class="src-full">{html.escape(desc)}</span></li>')
    return '<ul class="ars-srclist">' + ''.join(items) + '</ul>'


def _ars_weapon_cards_html(lang, s):
    """主頁武器內頁卡（3 張），每卡一句實戰 teaser，整卡連向內頁。
    himars/harpoon 有代表影像（16:9 圖片帶）；patriot 暫無專圖，維持無圖版型。"""
    a = s['ars']
    cards = []
    for wkey in ARS_DETAIL_PAGES:
        d = ARSENAL_DETAIL[wkey]
        name   = d['name_en'] if lang == 'en' else d['name_zh']
        teaser = d['teaser_en'] if lang == 'en' else d['teaser_zh']
        href = f'/en/arsenal/{wkey}.html' if lang == 'en' else f'/arsenal/{wkey}.html'
        img_file = ARSENAL_WEAPON_IMAGE.get(wkey)
        img_html = (f'<img class="ars-wcard-img" src="/assets/arsenal/{img_file}" '
                    f'alt="{html.escape(name)}" loading="lazy">') if img_file else ''
        cards.append(
            f'<a class="ars-wcard" href="{href}">{img_html}'
            f'<div class="ars-wcard-body">'
            f'<div class="ars-wcard-name">{html.escape(name)}</div>'
            f'<div class="ars-wcard-var">{html.escape(d["variant"])}</div>'
            f'<p class="ars-wcard-teaser">{html.escape(teaser)}</p>'
            f'<span class="ars-wcard-cta">{a["wcards_cta"]}</span></div></a>')
    return '<div class="ars-wcards">' + ''.join(cards) + '</div>'


def build_arsenal_detail(weapon_key, df_ars, df_peers, lang, out_dir, s):
    """/arsenal/{weapon}.html（zh）＋ /en/arsenal/{weapon}.html。"""
    a = s['ars']
    w = ARSENAL_DETAIL[weapon_key]
    name = w['name_en'] if lang == 'en' else w['name_zh']
    page_name = f'ars_{weapon_key}'
    head = make_head(lang, page_name, s,
                     head_extra=arsenal_jsonld(lang, s, df_ars, weapon_key),
                     page_path=f'/arsenal/{weapon_key}.html', abs_assets=True)
    back_href = '/en/arsenal/' if lang == 'en' else '/arsenal/'

    hero_img = _ars_detail_hero_img_html(weapon_key, name, lang)
    hero   = _ars_hero_stats_html(w, lang)
    tl     = _ars_timeline_html(w, lang, s)
    combat = _ars_combat_html(w, lang, s)
    role   = _ars_role_html(w, lang)
    credit_li = _ars_detail_credit_li(weapon_key, lang)
    srcs   = _ars_srclist_html(w, df_peers, lang)
    if credit_li:
        srcs = srcs.replace('</ul>', credit_li + '</ul>')

    if w['has_rank']:
        rows = _ars_rank_data(df_peers, w['rank_key'], lang)
        note = (f'<p class="ars-note">{a["rank_note"]}</p>'
                if any(r['is_aid'] for r in rows) else '')
        rank_sec = (
            f'<section class="ars-section anim-ready">'
            f'<div class="ars-sec-title">{a["rank_title"]}</div>'
            f'<p class="ars-lead">{a["rank_intro"]}</p>'
            f'{_ars_rank_chart_html(df_peers, w["rank_key"], lang, s)}{note}</section>')
    else:
        rank_sec = (
            f'<section class="ars-section anim-ready">'
            f'<div class="ars-sec-title">{a["users_title"]}</div>'
            f'<p class="ars-lead">{a["users_intro"]}</p>'
            f'{_ars_pac3_wall_html(df_peers, lang, s)}</section>')

    today_label = fmt_date_display(df_ars['announce_date'].max(), lang)

    # 同系列內頁互連（SEO：內頁之間傳遞權重＋給爬蟲第二條入路）
    sib_pfx = '/en/arsenal/' if lang == 'en' else '/arsenal/'
    sib_links = ''.join(
        f'<a class="ars-back" href="{sib_pfx}{k}.html" style="margin-right:1.2rem">'
        f'{html.escape(ARSENAL_DETAIL[k]["name_en" if lang == "en" else "name_zh"])} →</a>'
        for k in ARSENAL_DETAIL if k != weapon_key)

    html_doc = f"""{head}
<body>
<div class="top-bar">
  <span>{a['topbar']}</span>
  <span>{html.escape(w['variant'])}</span>
</div>
<header class="site-header">
  <div class="header-inner">
    <div class="site-brand">
      <div class="site-title">{s['site_title']}</div>
      <div class="site-sub">{s['site_sub']}</div>
    </div>
    {nav_html('arsenal', lang, page_name, s)}
  </div>
</header>

<main>
  <div class="ars-hero anim-ready">
    <a class="ars-back" href="{back_href}">{a['detail_back']}</a>
    <h1 class="ars-h1">{html.escape(name)}</h1>
    {hero_img}
    <p class="ars-sub">{html.escape(w['variant'])}</p>
  </div>

  {hero}

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['tl_title']}</div>
    {tl}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['combat_title']}</div>
    <p class="ars-lead">{a['combat_intro']}</p>
    {combat}
  </section>

  {rank_sec}

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['role_title']}</div>
    {role}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['src_title']}</div>
    {srcs}
  </section>

  <section class="ars-section anim-ready">
    <div class="ars-sec-title">{a['more_title']}</div>
    <p>{sib_links}</p>
  </section>
</main>

{_ANIM_JS}
{footer_html(today_label, s)}
</body></html>"""

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'{weapon_key}.html').write_text(html_doc, encoding='utf-8')
    rel = 'arsenal' if out_dir.parent == SITE_DIR else 'en/arsenal'
    print(f'[OK] {rel}/{weapon_key}.html')


# ── sitemap.xml / robots.txt ──────────────────────────────────────────────────

def build_sitemap(df):
    """Generate sitemap.xml covering both languages, with hreflang alternates."""
    data_mod   = df['date'].max()                       # 資料頁用最新資料日期
    build_mod  = f'{_VER[:4]}-{_VER[4:6]}-{_VER[6:8]}'  # 靜態頁用 build 日期（_VER 含時分，只取到日）
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

    # /arsenal/（目錄式路徑，非 .html）：zh + en。index 加 3 個武器內頁。
    ars_zh = f'{BASE_URL}/arsenal/'
    ars_en = f'{BASE_URL}/en/arsenal/'
    for loc in (ars_zh, ars_en):
        blocks.append(
            '  <url>\n'
            f'    <loc>{loc}</loc>\n'
            f'    <lastmod>{build_mod}</lastmod>\n'
            '    <changefreq>weekly</changefreq>\n'
            '    <priority>0.8</priority>\n'
            f'    <xhtml:link rel="alternate" hreflang="zh-Hant" href="{ars_zh}"/>\n'
            f'    <xhtml:link rel="alternate" hreflang="en" href="{ars_en}"/>\n'
            f'    <xhtml:link rel="alternate" hreflang="x-default" href="{ars_zh}"/>\n'
            '  </url>'
        )
    for wkey in ARS_DETAIL_PAGES:
        d_zh = f'{BASE_URL}/arsenal/{wkey}.html'
        d_en = f'{BASE_URL}/en/arsenal/{wkey}.html'
        for loc in (d_zh, d_en):
            blocks.append(
                '  <url>\n'
                f'    <loc>{loc}</loc>\n'
                f'    <lastmod>{build_mod}</lastmod>\n'
                '    <changefreq>monthly</changefreq>\n'
                '    <priority>0.7</priority>\n'
                f'    <xhtml:link rel="alternate" hreflang="zh-Hant" href="{d_zh}"/>\n'
                f'    <xhtml:link rel="alternate" hreflang="en" href="{d_en}"/>\n'
                f'    <xhtml:link rel="alternate" hreflang="x-default" href="{d_zh}"/>\n'
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
    df_ars   = load_arsenal()
    df_peers = load_peers()
    THEME = resolve_theme(df)   # 依當日資料決定全站主題（嚴重日 dark / 平常日 light）
    print(f'[OK] theme = {THEME}')
    build_css()

    for lang in ('zh', 'en'):
        s = STRINGS[lang]
        if lang == 'zh':
            out_dir = SITE_DIR
            ars_dir = SITE_DIR / 'arsenal'
        else:
            out_dir = SITE_DIR / 'en'
            out_dir.mkdir(exist_ok=True)
            ars_dir = SITE_DIR / 'en' / 'arsenal'

        build_index(df, lang, out_dir, s, df_ars=df_ars)
        build_records(df, lang, out_dir, s)
        build_monthly(df, lang, out_dir, s)
        build_about(df, lang, out_dir, s)
        build_arsenal(df_ars, df_peers, lang, ars_dir, s)
        for wkey in ARS_DETAIL_PAGES:
            build_arsenal_detail(wkey, df_ars, df_peers, lang, ars_dir, s)

    build_sitemap(df)
    build_robots()

    (SITE_DIR / 'version.txt').write_text(_VER, encoding='utf-8')
    print('[OK] version.txt')
    print('[DONE] Site built →', SITE_DIR)
