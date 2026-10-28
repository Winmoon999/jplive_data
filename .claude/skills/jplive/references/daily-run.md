# 每日追蹤流程

目標：每天一次，對關注清單做**增量**查詢，只處理新資訊，避免重複抓取。

## 「已抓過就不再抓」的實際規則

使用者要求抓過的就不要再抓。但如果連藝人官網的 Live 一覽頁都不再看，就永遠發現不了新活動。所以分成兩種頁面：

| 種類 | 例子 | 規則 |
|---|---|---|
| `detail` | 單一活動的公告頁、售票頁 | 抓過就不再抓 |
| `index` | 官網 Live 一覽、新聞列表、搜尋結果 | 每個日本日曆日最多抓一次（用來發現新活動） |

例外：活動仍有「待確認」資訊（`lineup_complete=false`、票務時間未公布、或有尚未開賣的階段）時，詳細頁可依 `recheck_pending_days`（預設 7 天）複查一次。設為 `0` 即完全不複查。
代價：已抓過且被視為「已確定」的活動，之後若臨時變更或取消可能漏掉。這是依使用者要求做的取捨；如果想降低風險，把 `recheck_pending_days` 調小，或對近期活動手動查詢。

## 步驟

1. 讀 `data/config.json`、`data/artists.json`、`data/live_events.json`。
2. 取得今天要檢查的藝人：`python scripts/fetch_log.py artist-due`。輸出為空就代表今天都檢查過了，直接做第 7 步。
3. 對每位藝人（以及其 `related_ids` 的對象）：
   1. 找出該藝人的 `index` 頁（官網 Live 頁、官方新聞、搜尋結果）。
   2. 對每個網址先問：`python scripts/fetch_log.py check <URL> --kind index`。回覆 `SKIP` 就不抓；`FETCH` 才抓。
   3. 從一覽頁找出活動連結。每個活動的 `detail` 網址同樣先問：`python scripts/fetch_log.py check <URL> --kind detail`；若該活動在資料庫中屬於待確認狀態，加上 `--pending`。
   4. 抓取後立刻記錄：`python scripts/fetch_log.py mark <URL> --kind <index|detail> --outcome <ok|empty|error> --artist <artist_id>`。抓失敗用 `error`（24 小時後才會重試），頁面沒有內容用 `empty`。
   5. 依 SKILL.md 的 Step 3、Step 4 驗證並合併進資料庫。
   6. 完成該藝人後：`python scripts/fetch_log.py artist-done <artist_id>`。
4. 只處理 `country == JP` 的場次，海外場次略過。
5. 執行 `python scripts/validate.py data/live_events.json`，有錯誤先修正。
6. 把已過期的活動（所有場次日期都早於今天）狀態改為 `ended`；更新頂層 `updated_at`。
7. 執行 `python scripts/report.py`，報告寫入 `reports/`。
8. 回覆一段簡短摘要：本次新增幾筆、變更幾筆、哪些藝人沒有新資訊、哪些來源抓取失敗。

## 失敗處理

- 某個藝人查詢失敗：該藝人**不要**執行 `artist-done`，這樣隔次執行會再試；其他藝人照常處理。
- 全部來源都抓不到：不要輸出空殼資料，報告中註明「今日來源無法讀取」。
- 不要因為單次沒查到就把活動改成取消；取消必須有官方公告。

## 排程用提示詞（建立排程任務時使用）

> 使用 jplive skill 執行每日追蹤：先閱讀 references/daily-run.md，依步驟對關注清單做增量查詢、更新 data/live_events.json、驗證並產生報告。只處理日本國內場次，不要編造資料，抓取前一律先用 scripts/fetch_log.py 檢查。最後回報新增、變更與失敗的來源。

注意：排程任務需要能存取 jplive 資料夾（也就是要在連結到使用者電腦、且電腦開機並開著 Claude 桌面版時才跑得到）。
