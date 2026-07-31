# 專案參考資料（需要時才讀，不必每次載入）

> 本檔存放 CLAUDE.md 抽出的細節。改了架構性事實（新頁面、新腳本、部署方式變更）
> 時要同步更新本檔，格式見 [maintenance.md](maintenance.md)。

## 系統全貌

- **產品**：每日追蹤解放軍在台灣周邊軍事活動的靜態網站。資料來源＝中華民國國防部
  每日發布的航跡圖／公告文字。發布管道：https://pla-tracker.pages.dev（Cloudflare
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
| `sitemap.xml` / `robots.txt` | build 產生；基準網址 = `https://pla-tracker.pages.dev` |
| `version.txt` | build 時間戳，每次 build 必變 |

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
- **空域漸層的做法有講究**（2026-07-31 使用者退件重做）：首頁 Leaflet 那套「多層
  縮放多邊形疊加」直接搬到 1080 寬的圖卡上，硬邊會變成看得見的階梯色塊；全部上
  模糊又會糊成沒有形狀的光斑。現行做法＝最外層硬邊（定範圍）＋內部八層縮放疊加後
  套 `ctx.filter='blur(16px)'`；12 浬帶與離島光暈同理用 blur(13px)。`ctx.filter`
  不支援時（舊 Safari）自動退回無模糊的分層版，不會壞掉，只是階梯感回來。
- 版面刻意留白、資訊只留三個當日數字＋一行空域＋一行月累計：早期版本把 pill 框、
  ▲▼ 說明、月統計面板全塞進去，使用者的評語是「太醜、資訊太多」。要加東西前先想
  這張圖是在手機動態牆上被滑過去的。
- 圖卡固定深色，不跟隨嚴重日主題（分享出去的圖在各 App 深色底上都要能看）。
- 已知落差：地圖只畫得出北部／西南／東部／東北四個空域框，公告裡的「中部」「南部」
  沒有對應多邊形（首頁地圖同樣沒有）。摘要 pill 用的是公告原文，所以文字會提到
  地圖上沒有的空域。要補就得先定出可查證的範圍，別憑印象畫。

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

## 已知歷史事件（查問題時的線索）

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
