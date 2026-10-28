# jplive_data

羅列日本歌手演唱會資料。只收錄**日本國內**場次，只存事實欄位（日期、場館、時間、票務階段）與來源連結，不轉載官方網站內文。

## 結構
- `index.json`：藝人索引（含 50 音 `gojuon`、`yomi`、別名、活動數、最近日期）。
- `artists/<id>.json`：每位藝人一個檔案（`artist` + `events[]`）。跨藝人的活動會同時出現在各自的檔案中，`id` 相同，匯入時以 `id` upsert。
- `schema/live_event.schema.json`：活動資料格式（schema_version 1）。

## 注意
- `confidence`：`official`（有官方來源）／`secondary`（僅整合站，待核對）／`rumor`。
- 票務只留連結，日本多為抽選，請至各售票網確認；本資料不保證即時、正確，請以官方公告為準。
- 資料可能有誤，請在 app 內使用「回報資料有誤」或開 Issue。
