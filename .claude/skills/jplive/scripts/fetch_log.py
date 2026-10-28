#!/usr/bin/env python3
"""抓取紀錄：避免重複抓取已處理過的頁面（僅用標準函式庫）。

兩種頁面：
  detail  單一活動的詳細頁。抓過就不再抓；只有「待確認」的活動才依 recheck_pending_days 複查。
  index   藝人官網的 Live 一覽、新聞列表、搜尋結果。要靠它發現新活動，所以每個日本日曆日可抓一次。

指令：
  check URL --kind detail|index [--pending]   輸出 FETCH 或 SKIP 與原因
  mark  URL --kind detail|index --outcome ok|empty|error [--artist ID ...]
  artist-due                                  列出今天（JST）還沒檢查過的關注藝人
  artist-done ID                              記錄該藝人今天已檢查
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "fetch_log.json"
CONFIG = ROOT / "data" / "config.json"
ARTISTS = ROOT / "data" / "artists.json"
JST = timezone(timedelta(hours=9))
TRACKING = {"fbclid", "gclid", "igshid", "ref", "si"}


def now():
    return datetime.now(JST)


def load(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_log(log):
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(url):
    """正規化網址：小寫網域、去除 fragment、追蹤參數、結尾斜線，查詢參數排序。"""
    p = urlsplit(url.strip())
    q = sorted(
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.startswith("utm_") and k not in TRACKING
    )
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(q), ""))


def hours_since(iso):
    return (now() - datetime.fromisoformat(iso)).total_seconds() / 3600


def cmd_check(args, cfg, log):
    key = norm(args.url)
    e = log["entries"].get(key)
    if e is None:
        return f"FETCH 從未抓過 [{key}]"

    if e["outcome"] == "error":
        if hours_since(e["last_attempt_at"]) >= cfg.get("error_retry_hours", 24):
            return "FETCH 上次失敗，已超過重試間隔"
        return "SKIP 上次失敗，尚未到重試間隔"

    if args.kind == "index":
        last_day = datetime.fromisoformat(e["last_fetched_at"]).astimezone(JST).date()
        if last_day == now().date():
            return "SKIP 一覽頁今天已抓過"
        return "FETCH 一覽頁，新的一天"

    # detail
    days = cfg.get("recheck_pending_days", 0)
    if args.pending and days > 0 and hours_since(e["last_fetched_at"]) >= days * 24:
        return f"FETCH 待確認活動，距上次抓取已超過 {days} 天"
    return "SKIP 詳細頁已抓過"


def cmd_mark(args, cfg, log):
    key = norm(args.url)
    t = now().isoformat(timespec="seconds")
    e = log["entries"].get(key) or {"kind": args.kind, "first_fetched_at": t, "artist_ids": []}
    e["kind"] = args.kind
    e["last_attempt_at"] = t
    e["outcome"] = args.outcome
    if args.outcome != "error":
        e["last_fetched_at"] = t
    e.setdefault("last_fetched_at", t)
    for a in args.artist or []:
        if a not in e["artist_ids"]:
            e["artist_ids"].append(a)
    log["entries"][key] = e
    save_log(log)
    return f"已記錄 {args.outcome}：{key}"


def cmd_artist_due(args, cfg, log):
    artists = load(ARTISTS, {"artists": []})["artists"]
    today = now().date()
    due = []
    for a in artists:
        if not a.get("watching"):
            continue
        last = log["artist_checks"].get(a["id"])
        if not last or datetime.fromisoformat(last).astimezone(JST).date() < today:
            due.append(a["id"])
    return "\n".join(due) if due else "（今天所有關注藝人都已檢查）"


def cmd_artist_done(args, cfg, log):
    log["artist_checks"][args.id] = now().isoformat(timespec="seconds")
    save_log(log)
    return f"已記錄 {args.id} 今天已檢查"


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("url")
    c.add_argument("--kind", choices=["detail", "index"], required=True)
    c.add_argument("--pending", action="store_true")
    m = sub.add_parser("mark")
    m.add_argument("url")
    m.add_argument("--kind", choices=["detail", "index"], required=True)
    m.add_argument("--outcome", choices=["ok", "empty", "error"], required=True)
    m.add_argument("--artist", action="append")
    sub.add_parser("artist-due")
    d = sub.add_parser("artist-done")
    d.add_argument("id")
    args = ap.parse_args()

    cfg = load(CONFIG, {})
    log = load(LOG, {"schema_version": 1, "entries": {}, "artist_checks": {}})
    fn = {"check": cmd_check, "mark": cmd_mark, "artist-due": cmd_artist_due, "artist-done": cmd_artist_done}[args.cmd]
    print(fn(args, cfg, log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
