# 快速診斷：本環境三大風險與修法

> 寫於 2026-07-04（Fable 5 制度建立 session）。這份是後面所有制度檔的依據。
> 讀者：未來在此專案工作的任何模型。每條都有「訊號 → 修法」，照做即可。

---

## 風險一（最漏 token）：把大檔案整份讀進主對話

**事實**：`scripts/build_site.py` 有 2011 行；`index.html` 等 HTML 是 build 產物、內含大量
inline JS；`data/records.csv` 已 204 行且每天增長。把這些整份 Read 進主對話，
一次就吃掉數萬 token，而且產出的 HTML 下次 build 就變了，讀了也白讀。

**訊號**：你正要對超過 500 行的檔案做無 offset/limit 的 Read；或你想「先看看整個
HTML 長怎樣」。

**修法（依序選第一個適用的）**：
1. 產出 HTML **永遠不要整份讀**。要確認輸出正確，跑 `python -X utf8 scripts/validate.py html`；
   要找特定片段，用 Grep 搜字串再 Read 該區段（offset+limit）。
2. `data/records.csv` 只讀尾端：`Read` 加 `offset`（總行數 − 30）。要統計全檔就寫個小
   Python 腳本跑，只把結果帶回對話。
3. `build_site.py` 先 Grep 找到目標函式，再 Read 該函式前後 ~80 行。需要理解全貌時，
   派 Explore subagent 去讀，只回摘要與 檔案:行號（見 [model-dispatch.md](model-dispatch.md)）。

---

## 風險二（最容易失焦）：誤解「誰在做每日更新」

**事實**：每日更新自 2026-06-22 起由 GitHub Actions 全自動執行
（`.github/workflows/daily_update.yml`：台灣時間 12:00/14:00 抓取、20:00 最終檢查，
`fetch_and_update.py` 用 Claude API 讀國防部圖片或公告文字 → validate → commit → 寄信）。
但舊版 CLAUDE.md 把「使用者提供圖片 → 手動輸入」寫成主流程，弱模型會誤以為
每個 session 都要做每日更新，或不知道資料缺漏時該去查 CI 而不是重做一遍。

**訊號**：使用者沒提供圖片你卻想開始「每日更新流程」；或某日資料缺漏時你想直接手動補
而沒先查 GitHub Actions 的執行紀錄。

**修法**：
1. Session 的預設角色是**開發、修復、回填、內容功能**，不是每日更新。只有使用者
   明確提供國防部圖片或說「補某日資料」時才走手動流程。
2. 某日資料缺漏 → 先查 CI：`gh run list --workflow daily_update.yml --limit 5`，
   看 log 裡是「提取結果：…」（有抓到）還是「今日公告尚未發布」（真的沒發布）。
   fetcher 的零架次/無圖片日已有文字備援路徑（2026-06-18 修，commit 741cff8）。
3. 新增網站頁面時，**必須**同步把新檔加進 `daily_update.yml` 的 `git add` 白名單，
   否則 CI 每日更新不會 commit 它 → 線上版該頁面停更。這是本專案最隱蔽的坑
   （CI 顯示 success，但頁面悄悄過期）。

---

## 風險三（最容易出錯）：Windows/編碼/推送的環境陷阱

**事實**：本機是 Windows 11 + PowerShell 5.1，主控台預設 cp950；repo 放在 OneDrive
同步資料夾且路徑含中文；CI bot 每天最多三班自動 commit 到 main。

**訊號與修法**：
1. Python 輸出出現 `UnicodeEncodeError` 或亂碼是 cp950 主控台造成的 → 本專案跑
   任何 Python 腳本一律加 `-X utf8`，沒有例外，不用判斷。
2. `git push` 被拒（rejected / fetch first）→ 這通常是 CI bot 剛推了每日更新，不是錯誤。
   照規則：`git pull --rebase origin main` 再 `git push origin HEAD:main`。**不要** force push。
3. PowerShell 5.1 沒有 `&&`、`??`、三元運算子；寫檔預設 UTF-16。跨平台腳本一律用
   Bash 工具或 Python 執行，別在 PowerShell 裡拼複雜指令。
4. OneDrive 偶爾鎖檔（`index.lock` 或寫檔失敗）→ 等幾秒重試一次；連續失敗就明確
   回報使用者是 OneDrive 同步干擾，不要換路徑亂寫。
5. 改了 `build_site.py` 等腳本卻沒重新 build 就 commit HTML → 腳本與產物不同步。
   鐵律：改腳本 → `python -X utf8 scripts/build_site.py` → `python -X utf8 scripts/validate.py html`
   → 一次 commit 全部（腳本＋HTML＋version.txt）。

---

## 這套修法的極限（誠實條款）

拆解、驗證、checklist 補得了**執行品質**；補不了**品味與模糊判斷**——
例如 SITREP 的措辭語感、品牌視覺、部落格/Threads 貼文的編輯取向。遇到這類問題：
不要硬做，給 2–3 個具體選項附取捨，讓使用者選（見 [judgment.md](judgment.md) 第 3 節）。
