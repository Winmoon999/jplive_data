#!/usr/bin/env python3
"""留言板工具（skill 端、app 端、使用者三方共用）。討論串放在 board/threads/T###-*.md。

指令：
  board.py list                         列出全部討論串與狀態
  board.py check                        驗證格式與「一次只有一個 active」
  board.py new "標題" --from app --to skill   建立新討論串（status=queued，若目前沒有 active 則直接 active）
  board.py reply T001 --who skill "內容"      追加一則回覆，並自動切換 turn、狀態（active→answered 需用 propose）
  board.py propose T001 --who skill "結論草稿"  提出結論，狀態改 answered，等使用者確認
  board.py finish T001 --ok-by 使用者           【需使用者明確同意後才可執行】標記 finished、寫入 CONCLUSIONS.md、啟動下一個 queued
"""
import argparse, datetime, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TH = ROOT / "board" / "threads"
CONC = ROOT / "board" / "CONCLUSIONS.md"
STATUS = ("queued", "active", "answered", "finished")
SIDES = ("app", "skill", "human")
HDR = re.compile(r"^- (status|from|to|turn|created|finished): *(.*)$", re.M)

def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

def parse(p):
    t = p.read_text(encoding="utf-8")
    h = {k: v.strip() for k, v in HDR.findall(t.split("## 問題")[0])}
    title = re.match(r"# (T\d+) (.+)", t)
    h["id"], h["title"] = title.group(1), title.group(2).strip()
    h["path"], h["text"] = p, t
    return h

def threads():
    return sorted((parse(p) for p in TH.glob("T*.md")), key=lambda x: x["id"])

def write_header(t, **kw):
    s = t["text"]
    for k, v in kw.items():
        if re.search(rf"^- {k}:.*$", s, re.M):
            s = re.sub(rf"^- {k}:.*$", f"- {k}: {v}", s, count=1, flags=re.M)
        else:
            s = s.replace("\n## 問題", f"\n- {k}: {v}\n\n## 問題", 1) if "\n- turn:" not in s else s
    t["path"].write_text(s, encoding="utf-8"); t["text"] = s

def section_conclusion(t):
    m = re.search(r"## 結論\n(.*?)(?:\Z|\n## )", t["text"], re.S)
    body = (m.group(1) if m else "").strip()
    return "" if body.startswith("（") else body

def cmd_check():
    errs = []
    ts = threads()
    ids = [t["id"] for t in ts]
    errs += [f"編號重複 {i}" for i in set(ids) if ids.count(i) > 1]
    act = [t["id"] for t in ts if t.get("status") == "active"]
    if len(act) > 1:
        errs.append(f"同時有多個 active：{act}（一次只能一個）")
    for t in ts:
        if t.get("status") not in STATUS: errs.append(f"{t['id']} status 不合法：{t.get('status')}")
        if t.get("from") not in SIDES or t.get("to") not in SIDES: errs.append(f"{t['id']} from/to 不合法")
        if t.get("status") == "finished" and not section_conclusion(t): errs.append(f"{t['id']} 已 finished 但沒有結論")
        if t.get("status") in ("active", "answered") and t.get("turn") not in SIDES: errs.append(f"{t['id']} 缺少 turn")
    for e in errs: print("[錯誤]", e)
    print(f"檢查完成：{len(ts)} 個討論串，{len(errs)} 個錯誤")
    return 1 if errs else 0

def cmd_list():
    for t in threads():
        print(f"{t['id']} [{t.get('status'):8}] {t['from']}→{t['to']} 輪到:{t.get('turn','-'):5} {t['title']}")
    return 0

def next_id():
    n = [int(t["id"][1:]) for t in threads()] or [0]
    return f"T{max(n)+1:03d}"

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:30] or "topic"

def cmd_new(a):
    ts = threads()
    tid = next_id()
    st = "queued" if any(t.get("status") in ("active", "answered") for t in ts) else "active"
    p = TH / f"{tid}.md"
    p.write_text(f"""# {tid} {a.title}

- status: {st}
- from: {a.__dict__['from']}
- to: {a.to}
- turn: {a.to}
- created: {now()}

## 問題
{a.body or '（請補充）'}

## 討論

## 結論
（尚未有結論）
""", encoding="utf-8")
    print("已建立", p.name, "狀態", st); return 0

def find(tid):
    for t in threads():
        if t["id"] == tid: return t
    sys.exit(f"找不到 {tid}")

def cmd_reply(a, propose=False):
    t = find(a.tid)
    if t.get("status") not in ("active", "answered"):
        sys.exit(f"{a.tid} 目前是 {t.get('status')}，不能回覆（queued 要等輪到；finished 已結束）")
    s = t["text"].replace("\n## 結論", f"\n### {now()} {a.who}{'（結論草稿）' if propose else ''}\n{a.body}\n\n## 結論", 1)
    t["text"] = s; t["path"].write_text(s, encoding="utf-8")
    if propose:
        s2 = re.sub(r"\n## 結論\n.*\Z", f"\n## 結論\n{a.body}\n", t["text"], flags=re.S)
        t["path"].write_text(s2, encoding="utf-8"); t["text"] = s2
        write_header(t, status="answered", turn="human")
    else:
        if a.who == "human":
            nxt = t["to"]
        else:
            nxt = t["from"] if a.who == t["to"] else t["to"]
        write_header(t, status="active", turn=nxt)
    print("已回覆", a.tid); return 0

def cmd_finish(a):
    t = find(a.tid)
    if t.get("status") != "answered":
        sys.exit(f"{a.tid} 必須先由雙方討論並用 propose 提出結論（status=answered），才能 finish")
    c = section_conclusion(t)
    if not c: sys.exit("沒有結論內容")
    write_header(t, status="finished", turn="-", finished=f"{now()}（{a.ok_by} 確認）")
    old = CONC.read_text(encoding="utf-8") if CONC.exists() else "# 已完成的結論（由 board.py finish 自動整理）\n"
    CONC.write_text(old.rstrip() + f"\n\n## {t['id']} {t['title']}\n- 提問：{t['from']}→{t['to']}　完成：{now()}（{a.ok_by} 確認）\n\n{c}\n", encoding="utf-8")
    q = [x for x in threads() if x.get("status") == "queued"]
    if q and not any(x.get("status") == "active" for x in threads()):
        write_header(q[0], status="active", turn=q[0]["to"]); print("已啟動下一個：", q[0]["id"])
    print("已完成", a.tid); return 0

def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list"); sp.add_parser("check")
    n = sp.add_parser("new"); n.add_argument("title"); n.add_argument("--from", dest="from", choices=SIDES, required=True); n.add_argument("--to", choices=SIDES, required=True); n.add_argument("--body", default="")
    for nm in ("reply", "propose"):
        r = sp.add_parser(nm); r.add_argument("tid"); r.add_argument("--who", choices=SIDES, required=True); r.add_argument("body")
    f = sp.add_parser("finish"); f.add_argument("tid"); f.add_argument("--ok-by", required=True, help="必須是使用者明確同意，例如：使用者")
    a = ap.parse_args()
    if a.cmd == "list": return cmd_list()
    if a.cmd == "check": return cmd_check()
    if a.cmd == "new": return cmd_new(a)
    if a.cmd == "reply": return cmd_reply(a)
    if a.cmd == "propose": return cmd_reply(a, True)
    if a.cmd == "finish": return cmd_finish(a)

if __name__ == "__main__":
    sys.exit(main())
