# 資料格式規格（app 端定義，skill 端遵循）

狀態：**草案 v1.1（2026-10-29）**，由實際整理出的資料（ReoNa、YOASOBI 等）反推。skill 端有補充或不同意見，請在留言板討論串 T004 提出；定案後才改 schema 與 validate.py。
決定權：**格式由 app 端決定**（使用者 2026-10-29 決議）；skill 提出補充，app 端與使用者確認後採用。

## 1. 原則
1. 一個「活動」（event）＝一個巡演／祭典／單場公演；底下有多個「場次」（performance）。app 月曆以**場次**為單位顯示。
2. 所有日期時間為日本時間（JST, +09:00）。不知道就 `null`，**不可用 00:00 充數**。
3. 給人看的文字放 `notes`；**app 不解析 `notes`**。凡是 app 要用的資訊，一律用結構化欄位。
4. 只存事實與來源連結，不轉載官方網站內文。
5. 加欄位用「可選欄位」方式，不影響舊資料；刪欄位或改意義才升 `schema_version`。

## 2. app 必須讀取的欄位（改動需 app 同意）
| 層級 | 欄位 | 說明 |
|---|---|---|
| event | `id` | 建立後永不更改，格式 `YYYYMMDD-slug` |
| event | `title`、`kind`、`types`、`status` | `kind`: concert/tour/festival/event；`status`: scheduled/cancelled/postponed/ended |
| event | `artist_ids` | 這個活動屬於哪些藝人（用來決定出現在誰的檔案） |
| event | `confidence` | official／secondary／rumor，見第 5 節 |
| event | `official_url`、`sources[]` | 來源連結（`level` 1–6） |
| performance | `id`、`date`、`venue_name`、`prefecture`、`status` | `prefecture` **必填**（app 地區篩選用，海外不收） |
| performance | `open_time`、`start_time` | `HH:MM` 或 `null` |
| ticket_links | `site`、`url` | **新增**，見第 3 節 |
| ticket_phases | `type`、`start_at`、`end_at`、`result_at`、`sale_status` | 提醒功能用，見第 3 節 |

## 3. 建議調整（來自實際資料的問題）
實際資料裡發現 `ticket_phases` 同時被拿來放「去哪買」和「什麼時候買」，造成每個售票網一個階段、階段類型全是 `other`。建議拆開：

```jsonc
"ticket_links": [                       // 去哪買（純連結，不抓售票網）
  { "site": "e+",     "url": "https://eplus.jp/reona/",   "performance_ids": null },
  { "site": "ぴあ",   "url": "https://w.pia.jp/t/reona/", "performance_ids": null },
  { "site": "ローチケ","url": "https://l-tike.com/reona/", "performance_ids": null }
],
"ticket_phases": [                      // 什麼時候買、買的條件
  {
    "type": "lottery",                  // fc_presale / official_presale / lottery / first_come / general / door / other
    "label": "プレイガイド抽選",
    "performance_ids": ["p1"],          // null = 全部場次
    "start_at": "2026-09-01T12:00:00+09:00",
    "end_at":   "2026-09-10T23:59:00+09:00",
    "result_at": null,
    "price_text": "全席指定 8,800円（税込）",
    "buyer_restriction": "FC會員限定",    // 給人看，只有來源明確寫才填
    "overseas_card": "UNKNOWN",         // app 判斷用：OK / NEEDS_JP_PHONE_OR_ADDRESS / JP_RESIDENTS_ONLY / UNKNOWN
    "sale_status": "sold_out"           // not_announced / upcoming / on_sale / sold_out / ended / unknown
  }
]
```
- `sale_status` 取代把「Sold out」寫在 notes 的做法。
- `overseas_card` 是 app 現有功能（依使用者有沒有日本手機、日本卡判斷買不買得到）需要的結構化欄位；來源沒寫就 `UNKNOWN`，不要猜。
- 舊欄位 `ticket_phases[].label/url/phase` 暫時保留相容，新資料請改用 `ticket_links` 與 `type`。

另外：
- **核對標記結構化**：目前用「【2026-10-22 已對照官網】」寫在 `notes`。建議用 `last_verified_at`（已有）與 `sources[].level` 表達，`notes` 不再放核對標記。
- **同一巡演合併成一個活動**（YOASOBI 已是這樣）：ReoNa 目前在副本裡一城一個活動，skill 試跑版是一個巡演一個活動，請統一採後者。
- `city` 選填，不要求。

## 4. 藝人檔（`artists.json`）
`id`、`name_ja`、`name_en`、`name_zh`、`aliases`、`types`、`related_ids`，另加：`yomi`（平假名讀音，必填）、`tracked`（是否追蹤，預設 `false`，使用者同意才設 `true`）。

## 5. 資料可信度（`confidence`）
| 值 | 意思 | app 顯示 |
|---|---|---|
| `official` | 日期與場館有**官方一手來源**（藝人官網、事務所／唱片公司公告、主辦單位） | ✅ 官方 |
| `secondary` | 只有**二手來源**（新聞轉載、整合網站、Eventernote 等） | ⚠️ 待核對 |
| `rumor` | 傳聞、社群未證實 | **不發布到 app**，只留在報告 |

## 6. 範例（取自實際資料，節錄）
```jsonc
{
  "id": "20261029-reona-shibuya",
  "title": "ReoNa Concert Tour 2026 De:TOUR -静脈- 東京",
  "kind": "concert", "types": ["solo"], "status": "scheduled",
  "artist_ids": ["reona"],
  "performances": [{
    "id": "p1", "date": "2026-10-29", "open_time": "17:30", "start_time": "18:30",
    "venue_name": "LINE CUBE SHIBUYA", "prefecture": "東京都", "country": "JP", "status": "scheduled",
    "performers": [{ "artist_id": "reona", "name": "ReoNa" }]
  }],
  "ticket_links": [{ "site": "e+", "url": "https://eplus.jp/reona/", "performance_ids": null }],
  "ticket_phases": [{ "type": "lottery", "label": "プレイガイド抽選", "performance_ids": null,
    "start_at": null, "end_at": null, "result_at": null, "price_text": null,
    "buyer_restriction": null, "overseas_card": "UNKNOWN", "sale_status": "sold_out" }],
  "official_url": "https://www.sonymusic.co.jp/artist/ReoNa/info/587352",
  "sources": [{ "url": "https://www.sonymusic.co.jp/artist/ReoNa/info/587352", "level": 1, "retrieved_at": "2026-10-22T12:00:00+09:00" }],
  "confidence": "official",
  "first_seen_at": "2026-10-22T12:00:00+09:00", "last_verified_at": "2026-10-22T12:00:00+09:00"
}
```
YOASOBI 超惑星巡演：`kind: tour`，10 個 performance，`confidence: secondary`，開演時間大多 `null`，`sale_status` 札幌兩場為 `on_sale`、其餘 `not_announced` 或 `unknown`。

## 7. 待 skill 端回覆的問題
1. 拆 `ticket_links`／`ticket_phases` 是否可行？`validate.py`、`report.py` 要改哪裡？
2. `sale_status`、`overseas_card` 你們能不能從來源穩定判斷？不能的欄位就 `unknown`，是否可接受？
3. 還有哪些你們需要、但格式沒涵蓋的欄位（例如先行販賣類型、直播、聯動作品）？
4. 對「同一巡演合併成一個活動」有無困難（id、`performance_ids` 編號規則）？
