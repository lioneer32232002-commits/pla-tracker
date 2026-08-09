# 專案參考資料（需要時才讀，不必每次載入）

> 本檔存放 CLAUDE.md 抽出的細節。改了架構性事實（新頁面、新腳本、部署方式變更）
> 時要同步更新本檔，格式見 [maintenance.md](maintenance.md)。

## 系統全貌

- **產品**：每日追蹤解放軍在台灣周邊軍事活動的靜態網站。資料來源＝中華民國國防部
  每日發布的航跡圖／公告文字。發布管道：https://pla-tracker.skyfaring.net（Cloudflare
  Pages，push 到 main 即自動部署）、Threads、部落格 https://yi-tienpan.blogspot.com。
  屬 Skyfaring 作品集（hub: https://skyfaring.net/）。
- **每日更新是全自動的**：GitHub Actions（`.github/workflows/daily_update.yml`）在
  台灣時間 12:00、14:00 抓取國防部公告，`scripts/fetch_and_update.py` 用 Claude API
  從圖片（無圖時退回公告文字）擷取數據 → 寫入 CSV → build → validate → commit →
  寄報告信；20:00 是最終檢查班，當日仍無資料才寄一封提醒信。
- **互動 session 的角色**：開發新功能、修 bug、回填資料、SEO/內容工作。不是每日更新。

## 檔案地圖

| 檔案 | 用途 |
|------|------|
| `data/records.csv` | 主資料（只能新增，禁止修改歷史列） |
| `scripts/build_site.py` | 從 CSV 產生全部 HTML（含 SEO/OG meta、Dataset JSON-LD、sitemap、robots）。~2000 行，讀之前先 Grep 定位 |
| `scripts/validate.py` | 兩段式驗證：`csv`（資料）、`html`（結構＋SEO＋sitemap＋robots＋OG）、`all` |
| `scripts/fetch_and_update.py` | CI 用的自動抓取器（Claude API 讀圖／讀文） |
| `scripts/send_daily_email.py` | CI 用的每日報告信／失敗提醒信 |
| `scripts/backfill_history.py` | 歷史回填工具（一次性） |
| `scripts/make_og_image.py` | 一次性產生 `og.png`/`og-en.png`（用 Windows 字型，只能本機跑；改品牌視覺才需要重跑） |
| `data/geo_card.json` | 分享圖卡地圖輪廓（Natural Earth 10m 裁切＋簡化，靜態；每日更新不會動它） |
| `index.html` | 首頁（總覽＋SITREP；一句話文字 SITREP 在地圖區塊之後，2026-07-23 起） |
| `records.html` / `monthly.html` | 每日紀錄頁／月度頁 |
| `about.html` / `en/about.html` | 方法論頁（build 產生，每日更新資料區間/筆數） |
| `card.html` | 每日分享圖卡（直式 1080×1350，canvas 客戶端繪製＋一鍵下載 PNG；只有中文版，noindex 不進 sitemap） |
| `sitemap.xml` / `robots.txt` | build 產生；基準網址 = `https://pla-tracker.skyfaring.net`（2026-08-05 遷入）。canonical／sitemap 一律走 `build_site.canon_url()` 去掉 `.html`——Pages 會把 `/x.html` 308 到 `/x`，canonical 指向轉址等於無效；validate 會擋 `.html</loc>` 與舊網域殘留 |
| `version.txt` | build 時間戳，每次 build 必變 |
| `_routes.json` | **配額命脈**（2026-08-05 加）。`functions/_middleware.js` 在 functions 根目錄，Pages 預設會讓全站每個請求都進 Function，連 CSS／圖片／CSV 都各算一次呼叫。免費方案 10 萬次／日是**整個帳號 13 個 Pages 專案共用**的，姊妹專案 flight-deck 8/04 一天燒了 74,213 次收到警告信。這支把靜態路徑排除掉。**新增靜態目錄要一起加進 exclude** |

## CSV 欄位

```
date, aircraft_total, median_line_cross, cross_rate,
aircraft_type, ships_total, activity_start, activity_end, special_event
```

- `aircraft_type` 合法值：`Manned` / `UAV` / `Mixed` / `Zero` / `Helicopter`
- `cross_rate` = median_line_cross ÷ aircraft_total × 100（允許 ±1% 誤差；total=0 時填 0）
- `median_line_cross` ≤ `aircraft_total`
- `activity_start` / `activity_end` 近期公告多為空，允許留空
- `special_event` 放空域描述或特殊事件，可留空

## 圖表與設計規格（改 build_site.py 圖表區才需要）

- **雙主題（2026-07-23 起）**：build 時由 CSV 最後一列決定整站深/淺色——
  嚴重日（`aircraft_total ≥ SEVERE_AC(15)` 且 `median_line_cross ≥ SEVERE_ML(10)`）
  深色，其餘淺色。`<html data-theme="dark|light">`；本機測試可用環境變數
  `PLA_THEME_OVERRIDE=light|dark` 強制。色盤常數與注入邏輯在 build_site.py 頂部
  （Grep `SEVERE_AC` 定位）。
- 深色圖表面板：`#1e2224`；軍機黃（當日 `#f5c842`，其他 `#8a7020`）；
  艦艇紅（當日 `#e05555`，其他 `#7a2a2a`）。淺色對應值見 build_site.py 色盤常數。
- 當日長條永遠高亮；圖表字體由 Chart.js options 的字級設定控制（要改先在
  build_site.py Grep `font` 定位，不要憑記憶找函式名）
- 圖表全程 Chart.js 瀏覽器端渲染。**鐵律：禁止為圖表在 build/CI 加入字型或
  Pillow 渲染**（CI 是 ubuntu、無 CJK 字型）
- **月統計頁的每日強度日曆（2026-07-30 起）**：`_monthly_heatmap_html`，純 HTML/CSS
  grid（不用 Chart.js），列＝月、欄＝該月 1→31 日，覆蓋全部歷史。三種「空白格」
  **必須維持區分**：`e`＝該月無此日／未來日、`n`＝有此日但國防部未發布、`v0`＝零架次。
  合併任兩者就是用視覺造假（目前 v0 有 42 天、n 只有 1 天）。validate.py 會檢查
  `hm-c n` 與 `hm-c v0` 都存在，合併會被攔下。
- **首頁兩組面板的差異（2026-07-30 起）**：`_CHART_JS_RECENT`＝近兩週（14 天）
  堆疊長條（下段逾越中線／上段未越線）＋30 日均虛線＋46px 艦艇細帶＋圖例；
  `_CHART_JS_YTD`＝年初至今，仍是原本的長條＋越線虛線＋130px 艦艇圖。
  改 recent 面板前先讀 `_CHART_JS_RECENT` 內的註解（記載 x/y 軸對齊為什麼要
  `offset:true` 與 `y.afterFit`，以及右緣 ~6px 殘差為何不再追）。
  `_build_panels` 傳 `avg` 才走堆疊版，不傳＝原面積線版。

## 分享圖卡 card.html（2026-07-31 起）

- 產生邏輯＝`build_site.py` 的 `_CARD_JS` ＋ `build_card()`；入口是導覽列最後一項
  `nav a.nav-card`（只有中文版加；英文版沒有 en/card.html，語言切換退回英文首頁）。
  導覽列已有六項，第七項在 ≤560px 只留圖示（`.nc-t{display:none}`），改導覽字樣前
  先量一次 390px 寬度會不會爆。
- **全部用 Canvas 2D 自繪，不得改用 html2canvas 或把 Leaflet 圖磚畫進 canvas**——
  圖磚是跨域點陣圖，會污染 canvas 讓 `toBlob()` 直接失敗（＝下載鈕壞掉）。
- 地圖輪廓讀 `data/geo_card.json`；空域方框／中線座標與首頁 `_MAP_JS` 同一組，
  空域判斷共用 `zones_from_special()`（改判斷邏輯時兩處會一起變，這是刻意的）。
- 取景由 `MH` 反推比例尺，並以 `MW/9.0` 為經度視野下限：超過這個下限，左緣會露出
  geo 資料被裁切出的直邊。改版面高度後要重看一次圖，別只看 validate。
- **空域漸層＝等高線式疊加，不要模糊、不要描邊**（2026-07-31 使用者連退兩次的結論）：
  就用首頁 `_MAP_JS` 的 `gradZone` 同一組參數（`sc=[1.0,.78,.58,.40,.24]`、
  `fo=[.04,.07,.10,.14,.19]`），一層層看得見邊界；使用者的原話是「網頁上的漸層是
  像等高線幾何疊起來，圖卡不能做一樣的嗎」。中間試過的兩版都被退：加描邊＝「有框線
  很怪」，整塊上 `ctx.filter` 模糊＝糊成沒有形狀的光斑。12 浬帶與離島光暈同理用硬邊
  分層（帶寬 `bw`／透明度 `ba` 見 `_CARD_JS`）。**要改這段前先看一眼這條。**
- 版面刻意留白、資訊只留三個當日數字＋一行空域＋一行月累計：早期版本把 pill 框、
  ▲▼ 說明、月統計面板全塞進去，使用者的評語是「太醜、資訊太多」。要加東西前先想
  這張圖是在手機動態牆上被滑過去的。
- 圖卡固定深色，不跟隨嚴重日主題（分享出去的圖在各 App 深色底上都要能看）。
- **空域框不要描邊**（2026-07-31 使用者退件）：「有框線很怪」。範圍感只靠最外層
  那一層硬邊填色（alpha 0.065），其餘全是模糊疊加層。
- 六個空域框（北部／中部／南部／西南部／東部／東北部）座標寫死在 `_MAP_JS`
  與圖卡的 `ZP`，兩邊必須一起改。**這些是依「相對台灣本島的方位」推定的示意範圍，
  不是國防部公布的座標**——公告只給空域名稱，沒有給邊界。所以地圖固定標「示意圖」，
  改框時只調整方位與相鄰關係，不要宣稱精確邊界。
- 中部／南部於 2026-07-31 補上（原本公告文字會提到地圖上沒有的空域）。中部框刻意
  停在澎湖以北（南緣 23.6°N）、東緣貼台灣西岸；南部框停在鵝鑾鼻以南（北緣 21.9°N），
  避免壓到陸地。改動時重看一次圖，別只看 validate。

## SEO 資產規則

- 所有 `<head>` meta、canonical、hreflang、OG/Twitter 卡、JSON-LD、sitemap、robots
  一律由 `build_site.py` 產生，**禁止手改任何產出 HTML**。
- OG 分享圖 `og.png`/`og-en.png` 是靜態檔，只有改品牌視覺才本機重跑
  `python -X utf8 scripts/make_og_image.py`。

## 新增頁面 checklist（每一項都要做）

1. 在 `build_site.py` 加產生邏輯（含 meta/canonical/hreflang/sitemap 條目）
2. 在 `validate.py` 加對應檢查
3. **把新檔案路徑加進 `.github/workflows/daily_update.yml` 的 `git add` 白名單**
   （漏了＝CI 不 commit 它＝線上版停更，且 CI 仍顯示 success，極難發現。
   `en/` 已涵蓋其下所有英文頁）
4. build → validate → commit 全部檔案 → push

## 軍購資料更新流程（改 data/arsenal*.csv 時）

1. 逐案查證來源後編修 `data/arsenal.csv` / `data/arsenal_peers.csv`
2. **同步把 `data/arsenal_updated.txt` 改成當天日期**（ISO）——/arsenal/ 的
   「資料更新」KPI 讀這個檔；每日 CI 重建不會動它，只有真的改了資料才變
3. build → validate → commit 全部 → push（延宕理由寫進 CSV notes，
   顯示入口＝系統卡展開區；獨立延宕對照表已於 2026-07-24 移除勿復活）

## Canva 每日圖卡（2026-08-05 起，使用者要求）

使用者在 Canva 手工維護一份圖卡母版，**動畫與字型由他自己設定**；session 每天只負責
換數字與活動空域，再交回給他套動畫、匯出 MP4。

- **母版 design id：`DAHRZtscuZM`**（標題 `20260805_PLA  TRACKER`，1080×1920 直式，
  給 Reels／Stories 用）。另有一份 4:5 舊版 `DAHRZTqPOY8`，非母版。
- **母版不可直接改**。每天用 `copy-design` 複製一份再改，改壞不影響母版。使用者明確要求
  改母版時（例：2026-08-06 加六空域），**動手前先 `copy-design` 存一份備份**——母版裡
  有他手工套的動畫與字型，改壞就是他重做。2026-08-06 的備份＝`DAHRfiLwNfE`。
- **母版已備齊六個空域且都套好動畫（2026-08-06 起）**，所以每日流程改成**只刪不插**：
  刪掉今天沒有的空域，今天有的原封不動留著。這是為了**保住動畫**——插進去的新形狀
  一定沒有動畫，使用者就得手動補。元素 id 全部登記在 `data/canva_zone_ops.json` 的
  `zones[].master_shape_ids` / `master_label_id`。
- **資料夾：`共機擾台`（folder id `FAFzxKT6D0A`）**。母版放這裡；每天複製出來的當日設計
  也要 `move-item-to-folder` 搬進去（複製預設不會落在母版所在資料夾）。
- 產生編輯指令：`python -X utf8 scripts/make_canva_ops.py --top T --left L --width W --height H`
  T/L/W/H＝母版裡**地圖元素**（viewBox 1080×816 的形狀，最底下那個海域矩形）當下的
  位置與大小，用 `read-design` 讀出來後填進去。腳本會反推投影，所以使用者之後移動或
  縮放地圖，算出來的空域仍然貼合。加 `--date` 可回填指定日期。
- 每日流程（**做之前先確認今天的設計不存在**：`list-folder-items` 查資料夾裡有沒有
  `YYYYMMDD_PLA  TRACKER`，有就直接回報連結，不要做第二份）：
  1. `copy-design` 母版 → 取得當日設計 id
  2. `read-design`（開 transaction）→ 交易 id；核對地圖元素位置與 `map_element` 相符
  3. 跑 `make_canva_ops.py` 取得 `texts` 與今日空域集合（沒有本機環境時改查
     `data/canva_zone_ops.json` ＋ 從網站首頁讀當日數字）
  4. `edit-design`：`update_title` 改成 `YYYYMMDD_PLA  TRACKER`；`replace_text` 換掉
     八格文字；`delete_element` 刪掉**今日沒有**的空域（每個 5 形狀＋1 標籤）
  5. commit transaction → `move-item-to-folder` 搬進資料夾 → 把設計連結給使用者
- **母版頂部有一張半透明航機照＋一張漸層遮罩（2026-08-07 加）**，兩者都不參與每日流程，
  別動也別刪：照片 `PBrY48DlSrkTrB5h-LBXP7J8g5Y5wZSrW`（F-16＋F-35，使用者要表達美日共同防衛，
  **不可壓暗機身**）；遮罩 `PBrY48DlSrkTrB5h-LBpX25hdgp4MrLdT`（Canva 素材 `MAHRmT5eVak`，
  y 540→690、1092×150）負責讓照片下緣淡入地圖底色。圖層順序**必須是**底色→照片→遮罩→地圖→文字，
  順序跑掉的症狀是數字被壓暗或漸層失效。教訓兩條：(1) Canva API **沒有漸層填色**，用純色窄帶疊
  出來的假漸層在照片上會看成百葉窗（使用者退件），要漸層就自製 alpha PNG 匯進來；
  (2) `insert_fill` 匯入的圖預設用「填滿」裁切，長寬比不符時只會露出中間一小段，
  插完必須用 `crop_media` 把 imageBox 設成和元素同尺寸。
- 只有在母版真的缺某個空域時才需要插入（`zones[].shapes` / `label`）。`add_text` 插出來的
  標籤是黑色 16px 左對齊，**插完必須再補一次 `format_text`**（黃 `#F5C842`／25px／
  bold／center），否則深色底上等於看不見。插入的形狀不會有動畫，要回報使用者。
- **空域判斷不要另外寫一份**：`make_canva_ops.py` 直接 import `build_site.zones_from_special`。
  公告實際寫的是「西南空域」而非「西南部」，自己重寫過一次就漏判（2026-08-05 踩過）。
- **`data/canva_zone_ops.json`＝整套作業資料**（2026-08-06 加）：母版／資料夾 id、八格
  文字的 locator id、六空域的 `master_shape_ids`、插入指令、標籤格式，用法寫在 `_readme`。
  母版與其複製品的 locator id 相同（2026-08-06 實測），所以這些 id 對每天的複製版都有效。
  有了它，**沒有本機 repo／不能跑 Python 的環境**（手機、雲端、另一台電腦）也能做圖卡：
  當日數字與空域從 https://pla-tracker.skyfaring.net 首頁讀得到。
  **套用前必須先核對地圖元素的 top/left/width/height 等於表裡的 `map_element`**；
  不等於代表使用者移動過地圖，停手改跑腳本重算，並用 `--atlas` 重生這張表
  （指令在 `_regenerate` 欄）。同理，某個 master id 找不到＝該元素被刪掉重畫過，
  改用座標比對認人並回報使用者這張表該更新。
- **自動排程**（2026-08-06 起）：本機排程任務 `pla-tracker-canva-daily`，每天台灣時間
  14:40 跑（CI 的 12:00／14:00 抓取班之後）。它是冪等的——資料夾裡已有當日設計就跳過。
  排程只在**這台主機開機時**會跑；漏跑了就在任何一台有這個 repo 的機器上說
  「做今天的 canva」，流程一模一樣。**排程任務本身不在版控裡**
  （`~/.claude/scheduled-tasks/`），換機器要重建，但作業知識全在本節與對照表裡。
- [2026-08-07] 症狀：排程有觸發（`list_scheduled_tasks` 的 `lastRunAt` 是當天 14:47）、
  資料也讀對了，但資料夾裡沒有當日設計，且沒有任何錯誤通知。根因：使用者全域設定是
  `"defaultMode": "dontAsk"` 且 allow 清單裡**沒有任何 MCP 工具**——互動 session 會跳確認框
  按一下就過，無人值守的排程 session 直接被拒（第一個 Canva 呼叫 `list-folder-items` 就死）。
  規則：Canva 連接器已加進 `.claude/settings.local.json` 的 allow（`mcp__<連接器 id>`，
  該檔被全域 gitignore 擋掉、不進版控，所以換機器要重建）。**若連接器在 claude.ai 被移除重連，
  id 會變、這條 allow 就失效，症狀一樣是靜默失敗**——排程連兩天沒產出就先查
  `~/.claude/projects/E--repos-pla-tracker/*.jsonl` 裡當次執行的權限錯誤，不要先懷疑 Canva 掛了。
- 品牌範本（Brand Template）**不適用**：官方自動填入只能換文字與圖片，換不了形狀。

## API 費用（2026-08-09 查證）

- 付費的只有 CI：`fetch_and_update.py`（Opus）＋`send_daily_email.py`（Sonnet），
  用 GitHub Secrets 的 `ANTHROPIC_API_KEY`（Console 上是 `adam-first-key`）。
  約 $0.085/天、$2.6/月（早退檢查上線後應降到 $0.6/月上下）。
  **互動 session 與排程 session（含 Canva 圖卡）不走這把 key**，算訂閱額度；
  本機沒有 `ANTHROPIC_API_KEY` 環境變數。查帳走 Console → **Cost 頁**（不是 Usage
  頁，後者含快取讀取會高估）→ Group by API key。
- 每次擷取呼叫 ≈ prompt 1,077 字 ＋ 航跡圖 1,180 token（圖固定 794×1115，
  依 `w*h/750` 計）≈ 2,300 token。**航跡圖長邊 1115px < 1568px**，所以升級
  Opus 5（上限 2576px）圖片 token 不會變多，費用不變。
- **改用公告文字取代圖片判讀：評估後不做**（2026-08-09）。文字公告只有 140–160 字，
  含 date／aircraft_total／median_line_cross／ships_total（共艦＋公務船相加）與越線空域，
  但**完全沒有機型詞、活動時間、航跡圖的 ①② 編號**。省的是每次呼叫的一半（不是九成，
  圖片本來就只佔一半），代價是 `aircraft_type` 只能推出 Zero／非 Zero，
  歷史上 23/219 天（Mixed 19、UAV 2、Helicopter 2）會被誤標成 Manned。
  附帶事實：`activity_start`/`activity_end` 全站零引用、全檔只有 12 筆有值
  （最後一筆 2026-05-30），實質是死欄位。
- **升級模型時必做兩件事**（尚未升級）：加 `thinking={"type":"disabled"}`
  （否則 `max_tokens=512` 會被思考吃掉、JSON 被截斷）；取值不可寫死 `content[0]`
  （已於 2026-08-09 改成找第一個 `type=text` 區塊，兩支腳本都改了）。

## 已知歷史事件（查問題時的線索）

- [2026-08-09] 症狀：每天 API 帳單約 10,000 input token，但真正有用的擷取只有一次。
  根因：每天有**五班**會抓到同一則公告（三班 cron ＋ 兩班來源不明的外部
  `workflow_dispatch`，以使用者帳號在 UTC 04:00／06:00 準點觸發，repo 內沒有任何東西
  會 dispatch 它），而 `append_to_csv` 的去重發生在 API 呼叫**之後**，四次是白花的。
  另註：GitHub 的 cron 每天延遲 30–50 分鐘，真正搶到當日公告的往往是那兩班準點
  dispatch。規則：任何「先花錢才判斷要不要用」的流程，把可用純字串／本地資料做的
  判斷提到花錢之前；本例＝`parse_bulletin_end_date()` 先解析公告日期，已在 CSV
  就 `outcome=exists` 早退（解析失敗回空字串照原路徑走，`FORCE_REBUILD=true` 不早退）。

- 2026-08-05：網域遷移 `pla-tracker.pages.dev` → `pla-tracker.skyfaring.net`。
  舊網域由 `functions/_middleware.js` 301 轉走；全站 canonical／og:url／sitemap／
  JSON-LD 改走 `build_site.canon_url()`（去 `.html`，因為 Pages 會把 `/x.html`
  308 到 `/x`）。Search Console：新資源（網址前置字元）靠 `skyfaring.net` 網域
  資源自動驗證、sitemap 已提交；舊資源用 HTML 檔案驗證並於同日送出「變更網址」
  遷移宣告（Google 保留 180 天，**期間不可拆掉 301**）。
  ⚠️ `_middleware.js` 裡的 `GSC_VERIFY_PATH/BODY` 是舊資源的擁有權驗證檔，
  **不可刪**——刪了 Google 會判定驗證失效、遷移宣告一併失效。它不是靜態檔的原因
  寫在該檔註解裡（舊網域雙層轉址會擋掉驗證抓取）。

- 2026-06-18 前：零架次且無航跡圖的日子，fetcher 誤判為「未發布」而漏資料
  （CI 仍 success）。已修（commit 741cff8）：無圖時改讀 `div.maincontent` 公告文字。
- 2026-06-21：SEO 地基（95b84ca）＋媒體引用圖表（51e04e5）上線。
- 2026-07-30：使用者體檢日（2763cc9／ad7a5b2／d21d106）。方法論頁 6 節→4 節；
  清掉內部用語（「站內黃」「口徑說明」「未確認」→「進度未確認」）與一句殘留的
  內部待辦（ATACMS 判讀的「上線前仍需補來源」）；/arsenal/ 卡片牆按交付階段拆成
  圖卡（10）＋緊湊列（11），延宕標籤只掛真延宕者並加進全表狀態欄；首頁近兩週面板
  改堆疊長條。**教訓**：內部語彙與待辦註解會隨字串一路上線，寫使用者可見字串時
  要當成對外文案審一次。
- 2026-07-23：大改版日。(1) 功能 E（PNG 下載/iframe 嵌入、embed 頁）**整組移除**
  （使用者判斷無人引用，b2038a6）；(2) 一句話 SITREP 移到地圖下方、SITREP/月統計
  卡片化、導覽列藥丸化（58b8261/b2038a6）；(3) 嚴重日自動配色上線（ec935b3）；
  (4) `_VER` 改分鐘級＋fetcher exists 路徑真正跳過重建（58b8261/2715450，
  原本 log 說不重建卻照建，配分鐘版本會產生噪音 commit）；(5) 日報信加
  今日/昨日對比＋Threads 草稿（固定兩段式：擾台形式＋國內國防新聞並置）。
- [2026-07-23] 症狀：主對話 commit 單一檔案時，另一個並行 subagent 已 `git rm`
  的刪除被一併帶進 commit。根因：`git add <檔>` 後的 `git commit` 會提交 index
  中**所有**已 stage 內容。規則：多 agent 並行改 repo 時，commit 一律用
  pathspec 限定（`git commit -- <路徑>`）。
- 2026-07-31：功能 F（分享圖卡）上線＝`card.html`，直式 1080×1350、客戶端 canvas
  繪製、一鍵下載 PNG。CI 自動產圖的路線**沒有**採用（要在 runner 裝 CJK 字型，
  違反鐵律 7）；使用者選的是「卡片頁＋下載鈕」。
- 進行中（2026-07-23 啟動）：「美製武器實戰檔案」內容區（/arsenal/，魚叉/愛國者/
  HIMARS 三篇研究稿在 session scratchpad，待使用者審後建頁）；
  pla-tracker × skyfaring 串接計畫（調查報告同 scratchpad）。
