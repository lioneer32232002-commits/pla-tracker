# Canva 每日圖卡（2026-08-05 起，使用者要求）

> 自 project-reference.md 拆出（2026-08-09），內容未改。使用者說「做今天的 canva／
> 圖卡／貼文圖」時讀這份；流程與禁忌都在這裡，不要自己發明。

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
- **自動排程＝雲端主班＋本機備援班**（2026-08-09 改制）：
  - **兩班都在雲端**：claude.ai 的 routine `trig_01RbV4ojgTax7DoEUEy2euWW`，
    cron `40 6,8 * * *` UTC＝**台灣 14:40（主班）與 16:40（備援班）**，
    model sonnet-5，掛 Canva 連接器（`connector_uuid` df40f712-07ae-46d1-9ef9-8ea2809c16ff、
    url `https://mcp.canva.com/mcp`）。**不依賴任何一台本機開機**。管理頁：
    https://claude.ai/code/routines/trig_01RbV4ojgTax7DoEUEy2euWW
    ⚠️ 雲端環境**沒預裝 pandas**，所以 prompt 第 0 步是 `pip install -r requirements.txt`
    （2026-08-09 實測：不裝的話 `make_canva_ops.py` 在 import 就 ModuleNotFoundError）。
  - **本機排程任務 `pla-tracker-canva-daily` 已於 2026-08-09 停用**（`enabled: false`），
    因為使用者無法保證假日／公司那台會開機，備援放在本機等於備援本身不可靠。
    任務檔保留供**手動**觸發（說「做今天的 canva」），不再自動跑。
  - **兩班不會做出兩份**：開工前都做冪等檢查（`list-folder-items` 查資料夾裡有沒有
    當日標題），且相隔兩小時、不會同時開跑。正常日子 16:40 那班查到已存在就直接結束。
  - **怎麼分辨是哪一班做的**：看設計的 `created_at`——約 14:4x＝主班，約 16:4x＝備援班
    （備援班真的動手＝主班那天失敗了，去 routine 頁看原因）。
  - 備援班的存在理由：GitHub cron 遲到嚴重時（例如 2026-08-03 第一班拖到台灣 14:49）
    資料會晚於 14:40 才進版，主班會撲空。
  - **claude.ai 的連接器清單有時會回報「No available MCP connectors found」**——那是清單
    沒抓到，不代表不能用。手動在 routine 的 `mcp_connections` 指定 uuid＋url 就通了
    （2026-08-09 實測成功列出資料夾內容）。
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

