# PLA Tracker 英文版施工計畫

> 給執行 session 的說明：本計畫由另一個 session 評估後產出。
> 執行前先讀完整份計畫與本專案 CLAUDE.md，兩者衝突時以 CLAUDE.md 為準。
> 依 Phase 順序執行，每個 Phase 結束都要通過驗收條件才能進下一個。

## 目標

讓 build_site.py 在產生現有中文頁面的同時，自動產出英文版三頁
（`en/index.html`、`en/monthly.html`、`en/records.html`），
並在每日 GitHub Actions 自動更新時跟著更新，日常維護工作量增加為零。
英文版同時是電子報訂閱的入口（漏斗），不只是翻譯。

## 架構原則（不可違反）

1. 英文頁面一律由 `build_site.py` 產生，禁止手寫或手改任何 HTML 檔
2. `data/records.csv` 完全不動，不新增欄位、不改歷史資料
3. 中文頁面輸出必須與改版前一致（驗收方式見 Phase 1）
4. 翻譯採規則式對照表（deterministic），不在 build 流程呼叫 LLM API

---

## Phase 0：前置（使用者手動，不是 Claude 的工作）

- [ ] 使用者決定英文版首頁定位句（一句話說明與 PLATracker 等既有英文追蹤站的差異，
      例如強調台灣在地視角、整合海巡與漢光動態）。未定稿前先用 placeholder。
- [ ] 使用者註冊 Buttondown（或 Substack）帳號，取得 embed 訂閱表單的 HTML 片段。
      未提供前先在頁面上放注釋掉的佔位區塊。

Phase 0 未完成不阻擋 Phase 1–3 施工。

---

## Phase 1：build_site.py 雙語化（核心工程）

### 做法

1. 改造前先存基準：`python scripts/build_site.py` 之後
   `cp index.html /tmp/base_index.html`（三頁都存），作為回歸比對基準。
2. 在 `build_site.py` 加一個字串表結構，例如：
   ```python
   STRINGS = {
       'zh': {'site_title': '...', 'nav_records': '每日紀錄', ...},
       'en': {'site_title': 'PLA Activity Tracker — Taiwan Strait', ...},
   }
   ```
   把現有模板裡寫死的中文 UI 字串全部抽進 `zh` 表，逐一補上 `en` 對應。
3. 主流程改成迴圈：`for lang in ('zh', 'en')`，zh 輸出到現有路徑（檔名不變），
   en 輸出到 `en/` 子目錄。
4. 寫 `translate_special_event(text)` 規則式翻譯函式，處理 CSV 的
   `special_event` 中文自由文字。已知的固定模式：
   - `中共空飄氣球計偵獲N顆` → `N PRC surveillance balloon(s) detected`
     （注意原文常帶 `三、`/`四、` 的國防部條目編號前綴與換行，要先清掉）
   - `越線：{空域列表}` → `Median line crossings: {regions} airspace`
     - 區域對照：北部 northern、中部 central、西南 southwestern、
       南部 southern、東部 eastern；頓號/及/、 連接 → 逗號 + and
   - 空字串 → 空字串
   - **無法匹配的字串：原樣保留中文並在 build 輸出 warning**（不可默默吞掉），
     方便日後補規則。
5. 日期格式：en 版用 `Jan 15` / `2026-01-15` 等英文慣例，不用 `1/15` 中式簡寫。
6. `aircraft_type` 欄位值（manned/uav/mixed/zero/helicopter）的顯示翻譯：
   Manned aircraft / UAV / Mixed / No activity / Helicopter。
7. SITREP 區塊（index 首頁）：找出它在 build_site.py 裡的產生邏輯，
   同樣模板雙語化。若 SITREP 含 LLM 產生的中文長文，en 版先放
   數據摘要（結構化句型，由數字填模板），不即時翻譯長文。
8. 語言切換：兩版頁面的 top bar 各加一個切換連結
   （zh 頁 → `/en/...`，en 頁 → `/../...`，用相對路徑，注意 en/ 子目錄層級，
   css/favicon 引用路徑也要跟著對，建議改用絕對路徑 `/style.css`）。
9. `<html lang>`：zh 頁 `zh-Hant`，en 頁 `en`。
   兩版都加 hreflang alternate `<link>` 互指。

### 驗收條件

- [ ] `python scripts/build_site.py` 成功，產出 `en/index.html`、
      `en/monthly.html`、`en/records.html`
- [ ] 中文三頁與基準檔 diff 一致（若有差異，只允許 hreflang/語言切換等
      本計畫明列的新增項，逐行確認）
- [ ] `python -X utf8 scripts/validate.py html` 通過
- [ ] en 頁面肉眼檢查：無殘留中文（special_event 規則未覆蓋者除外，
      且 build log 有對應 warning）、無破版、語言切換連結雙向可用
- [ ] 測試 special_event 翻譯函式：對 `data/records.csv` 全部 182+ 行跑一遍，
      列出無法匹配的字串清單，能匹配率應 > 95%

---

## Phase 2：validate.py 擴充

1. HTML 驗證納入 `en/` 三頁（檔案存在、結構檢查比照中文版）
2. 新增檢查：en 頁面的 `<html lang="en">`、hreflang 標籤存在
3. 驗收：故意刪掉 `en/index.html` 再跑 validate 應該要報錯（測完還原）

---

## Phase 3：自動化管線接上（最容易漏的一步）

1. **改 `.github/workflows/daily_update.yml` 的 commit 步驟**：
   `git add` 白名單目前列死了檔案清單，必須加上 `en/`
   （順便確認 `monthly.html` 是否也該在白名單裡，目前似乎缺漏，
   若確認是缺漏一併補上）
2. 本機完整跑一次：build → validate → commit（中英所有變更 + version.txt）→ push
3. push 後用 `gh run watch` 或到 Actions 頁確認下一次排程班次成功，
   且 bot 的 commit 有包含 `en/` 檔案
4. 確認部署平台（Cloudflare Pages 或 GitHub Pages）上 `/en/` 路徑可訪問

### 驗收條件

- [ ] 隔天（或手動 workflow_dispatch 觸發）bot 自動更新後，
      線上 `/en/index.html` 的數據日期與中文版同步

---

## Phase 4：訂閱入口與 SEO（漏斗）

1. en 三頁與中文三頁都加 Buttondown/Substack embed 訂閱區塊
   （Phase 0 未提供 embed code 前，先放隱藏的佔位 div）
2. en 版 SEO：英文 `<title>`、meta description、Open Graph 標籤
   （title 建議含 "PLA Taiwan Strait activity tracker" 等搜尋詞）
3. 產生 `sitemap.xml`（中英六頁）與 `robots.txt`（由 build_site.py 產生）
4. 加 Cloudflare Web Analytics beacon（中英都加）。
   注意：使用者的三站流量儀表板還缺 pla-tracker 的 site_tag，
   拿到 beacon token 後回報給使用者，讓另一個 session 補進 traffic-dashboard

---

## Phase 5：完工檢查

- [ ] CLAUDE.md 更新：把「英文版由 build 自動產生、禁止手改 en/ HTML、
      新增 special_event 翻譯規則時要跑全量匹配測試」寫進工作規則
- [ ] 全流程演練一次每日更新（模擬新增一筆資料 → build → validate →
      確認中英同步），結束後還原測試資料（CSV 禁改歷史，測試列要刪乾淨）
- [ ] 本計畫檔案任務完成後可刪除或移入 docs/

## 已知風險備忘

- workflow git add 白名單漏加 en/ → 英文版永遠停更（Phase 3 第 1 點）
- en/ 子目錄的相對路徑（css、favicon、返回首頁連結）是最常見的破版來源
- special_event 未來出現新句型（如聯合戰備警巡的新措辭）時，
  規則表要補，warning 機制是安全網
- 不要為了英文版「順手重構」build_site.py 的其他部分，中文版輸出不變是硬約束
