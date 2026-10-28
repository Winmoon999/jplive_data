#!/usr/bin/env python3
"""由 artists/*.json 產生人類可讀的 Markdown：SCHEDULE.md（全部依日期）與 views/<id>.md（每位藝人）。
用法：python3 scripts/build_views.py [--today YYYY-MM-DD]。每次資料更新後執行，產物與 JSON 一起提交。"""
import json, sys, argparse, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
WD = "一二三四五六日"
CONF = {"official": "✅ 官方", "secondary": "⚠️ 待核對", "rumor": "❓ 傳聞"}
def wd(d): 
    x = datetime.date.fromisoformat(d); return f"{d[5:].replace('-', '/')}（{WD[x.weekday()]}）"
def esc(s): return (s or "").replace("|", "／").replace("\n", " ")
def hhmm(p):
    o, s = p.get("open_time"), p.get("start_time")
    return " / ".join(x for x in (f"開場 {o}" if o else "", f"開演 {s}" if s else "") if x) or "未公布"
def fmt_dt(s): return s[5:16].replace("-", "/").replace("T", " ") if s else None
def tickets(ev, pid):
    out = []
    for t in ev["ticket_phases"]:
        ids = t.get("performance_ids")
        if ids is not None and pid not in ids: continue
        when = " ".join(x for x in (f"開賣 {fmt_dt(t.get('start_at'))}" if t.get("start_at") else "", f"截止 {fmt_dt(t.get('end_at'))}" if t.get("end_at") else "") if x)
        label = f"[{esc(t['label'])}]({t['url']})" if t.get("url") else esc(t["label"])
        out.append(label + (f" {when}" if when else ""))
    return "<br>".join(out) or "—"
def rows(events, today, with_artist=False, names=None):
    items = []
    for ev in events:
        for p in ev["performances"]:
            items.append((p["date"], ev, p))
    items.sort(key=lambda x: (x[0], x[1]["id"]))
    up = [i for i in items if i[0] >= today]; past = [i for i in items if i[0] < today]
    def table(lst):
        head = "| 日期 | " + ("藝人 | " if with_artist else "") + "活動 | 場館 | 時間 | 票務 | 資料 |\n|---|" + ("---|" if with_artist else "") + "---|---|---|---|---|\n"
        body = ""
        for d, ev, p in lst:
            a = (" | ".join([esc("、".join(names.get(i, i) for i in ev["artist_ids"]))]) + " | ") if with_artist else ""
            body += f"| {wd(d)} | {a}{esc(ev['title'])} | {esc(p['venue_name'])}（{esc(p.get('prefecture'))}） | {hhmm(p)} | {tickets(ev, p['id'])} | {CONF.get(ev['confidence'], ev['confidence'])} |\n"
        return head + body
    return (table(up) if up else "_目前沒有已知的未來場次。_\n"), (table(past) if past else "")
HEAD = """# jplive_data

羅列日本歌手演唱會資料。只收錄**日本國內**場次，只存事實欄位（日期、場館、時間、票務階段）與來源連結，不轉載官方網站內文。

## 直接看
- **[全部時間表（依日期）](SCHEDULE.md)**
- 依藝人（50 音）：
{TOC}
## 給 app／程式用的資料
- `index.json`：藝人索引（50 音 `gojuon`、`yomi`、別名、活動數）。
- `artists/<id>.json`：每位藝人一個檔案。跨藝人的活動會同時出現在各自的檔案，`id` 相同，匯入時以 `id` upsert。
- `schema/live_event.schema.json`：資料格式（schema_version 1）。
- `views/*.md`、`SCHEDULE.md`、本檔由 `python3 scripts/build_views.py` 自動產生，請勿手改。

## 注意
- ✅官方＝有官方來源；⚠️待核對＝僅整合站，請先對照官方公告。
- 票務只提供連結（日本多為抽選），開賣時間以售票網為準。本資料不保證即時、正確。
"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--today", default=datetime.date.today().isoformat()); a = ap.parse_args()
    idx = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    names = {x["id"]: x["name_ja"] for x in idx["artists"]}
    allev = {}; per = {}
    for x in idx["artists"]:
        d = json.loads((ROOT / x["file"]).read_text(encoding="utf-8"))
        per[x["id"]] = d["events"]
        for e in d["events"]: allev[e["id"]] = e
    foot = f"\n---\n資料更新：{idx['updated_at']}　｜　✅官方＝有官方來源　⚠️待核對＝僅整合站，請先對照官方公告再買票。票務只提供連結，開賣時間以售票網為準。\n"
    up, past = rows(list(allev.values()), a.today, True, names)
    md = f"# 日本 Live 時間表\n\n_以 {a.today} 為準；依日期排序。_\n\n## 即將到來\n\n{up}\n"
    if past: md += f"\n## 已結束\n\n{past}"
    (ROOT / "SCHEDULE.md").write_text(md + foot, encoding="utf-8")
    links = []
    for x in sorted(idx["artists"], key=lambda z: (z["gojuon"], z["yomi"])):
        up, past = rows(per[x["id"]], a.today)
        ttl = x['name_ja'] if x['name_en'] == x['name_ja'] else f"{x['name_ja']}（{x['name_en']}）"
        m = f"# {ttl}\n\n別名：{'、'.join(x['aliases'])}\n\n## 即將到來\n\n{up}\n"
        if past: m += f"\n## 已結束\n\n{past}"
        (ROOT / "views" / f"{x['id']}.md").write_text(m + foot, encoding="utf-8")
        links.append((x["gojuon"], f"[{x['name_ja']}](views/{x['id']}.md)（{x['event_count']} 場）"))
    print("ok", len(allev), "events,", len(idx["artists"]), "artists")
    grp = {}
    for g, l in links: grp.setdefault(g, []).append(l)
    toc = "".join(f"- **{g}行**：{'、'.join(v)}\n" for g, v in sorted(grp.items(), key=lambda kv: "あかさたなはまやらわ".index(kv[0])))
    (ROOT / "README.md").write_text(HEAD.replace("{TOC}", toc), encoding="utf-8")
main()
