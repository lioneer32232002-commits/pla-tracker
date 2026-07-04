# PLA Tracker — Claude 工作規則

每日追蹤解放軍在台灣周邊軍事活動的靜態網站（https://pla-tracker.pages.dev，
push 到 main 即自動部署）。回覆一律用繁體中文。

## 你的角色

**每日更新已由 GitHub Actions 全自動執行**（每天台灣時間 12:00/14:00/20:00）。
Session 的工作是：開發功能、修 bug、回填資料、SEO/內容。
只有使用者明確提供國防部圖片、或要求補某日資料時，才走下面的手動更新流程。
某日資料缺漏 → 先查 CI 紀錄（`gh run list --workflow daily_update.yml --limit 5`），
不要直接重做。

## 鐵律（違反任何一條都算失敗）

1. `data/records.csv` 只能新增列，禁止修改歷史資料。
2. 驗證未通過禁止 commit。跑腳本一律加 `-X utf8`。
3. 改任何腳本後必須重新 build＋驗證，再一次 commit 全部變更（腳本＋HTML＋version.txt）。
4. 產出 HTML（index/records/monthly/about/embed/sitemap/robots）禁止手改，一律改 `build_site.py`。
5. 禁止留未 push 的 commit。編輯完成即 commit＋push，不需詢問。
   Push：`git push origin HEAD:main`；被拒→`git pull --rebase origin main` 再推（通常是 CI bot 剛推過）。
   **唯一例外**：結構性變更（新頁面、改導覽、改網址結構，見 judgment.md 第 3 節）
   要在**動工前**先問使用者；批准後照常做完即 commit＋push，中途不留懸置 commit。
6. 新增網站頁面必須同步加進 `daily_update.yml` 的 `git add` 白名單，否則線上版停更。
7. 禁止在 build/CI 加入字型或 Pillow 圖表渲染（CI 無 CJK 字型；圖表一律 Chart.js 客戶端）。

## 手動更新流程（備援，每步必做）

1. 視覺辨識圖片 → 新一行寫入 `data/records.csv`
2. `python -X utf8 scripts/validate.py csv` — 失敗即停手修正
3. `python -X utf8 scripts/build_site.py`
4. `python -X utf8 scripts/validate.py html` — 失敗即停手修正
5. Commit 全部變更 → `git push origin HEAD:main`

驗證規則：通過不說話，失敗才回報並阻止 commit。

## CSV 欄位

```
date, aircraft_total, median_line_cross, cross_rate,
aircraft_type, ships_total, activity_start, activity_end, special_event
```

`aircraft_type` ∈ Manned/UAV/Mixed/Zero/Helicopter；
`cross_rate` = cross÷total×100（±1%）；cross ≤ total。

## 路由表（做右欄的事之前，先讀左欄的檔）

| 檔案 | 什麼時候讀 |
|------|-----------|
| `.claude/rules/00-diagnosis.md` | 每個 session 開工前掃一眼（本環境三大坑：大檔讀取、CI 誤解、Windows 陷阱） |
| `.claude/rules/project-reference.md` | 要動 build_site.py／新增頁面／查檔案用途／查 CI 細節／改圖表 |
| `.claude/rules/model-dispatch.md` | 要派 subagent、大量讀檔掃 repo、查網頁、或任務連錯兩次 |
| `.claude/rules/judgment.md` | 不確定「該不該問使用者」「算不算完成」「要不要換方法」時 |
| `.claude/rules/delegation-templates.md` | 撰寫 subagent 派工 prompt 時直接套模板 |
| `.claude/rules/maintenance.md` | 要修改以上任何規則檔、或踩了坑要寫教訓時 |
| `.claude/rules/letter.md` | 接手大型／跨 session 工作前 |

規則檔互相矛盾時：CLAUDE.md 鐵律 > 各規則檔 > 你的預設習慣。發現矛盾就照
`maintenance.md` 修掉並告知使用者。
