#!/usr/bin/env python3
"""由資料庫產生 Markdown 報告（僅用標準函式庫）。格式固定，不依賴模型自由發揮。

用法：
    python scripts/report.py                       # 輸出到 reports/jplive-YYYY-MM-DD.md
    python scripts/report.py --since 2026-10-28    # 指定「新增／變更」的起算時間
    python scripts/report.py --stdout              # 只印出，不寫檔
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))
WEEKDAY = "一二三四五六日"
CONF = {"official": "官方確認", "secondary": "僅整合站（尚未官方確認）", "rumor": "傳聞"}
STATUS = {"scheduled": "", "cancelled": "【已取消】", "postponed": "【延期】", "ended": "【已結束】"}
PHASE = {
    "fc_presale": "FC先行", "official_presale": "官方先行", "lottery": "抽選",
    "first_come": "先著", "general": "一般発売", "door": "當日券", "other": "其他",
}


def load(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def d_of(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def dt_of(s):
    return datetime.fromisoformat(s) if s else None


def fmt_date(s):
    d = d_of(s)
    return f"{d.year}/{d.month:02d}/{d.day:02d}（{WEEKDAY[d.weekday()]}）"


def fmt_dt(s):
    t = dt_of(s)
    if not t:
        return "未公布"
    t = t.astimezone(JST)
    return f"{t.year}/{t.month:02d}/{t.day:02d}（{WEEKDAY[t.weekday()]}）{t:%H:%M} JST"


def render_event(ev):
    out = []
    mark = STATUS.get(ev["status"], "")
    out.append(f"#### {mark}{ev['title']}")
    out.append(f"- 可信度：{CONF.get(ev['confidence'], ev['confidence'])}"
               + ("　／　陣容尚未全部公布" if ev.get("lineup_complete") is False else ""))
    out.append("- 場次：")
    for pf in ev["performances"]:
        tm = " / ".join(x for x in [pf.get("open_time"), pf.get("start_time")] if x) or "時間未公布"
        place = pf["venue_name"] + (f"（{pf['prefecture']}）" if pf.get("prefecture") else "")
        st = STATUS.get(pf["status"], "")
        out.append(f"  - {st}{fmt_date(pf['date'])} {place}　{tm}")
    if ev["ticket_phases"]:
        out.append("- 票務：")
        for tp in ev["ticket_phases"]:
            span = fmt_dt(tp.get("start_at"))
            if tp.get("end_at"):
                span += f" ～ {fmt_dt(tp['end_at'])}"
            extra = []
            if tp.get("result_at"):
                extra.append(f"結果 {fmt_dt(tp['result_at'])}")
            if tp.get("price_text"):
                extra.append(tp["price_text"])
            if tp.get("buyer_restriction"):
                extra.append(f"購買限制：{tp['buyer_restriction']}")
            out.append(f"  - {tp['label']}：{span}" + (f"　（{'；'.join(extra)}）" if extra else ""))
    else:
        out.append("- 票務：未公布")
    if ev.get("notes"):
        out.append(f"- 備註：{ev['notes']}")
    src = ev["sources"][0]
    out.append(f"- 來源：[{src.get('title') or src['url']}]({src['url']})")
    return "\n".join(out)


def event_artists(ev):
    ids = set(ev.get("artist_ids", []))
    for pf in ev["performances"]:
        for pr in pf.get("performers", []):
            if pr.get("artist_id"):
                ids.add(pr["artist_id"])
    return ids


def last_date(ev):
    return max(d_of(p["date"]) for p in ev["performances"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "live_events.json"))
    ap.add_argument("--artists", default=str(ROOT / "data" / "artists.json"))
    ap.add_argument("--config", default=str(ROOT / "data" / "config.json"))
    ap.add_argument("--since", help="YYYY-MM-DD，預設為今天（JST）")
    ap.add_argument("--today", help="測試用，覆寫今天的日期")
    ap.add_argument("--out", help="輸出檔路徑")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    cfg = load(args.config, {})
    now = datetime.now(JST)
    today = d_of(args.today) if args.today else now.date()
    since = datetime.combine(d_of(args.since) if args.since else today, datetime.min.time(), JST)
    window_end = datetime.combine(today, datetime.min.time(), JST) + timedelta(days=cfg.get("ticket_window_days", 14) + 1)
    window_start = datetime.combine(today, datetime.min.time(), JST)

    db = load(args.db, {"events": []})
    artists = load(args.artists, {"artists": []})["artists"]
    watch = [a for a in artists if a.get("watching")]
    # 只保留 focus_country（預設 JP）的場次；沒有任何符合場次的活動整筆略過
    focus = cfg.get("focus_country", "JP")
    events = []
    for e in db["events"]:
        pfs = [p for p in e["performances"] if p.get("country") == focus]
        if pfs:
            events.append({**e, "performances": pfs})

    lines = [f"# jplive 日報　{today.year}/{today.month:02d}/{today.day:02d}", ""]

    new = [e for e in events if dt_of(e["first_seen_at"]) >= since]
    chg = [e for e in events if e not in new and e.get("last_changed_at") and dt_of(e["last_changed_at"]) >= since]
    lines += [f"## 本次新增（{len(new)}）", ""]
    lines += [render_event(e) + "\n" for e in new] or ["無\n"]
    lines += [f"## 本次變更（{len(chg)}）", ""]
    lines += [render_event(e) + "\n" for e in chg] or ["無\n"]

    # 近期票務（開賣或截止落在視窗內）
    hits = []
    for e in events:
        if e["status"] in ("cancelled", "ended"):
            continue
        for tp in e["ticket_phases"]:
            for key, what in (("start_at", "開始"), ("end_at", "截止"), ("result_at", "結果公布")):
                t = dt_of(tp.get(key))
                if t and window_start <= t < window_end:
                    hits.append((t, e["title"], tp["label"], what))
    hits.sort()
    lines += [f"## 近期票務（未來 {cfg.get('ticket_window_days', 14)} 天）", ""]
    lines += [f"- {fmt_dt(t.isoformat())}　{title}　{label}　{what}" for t, title, label, what in hits] or ["無"]
    lines.append("")

    # 依藝人列出未來的 Live
    lines += ["## 關注清單：即將到來的 Live", ""]
    known = set()
    for a in watch:
        mine = [e for e in events if a["id"] in event_artists(e) and e["status"] != "ended"
                and e["status"] != "cancelled" and last_date(e) >= today]
        mine.sort(key=lambda e: min(d_of(p["date"]) for p in e["performances"]))
        lines.append(f"### {a['name_ja']}")
        lines.append("")
        if mine:
            lines += [render_event(e) + "\n" for e in mine]
            known.update(e["id"] for e in mine)
        else:
            lines.append("目前沒有已知的未來 Live。\n")
    others = [e for e in events if e["id"] not in known and e["status"] not in ("ended", "cancelled")
              and last_date(e) >= today]
    if others:
        lines += ["### 其他（不在關注清單內）", ""]
        lines += [render_event(e) + "\n" for e in others]

    lines += ["---", f"產生時間：{now:%Y-%m-%d %H:%M} JST　資料庫更新：{db.get('updated_at', '未知')}", ""]
    text = "\n".join(lines)

    if args.stdout:
        print(text)
        return 0
    out = Path(args.out) if args.out else ROOT / cfg.get("report_dir", "reports") / f"jplive-{today:%Y-%m-%d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"已輸出：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
