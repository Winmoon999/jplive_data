#!/usr/bin/env python3
"""發布腳本（app 端負責維護）。

把 skill 的「正本」資料庫轉成 app 與人類要讀的檔案：
  輸入（正本，skill 維護）：<src>/data/live_events.json、<src>/data/artists.json
  輸出（衍生檔，請勿手改）：
    index.json            藝人索引（50 音）
    artists/<id>.json     每位藝人一個檔案（app 下載這個）
    SCHEDULE.md           全部活動依日期的表格
    views/<id>.md         每位藝人的表格
    README.md             首頁（含 50 音目錄）

用法：python3 scripts/publish.py [--src .claude/skills/jplive] [--out .] [--today YYYY-MM-DD]
規則：只發布 artists.json 中 tracked（或舊欄位 watching）為 true 的藝人。
      不讀、不改 old/。輸出前先驗證輸入，驗證不過就不寫任何檔案。
"""
import argparse, datetime, json, pathlib, re, sys

WD = "一二三四五六日"
CONF = {"official": "✅ 官方", "secondary": "⚠️ 待核對", "rumor": "❓ 傳聞"}
ROWS = "あかさたなはまやらわ"
KANA_ROW = {}
for row, chars in {
    "あ": "あいうえおぁぃぅぇぉ", "か": "かきくけこがぎぐげご", "さ": "さしすせそざじずぜぞ",
    "た": "たちつてとだぢづでどっ", "な": "なにぬねの", "は": "はひふへほばびぶべぼぱぴぷぺぽ",
    "ま": "まみむめも", "や": "やゆよゃゅょ", "ら": "らりるれろ", "わ": "わをんゐゑ"}.items():
    for ch in chars: KANA_ROW[ch] = row

def to_hira(s):  # 片假名 → 平假名
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)

def gojuon_of(yomi):
    return KANA_ROW.get(to_hira(yomi)[:1], "他") if yomi else "他"

def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))

def tracked(a):
    return bool(a.get("tracked", a.get("watching", False)))

def wd(d):
    x = datetime.date.fromisoformat(d)
    return f"{d[5:].replace('-', '/')}（{WD[x.weekday()]}）"

def esc(s):
    return (s or "").replace("|", "／").replace("\n", " ")

def hhmm(p):
    o, s = p.get("open_time"), p.get("start_time")
    return " / ".join(x for x in (f"開場 {o}" if o else "", f"開演 {s}" if s else "") if x) or "未公布"

def fmt_dt(s):
    return s[5:16].replace("-", "/").replace("T", " ") if s else None

def tickets(ev, pid):
    out = []
    for t in ev.get("ticket_phases", []):
        ids = t.get("performance_ids")
        if ids is not None and pid not in ids:
            continue
        when = " ".join(x for x in (
            f"開賣 {fmt_dt(t.get('start_at'))}" if t.get("start_at") else "",
            f"截止 {fmt_dt(t.get('end_at'))}" if t.get("end_at") else "") if x)
        label = f"[{esc(t['label'])}]({t['url']})" if t.get("url") else esc(t["label"])
        out.append(label + (f" {when}" if when else ""))
    return "<br>".join(out) or "—"

def table(items, names=None):
    head = "| 日期 | " + ("藝人 | " if names else "") + "活動 | 場館 | 時間 | 票務 | 資料 |\n|---|" + ("---|" if names else "") + "---|---|---|---|---|\n"
    body = ""
    for d, ev, p in items:
        a = esc("、".join(names.get(i, i) for i in ev.get("artist_ids", []))) + " | " if names else ""
        body += (f"| {wd(d)} | {a}{esc(ev['title'])} | {esc(p['venue_name'])}（{esc(p.get('prefecture'))}） | "
                 f"{hhmm(p)} | {tickets(ev, p['id'])} | {CONF.get(ev['confidence'], ev['confidence'])} |\n")
    return head + body

def split(events, today):
    items = sorted(((p["date"], ev, p) for ev in events for p in ev["performances"]), key=lambda x: (x[0], x[1]["id"]))
    return [i for i in items if i[0] >= today], [i for i in items if i[0] < today]

def section(events, today, names=None):
    up, past = split(events, today)
    s = "## 即將到來\n\n" + (table(up, names) if up else "_目前沒有已知的未來場次。_\n")
    if past:
        s += "\n## 已結束\n\n" + table(past, names)
    return s

def involved(ev, aid):
    return aid in ev.get("artist_ids", []) or any(pf.get("artist_id") == aid for p in ev["performances"] for pf in p.get("performers", []))

HEAD = """# jplive_data

羅列日本歌手演唱會資料。只收錄**日本國內**場次，只存事實欄位（日期、場館、時間、票務階段）與來源連結，不轉載官方網站內文。

## 直接看
- **[全部時間表（依日期）](SCHEDULE.md)**
- 依藝人（50 音）：
{TOC}
## 給 app／程式用的資料（自動產生，請勿手改）
- `index.json`：藝人索引（50 音 `gojuon`、`yomi`、別名、活動數）。
- `artists/<id>.json`：每位藝人一個檔案。跨藝人的活動會同時出現在各自的檔案，`id` 相同，匯入時以 `id` upsert。
- 資料正本在 `.claude/skills/jplive/data/`；分工與流程見 `docs/ROLES.md`。

## 注意
- ✅官方＝有官方來源；⚠️待核對＝僅整合站，請先對照官方公告。
- 票務只提供連結（日本多為抽選），開賣時間以售票網為準。
- **以上內容僅供參考，請以官方公布為主。** 本資料不保證即時、正確。
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".claude/skills/jplive")
    ap.add_argument("--out", default=".")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    today = a.today or now.date().isoformat()

    db = load(src / "data" / "live_events.json")
    artists = load(src / "data" / "artists.json")["artists"]
    errs = []
    if db.get("schema_version") != 1:
        errs.append(f"schema_version 不是 1：{db.get('schema_version')}")
    ids = [e["id"] for e in db["events"]]
    errs += [f"活動 id 重複：{i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    known = {x["id"] for x in artists}
    for e in db["events"]:
        for aid in e.get("artist_ids", []):
            if aid not in known:
                errs.append(f"活動 {e['id']} 指向不存在的藝人 {aid}")
    if errs:
        print("驗證失敗，未寫入任何檔案：\n- " + "\n- ".join(errs)); return 1

    pub = [x for x in artists if tracked(x)]
    names = {x["id"]: x["name_ja"] for x in pub}
    updated = db.get("updated_at") or now.isoformat(timespec="seconds")
    foot = (f"\n---\n資料更新：{updated}　｜　✅官方＝有官方來源　⚠️待核對＝僅整合站，請先對照官方公告再買票。"
            "票務只提供連結，開賣時間以售票網為準。\n**以上內容僅供參考，請以官方公布為主。**\n")

    (out / "artists").mkdir(parents=True, exist_ok=True)
    (out / "views").mkdir(parents=True, exist_ok=True)
    for old in (out / "artists").glob("*.json"):
        old.unlink()
    for old in (out / "views").glob("*.md"):
        old.unlink()

    index, per, warn = [], {}, []
    for x in pub:
        evs = [e for e in db["events"] if involved(e, x["id"])]
        per[x["id"]] = evs
        yomi = x.get("yomi") or ""
        if not yomi:
            warn.append(f"{x['id']} 缺少 yomi（假名讀音），50 音歸「他」；請 skill 補上")
        fut = sorted(p["date"] for e in evs for p in e["performances"] if p["date"] >= today and p.get("status") != "cancelled")
        entry = {"id": x["id"], "name_ja": x["name_ja"], "name_en": x.get("name_en"), "name_zh": x.get("name_zh"),
                 "yomi": yomi, "gojuon": x.get("gojuon") or gojuon_of(yomi), "aliases": x.get("aliases", []),
                 "types": x.get("types", []), "file": f"artists/{x['id']}.json",
                 "event_count": len(evs), "next_date": fut[0] if fut else None}
        index.append(entry)
        body = {"schema_version": 1, "updated_at": updated,
                "artist": {k: x.get(k) for k in ("id", "name_ja", "name_en", "name_zh", "aliases", "types", "related_ids")},
                "events": evs}
        (out / "artists" / f"{x['id']}.json").write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index.sort(key=lambda z: (ROWS.index(z["gojuon"]) if z["gojuon"] in ROWS else 99, z["yomi"], z["id"]))
    (out / "index.json").write_text(json.dumps({"schema_version": 1, "updated_at": updated, "artists": index},
                                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    allev = {e["id"]: e for evs in per.values() for e in evs}
    (out / "SCHEDULE.md").write_text(f"# 日本 Live 時間表\n\n_以 {today} 為準；依日期排序。_\n\n"
                                     + section(list(allev.values()), today, names) + foot, encoding="utf-8")
    toc = {}
    for e in index:
        ttl = e["name_ja"] if e["name_en"] in (None, e["name_ja"]) else f"{e['name_ja']}（{e['name_en']}）"
        x = next(z for z in pub if z["id"] == e["id"])
        (out / "views" / f"{e['id']}.md").write_text(
            f"# {ttl}\n\n別名：{'、'.join(e['aliases']) or '—'}\n\n" + section(per[e['id']], today) + foot, encoding="utf-8")
        toc.setdefault(e["gojuon"], []).append(f"[{e['name_ja']}](views/{e['id']}.md)（{e['event_count']} 場）")
    order = lambda g: ROWS.index(g) if g in ROWS else 99
    (out / "README.md").write_text(HEAD.replace("{TOC}", "".join(
        f"- **{g}行**：{'、'.join(v)}\n" for g, v in sorted(toc.items(), key=lambda kv: order(kv[0])))), encoding="utf-8")

    for w in warn:
        print("[警告]", w)
    print(f"發布完成：{len(pub)} 位藝人、{len(allev)} 筆活動（today={today}）")
    return 0

if __name__ == "__main__":
    sys.exit(main())
