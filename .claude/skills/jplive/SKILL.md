---
name: jplive
description: 追蹤日本 Live／演唱會資訊（歌手、聲優、偶像、團體、祭典、作品企劃），以關注清單每日增量查詢，結果存成可匯入 Android app 的 JSON 資料庫並輸出 Markdown 報告。當使用者詢問日本 Live、售票、巡演，或要執行／更新 jplive 每日追蹤時使用。
---

# jplive：日本 Live 追蹤與資料庫

使用者是為了「去日本看 Live」而追蹤，資料會餵給自己的 Android app。所以：
- 只關心**日本國內**的場次（`focus_country: JP`，見 `data/config.json`）。海外場次不記錄。
- 重點是日期、場館、開場／開演時間、票務階段與購買限制。
- 資料必須**穩定、可驗證、可合併**，寧可少填也不要亂填。

## 兩種模式

### A. 單次查詢
使用者給「藝人／活動名稱」，通常也會給時間範圍（例如「2027 年上半」）。
**不支援依地點或日期反查**（例如「11 月東京有什麼 Live」）；遇到這種問法，說明目前不支援，並建議改用藝人名稱查詢。

流程：Step 1–4（見下）。

### B. 每日追蹤（預設的主要用法）
對 `data/artists.json` 中 `watching: true` 的藝人，每天做一次增量查詢，更新資料庫並輸出報告。
完整步驟見 `references/daily-run.md`，**執行每日追蹤前必須先讀它**。

## 核心流程（兩種模式共用）

### Step 1：辨識對象與類型
依 `references/categories.md` 判斷屬於 solo／group／festival／franchise（可複選）。用 `data/artists.json` 的 `aliases` 比對名稱；有歧義且無法確定時才問使用者。
注意：`related_ids` 指向有關聯的對象（例如 YOASOBI 與成員幾田りら），兩者都要查，但活動分開記錄。

### Step 2：搜尋
- 一律用 WebSearch／WebFetch 即時查，不可憑記憶回答日期或場地。
- 以日文原名為主，再補英文與繁中譯名；關鍵字見 `references/sources.md`。
- 來源優先順序見 `references/sources.md`。官方優先，整合站只能當線索。
- **抓取前先問 `scripts/fetch_log.py`**（見 daily-run.md），已抓過的詳細頁不重抓。
- X 常常抓不到；抓不到不等於沒有。

### Step 3：驗證與取捨
- 日期、場地、票務至少要有一個官方來源，才能把 `confidence` 設為 `official`。
- 來源衝突時，以官方最新公告為準，並在 `notes` 記錄衝突。
- 查不到就是查不到，**絕不編造**。
- 日期時間用 ISO 8601（JST，`+09:00`）；只知道日期時，時間欄位設 `null`，不要填 `00:00`。
- 購買限制（如 FC 會員限定、需日本國內電話或地址）**只有來源明確寫出時才填** `buyer_restriction`，否則留 `null`。

### Step 4：寫入資料庫
1. 讀取 `data/live_events.json`，以 `id` 合併：不存在就新增，存在就更新。
2. 新增時設 `first_seen_at`；**內容真的有變**（日期、場地、票務、狀態、陣容等）才更新 `last_changed_at`；每次查證都更新 `last_verified_at`。
3. 絕不刪除。取消用 `cancelled`、延期用 `postponed`、過期用 `ended`。
4. 新藝人補進 `data/artists.json`（`watching` 預設 `false`，只有使用者要求才設 `true`）。
5. 檔案一律 UTF-8（無 BOM）、縮排 2 空格、保留日文字元。
6. 執行 `python scripts/validate.py data/live_events.json`，通過才算完成。

### Step 5：輸出
- 單次查詢：先用對話簡短回覆，並依 `references/output-format.md` 產出報告檔。
- 每日追蹤：執行 `python scripts/report.py`，報告寫入 `reports/jplive-YYYY-MM-DD.md`。報告由腳本產生，格式固定，不要手寫覆蓋。

## ID 規則
`id` 建立後**永不更改**（Android 用它當主鍵）。格式 `{最早場次日期YYYYMMDD}-{藝人或活動的小寫英文 slug}`，例：`20270320-sample-artist-hall-tour`。巡演的每一場是 `performance`，掛在同一個 event 下。

## 守則
- 只收錄公開資訊，不收錄轉售票務，不提供搶票腳本或繞過售票限制的方法。
- `examples/` 內全部是虛構資料，不可寫進真實資料庫。
- 若 WebSearch／WebFetch 拒絕某網站，換來源或請使用者自行開啟，不要繞過。

## 檔案一覽
- `references/daily-run.md`：每日追蹤步驟與排程用提示詞
- `references/categories.md`：四種類型的辨識與搜尋策略
- `references/sources.md`：來源優先順序、日文關鍵字
- `references/schema.md`：資料庫欄位說明與 Android 對應
- `references/output-format.md`：報告格式
- `schema/live_event.schema.json`：JSON Schema
- `scripts/validate.py`：資料驗證
- `scripts/fetch_log.py`：抓取紀錄（避免重複抓取）
- `scripts/report.py`：產生 Markdown 報告
- `data/live_events.json`：活動資料庫
- `data/artists.json`：藝人主檔與關注清單
- `data/config.json`：設定
- `data/fetch_log.json`：抓取紀錄
- `examples/`：虛構範例
