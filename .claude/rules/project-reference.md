# 專案參考資料（需要時才讀，不必每次載入）

> 本檔存放 CLAUDE.md 抽出的細節。改了架構性事實（新頁面、新腳本、部署方式變更）
> 時要同步更新本檔，格式見 [maintenance.md](maintenance.md)。

## 系統全貌

- **產品**：每日追蹤解放軍在台灣周邊軍事活動的靜態網站。資料來源＝中華民國國防部
  每日發布的航跡圖／公告文字。發布管道：https://pla-tracker.pages.dev（Cloudflare
  Pages，push 到 main 即自動部署）、Threads、部落格 https://yi-tienpan.blogspot.com。
  屬 Skyfaring 作品集（hub: https://skyfaring.pages.dev/）。
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
| `index.html` | 首頁（總覽＋SITREP＋一句話文字 SITREP） |
| `records.html` / `monthly.html` | 每日紀錄頁／月度頁 |
| `about.html` / `en/about.html` | 方法論頁（build 產生，每日更新資料區間/筆數） |
| `embed/*.html` / `en/embed/*.html` | 媒體引用圖表頁（build 產生、noindex、供 iframe 嵌入） |
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

- 深色背景：`#1e2224`
- 軍機顏色：黃（當日 `#f5c842`，其他 `#8a7020`）
- 艦艇顏色：紅（當日 `#e05555`，其他 `#7a2a2a`）
- 當日長條永遠高亮；圖表字體由 Chart.js options 的字級設定控制（要改先在
  build_site.py Grep `font` 定位，不要憑記憶找函式名）
- 圖表全程 Chart.js 瀏覽器端渲染。**鐵律：禁止為圖表在 build/CI 加入字型或
  Pillow 渲染**（CI 是 ubuntu、無 CJK 字型；2026-06-21 的功能 E 就因此改走
  客戶端 PNG 匯出，這是所有未來圖表功能的範本）

## SEO 資產規則

- 所有 `<head>` meta、canonical、hreflang、OG/Twitter 卡、JSON-LD、sitemap、robots
  一律由 `build_site.py` 產生，**禁止手改任何產出 HTML**。
- OG 分享圖 `og.png`/`og-en.png` 是靜態檔，只有改品牌視覺才本機重跑
  `python -X utf8 scripts/make_og_image.py`。
- 首頁圖表工具列提供高解析 PNG 下載＋iframe 嵌入碼（客戶端渲染）。

## 新增頁面 checklist（每一項都要做）

1. 在 `build_site.py` 加產生邏輯（含 meta/canonical/hreflang/sitemap 條目）
2. 在 `validate.py` 加對應檢查
3. **把新檔案路徑加進 `.github/workflows/daily_update.yml` 的 `git add` 白名單**
   （漏了＝CI 不 commit 它＝線上版停更，且 CI 仍顯示 success，極難發現。
   `en/` 已涵蓋其下所有英文頁）
4. build → validate → commit 全部檔案 → push

## 已知歷史事件（查問題時的線索）

- 2026-06-18 前：零架次且無航跡圖的日子，fetcher 誤判為「未發布」而漏資料
  （CI 仍 success）。已修（commit 741cff8）：無圖時改讀 `div.maincontent` 公告文字。
- 2026-06-21：SEO 地基（95b84ca）＋媒體引用圖表（51e04e5）上線。
- 待辦（使用者未催）：功能 F＝每日自動社群卡圖（1200×675）。難點是 CI 無 CJK
  字型；方向建議延續客戶端渲染，不要在 build 塞字型/Pillow。
