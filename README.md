# jplive_data

羅列日本歌手演唱會資料。只收錄**日本國內**場次，只存事實欄位（日期、場館、時間、票務階段）與來源連結，不轉載官方網站內文。

## 直接看
- **[全部時間表（依日期）](SCHEDULE.md)**
- 依藝人（50 音）：
- **あ行**：[あたらよ](views/atarayo.md)（2 場）、[幾田りら](views/ikuta-lilas.md)（0 場）
- **た行**：[茅原実里](views/chihara-minori.md)（6 場）、[tuki.](views/tuki.md)（6 場）
- **な行**：[西野カナ](views/nishino-kana.md)（0 場）
- **や行**：[YOASOBI](views/yoasobi.md)（1 場）
- **ら行**：[ReoNa](views/reona.md)（7 場）

## 給 app／程式用的資料
- `index.json`：藝人索引（50 音 `gojuon`、`yomi`、別名、活動數）。
- `artists/<id>.json`：每位藝人一個檔案。跨藝人的活動會同時出現在各自的檔案，`id` 相同，匯入時以 `id` upsert。
- `schema/live_event.schema.json`：資料格式（schema_version 1）。
- `views/*.md`、`SCHEDULE.md`、本檔由 `python3 scripts/build_views.py` 自動產生，請勿手改。

## 注意
- ✅官方＝有官方來源；⚠️待核對＝僅整合站，請先對照官方公告。
- 票務只提供連結（日本多為抽選），開賣時間以售票網為準。本資料不保證即時、正確。
