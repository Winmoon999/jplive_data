# jplive_data

羅列日本歌手演唱會資料。這個儲存庫同時是 **jplive skill** 與它產生的**資料庫**。

## 結構

- `.claude/skills/jplive/`：Claude skill（搜尋流程、驗證腳本、資料格式）
  - `data/live_events.json`：活動資料庫
  - `data/artists.json`：藝人主檔
  - `data/fetch_log.json`：抓取紀錄（避免重複抓取）
  - `reports/`：每日報告
- 資料格式說明：`.claude/skills/jplive/references/schema.md`

## 資料原則

- 只收錄日本國內場次，來源為官方網站與官方公告。
- 售票網只存連結，不自動讀取其內容。
- 每筆活動都帶來源連結、可信度與最後查證時間；請以官方公告為準。
- 資料更新先進 `data-update` 分支，經檢查後再合併到 `main`。

## 狀態

初始版本：資料庫尚為空，等待第一次試跑。
