# 資料庫格式（給人看的說明）

機器可讀的權威定義是 `schema/live_event.schema.json`；本文件說明設計理由與 Android 對應方式。兩者衝突時以 schema 為準。

## 檔案

| 檔案 | 內容 |
|---|---|
| `data/live_events.json` | 活動資料庫：`{ schema_version, updated_at, events[] }` |
| `data/artists.json` | 藝人／企劃主檔與關注清單：`{ schema_version, artists[] }` |
| `data/config.json` | 設定（國別、複查天數、報告資料夾等） |
| `data/fetch_log.json` | 抓取紀錄，Android 不需要讀取 |

空模板：

```json
{ "schema_version": 1, "updated_at": "2026-01-01T00:00:00+09:00", "events": [] }
```

## 階層

```
event（一個活動或一整個巡演／祭典）
├── performances[]   每一個開催日／場次
│   └── performers[] 該場出演者
├── ticket_phases[]  票務階段（可指定適用哪些場次）
├── streaming        直播／ライブビューイング
└── sources[]        資料來源與等級
```

## 重要欄位

| 欄位 | 說明 |
|---|---|
| `id` | 永不更改的主鍵。格式 `YYYYMMDD-slug`，日期為建立當下最早場次日期 |
| `kind` | `concert` / `tour` / `festival` / `event` |
| `types` | `solo` / `group` / `festival` / `franchise`，可複選 |
| `status` | `scheduled` / `cancelled` / `postponed` / `ended`；event 與 performance 各有一個 |
| `performances[].id` | 在該 event 內唯一，格式 `p1`、`p2`…；建立後不重新編號 |
| `performances[].country` | ISO 3166-1 alpha-2，本 skill 只收 `JP`；欄位保留是為了日後擴充 |
| `open_time` `start_time` | `HH:MM`，不知道就 `null`，不可用 `00:00` 充數 |
| `ticket_phases[].performance_ids` | `null` 表示適用全部場次 |
| `lineup_complete` | 祭典陣容是否已全部公布。`false` 代表之後還會增加 |
| `sources[].level` | 1–6，對應 `references/sources.md` 的等級 |
| `confidence` | `official` / `secondary` / `rumor`，必須與來源等級一致（validate.py 會檢查） |
| `first_seen_at` | 第一次記錄的時間，含 `+09:00` |
| `last_changed_at` | 內容真的變動的時間（日期、場地、票務、狀態、陣容）；只是重新查證沒變時**不要**更新。報告的「本次變更」與 app 的更新通知都靠它 |
| `last_verified_at` | 最後一次查證時間，每次查證都更新 |
| `ticket_phases[].buyer_restriction` | 購買限制，如 FC 會員限定、需日本國內電話。只有來源明確寫出才填，否則 `null` |

所有日期時間為 ISO 8601。純日期用 `YYYY-MM-DD`，時間點用 `YYYY-MM-DDTHH:MM:SS+09:00`。

## 更新規則（合併而非覆蓋）

1. 以 `event.id` 找既有資料；有則更新、無則新增。
2. 絕不刪除。取消 → `status: "cancelled"`，延期 → `"postponed"`，過期 → `"ended"`。
3. 延期後日期改變時，**id 不變**，舊日期寫在 `notes`。
4. 新增場次時，`performances[].id` 接續現有最大編號。
5. 每次查證都更新 `last_verified_at`，即使內容沒變。
6. 更新後一定要跑 `python scripts/validate.py data/live_events.json`。

## Android（Room）對應建議

建議把 JSON 當作**交換格式**，在 app 內拆成關聯表，而不是整份存成一個欄位：

| 表 | 主鍵 | 備註 |
|---|---|---|
| `event` | `id` | `types`、`artist_ids` 用關聯表或 TypeConverter |
| `performance` | `(event_id, id)` | 日期用 `LocalDate`，時間用 `LocalTime?` |
| `performer` | 自動編號 | 外鍵指向 performance |
| `ticket_phase` | 自動編號 | `performance_ids` 另建關聯表 |
| `source` | 自動編號 | 外鍵指向 event |
| `artist` | `id` | 含 `watching` 旗標與 `related_ids` 關聯 |

實作要點：

- JSON 解析可用 kotlinx.serialization。欄位多為可為 null，對應 Kotlin 的 `?` 型別。
- 以 `schema_version` 判斷是否需要資料遷移。結構有不相容變更時遞增版本，並同步更新 schema 與 validate.py。
- 匯入策略：以 `id` 做 upsert；不要因為 JSON 沒有某筆就刪除本機資料。
- 通知功能（開賣提醒）可直接使用 `ticket_phases[].start_at`。
- 時區：app 內一律以 `Asia/Tokyo` 顯示活動時間，另外視需要顯示使用者本地時間。

## artists.json 欄位

```json
{
  "id": "sample-artist",
  "types": ["solo"],
  "name_ja": "サンプルアーティスト",
  "name_en": "Sample Artist",
  "name_zh": "範例藝人",
  "aliases": ["別名或舊名"],
  "agency": null,
  "official_url": null,
  "franchise": null,
  "watching": false
}
```

- `id`：小寫英數與連字號，建立後不更改。
- `aliases`：搜尋比對用，含常見譯名、暱稱、舊藝名。
- `franchise`：聲優或樂團所屬的企劃（可為 null）。
- `related_ids`：有關聯的對象（例如團體與成員），查詢時一併檢查，但活動分開記錄。
- `notes`：搜尋提示或狀態備註，例如名稱含特殊符號、活動狀態需以官方為準。
- `watching`：使用者關注旗標，每日追蹤只處理 `true` 的對象。由使用者決定，Claude 不自行設為 true。
