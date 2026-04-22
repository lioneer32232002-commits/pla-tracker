# PLA Tracker — Claude 工作規則

## 專案說明

每日追蹤中共解放軍在台灣周邊的軍事活動。資料來源為中華民國國防部每日發布圖片。
用途：發布於 Threads 與部落格 https://yi-tienpan.blogspot.com

---

## 每日更新流程（每步都要做，不能跳）

1. 使用者提供國防部圖片 → 用視覺辨識擷取欄位
2. 將新一行資料寫入 `data/records.csv`（只能新增，不能修改歷史資料）
3. 驗證 CSV：`python -X utf8 scripts/validate.py csv`
   - 有錯誤 → 立刻停手修正，不得繼續
4. 重新建置網站：`python scripts/build_site.py`
5. 驗證 HTML：`python -X utf8 scripts/validate.py html`
   - 有錯誤 → 立刻停手修正，不得繼續
6. Commit 所有變更檔案 → `git push origin HEAD:main`

**驗證規則：silent on pass（通過不說話），失敗才回報並阻止 commit。**

---

## Git 規則

- 每次編輯或更新資料後，立刻 commit + push，不需詢問使用者
- 不需要確認，直接執行
- Push 指令：`git push origin HEAD:main`
- 若 push 被拒（遠端有新 commit）：先 `git pull --rebase origin main`，再 push

---

## 編輯腳本後的規則

- 改完任何腳本（`build_site.py` 等）後，必須先執行 `python scripts/build_site.py` 重新產生 HTML
- 再執行 `python -X utf8 scripts/validate.py html` 確認輸出正確
- 最後才 commit，且要一次 commit 所有變更的檔案（腳本 + HTML + version.txt）

---

## 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `data/records.csv` | 主資料（只能新增，禁止修改歷史） |
| `scripts/build_site.py` | 從 CSV 產生全部 HTML 頁面 |
| `scripts/validate.py` | 兩段式驗證（CSV 資料 + HTML 結構） |
| `index.html` | 首頁（總覽 + SITREP） |
| `records.html` | 每日紀錄頁 |
| `version.txt` | build 時間戳，build 後必定更新 |

---

## CSV 欄位說明

```
date, aircraft_total, median_line_cross, cross_rate,
aircraft_type, ships_total, activity_start, activity_end, special_event
```

- `aircraft_type` 合法值：`Manned` / `UAV` / `Mixed` / `Zero` / `Helicopter`
- `cross_rate` = median_line_cross ÷ aircraft_total × 100（允許 ±1% 誤差）
- `median_line_cross` 不能大於 `aircraft_total`

---

## 圖表與設計規格

- 深色背景：`#1e2224`
- 軍機顏色：黃色（當日 `#f5c842`，其他 `#8a7020`）
- 艦艇顏色：紅色（當日 `#e05555`，其他 `#7a2a2a`）
- 當日長條永遠高亮
- 字體大小依月份天數自動縮放（`adaptive_fs()`）

---

## 禁止事項

- 禁止修改 `data/records.csv` 的歷史資料
- 禁止在驗證未通過的情況下 commit
- 禁止改完腳本後沒有重新 build 就 commit HTML
- 禁止留下未 push 的 commit
