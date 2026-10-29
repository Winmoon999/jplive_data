# 交接紀錄（新的在最上面）

## 2026-10-29 app 端 → skill 端（補充）
- 使用者同意：新藝人進來時可先查該藝人的 Eventernote 頁面一次當線索，再用官方來源搜尋核對（規則見 ROLES「第三方整合站的使用規則」）。映画.com 不納入。
- 請試上田麗奈、fripSide、あいみょん、Aimer，並回報 Eventernote 藝人頁在雲端環境是否讀得到（被允許清單擋掉就如實記錄，不繞過）。

## 2026-10-29 app 端 → skill 端
- 新增 `scripts/publish.py`：吃正本 `.claude/skills/jplive/data/` 產生衍生檔，已用 PR #2 的試跑資料測試通過。
- 請在 `artists.json` 為每位藝人補 `yomi`（平假名）與 `tracked: true`；publish 暫時也認 `watching`。
- 請依 `docs/ROLES.md`「副本核對流程」核對 `data-review` 分支的副本，再試跑 4 位新藝人。
- 附帶發現：你們 PR #2 的試跑與我們副本的 ReoNa 資料日期、時間一致；YOASOBI 兩邊都是第三方來源。
