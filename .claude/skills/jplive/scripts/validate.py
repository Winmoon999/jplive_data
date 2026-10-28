#!/usr/bin/env python3
"""驗證 jplive 資料庫（僅使用 Python 標準函式庫）。

用法：
    python scripts/validate.py data/live_events.json
    python scripts/validate.py data/live_events.json --artists data/artists.json

規則來源：schema/live_event.schema.json（結構）＋本檔的語意檢查。
結束碼：0 = 通過（可能有警告）、1 = 有錯誤。
"""
import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "live_event.schema.json"

TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def type_ok(value, t):
    if t == "integer" and isinstance(value, bool):
        return False
    if t == "number" and isinstance(value, bool):
        return False
    return isinstance(value, TYPE_MAP[t])


def check(value, schema, root, path, errors):
    """實作本 schema 用到的 JSON Schema 子集。"""
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return check(value, node, root, path, errors)

    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(type_ok(value, x) for x in types):
            errors.append(f"{path}: 型別應為 {types}，實際為 {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: 值 {value!r} 不在允許範圍 {schema['enum']}")

    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} 不符合格式 {schema['pattern']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: 字串長度不足 {schema['minLength']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: 至少需要 {schema['minItems']} 筆")
        if "items" in schema:
            for i, item in enumerate(value):
                check(item, schema["items"], root, f"{path}[{i}]", errors)

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: 缺少必要欄位 {key}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: 不允許的欄位 {key}")
        for key, sub in props.items():
            if key in value:
                check(value[key], sub, root, f"{path}.{key}", errors)


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def parse_dt(s):
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def semantic_checks(db, artist_ids, errors, warnings):
    seen_ids = set()
    for i, ev in enumerate(db.get("events", [])):
        p = f"events[{i}]"
        eid = ev.get("id")
        if eid in seen_ids:
            errors.append(f"{p}: id 重複 {eid!r}")
        seen_ids.add(eid)
        p = f"{p}({eid})"

        perfs = ev.get("performances", [])
        pids = [x.get("id") for x in perfs]
        if len(pids) != len(set(pids)):
            errors.append(f"{p}: performances 的 id 有重複")

        dates = []
        for j, pf in enumerate(perfs):
            d = parse_date(pf.get("date"))
            if d is None:
                errors.append(f"{p}.performances[{j}]: 日期不是有效的日曆日期 {pf.get('date')!r}")
            else:
                dates.append(d)
            ot, st = pf.get("open_time"), pf.get("start_time")
            if ot and st and ot > st:
                warnings.append(f"{p}.performances[{j}]: 開場時間 {ot} 晚於開演時間 {st}")
            if not pf.get("performers") and ev.get("lineup_complete") is not False:
                warnings.append(f"{p}.performances[{j}]: 沒有出演者，若陣容尚未公布請設 lineup_complete=false")
            for pr in pf.get("performers", []):
                aid = pr.get("artist_id")
                if aid and artist_ids is not None and aid not in artist_ids:
                    warnings.append(f"{p}: performer artist_id {aid!r} 不在 artists.json")

        # id 的日期前綴應等於最早一場的日期
        if dates and eid:
            prefix = eid[:8]
            if prefix != min(dates).strftime("%Y%m%d"):
                warnings.append(f"{p}: id 日期前綴 {prefix} 與最早場次 {min(dates)} 不一致（id 建立後不應更改，若是延期造成請忽略）")

        for aid in ev.get("artist_ids", []):
            if artist_ids is not None and aid not in artist_ids:
                warnings.append(f"{p}: artist_id {aid!r} 不在 artists.json")

        for j, tp in enumerate(ev.get("ticket_phases", [])):
            for ref in tp.get("performance_ids") or []:
                if ref not in pids:
                    errors.append(f"{p}.ticket_phases[{j}]: performance_ids 引用了不存在的 {ref!r}")
            s, e = parse_dt(tp.get("start_at")), parse_dt(tp.get("end_at"))
            if s and e and s > e:
                errors.append(f"{p}.ticket_phases[{j}]: start_at 晚於 end_at")

        # 可信度與來源等級一致
        levels = [s.get("level") for s in ev.get("sources", [])]
        conf = ev.get("confidence")
        if conf == "official" and not any(isinstance(l, int) and l <= 4 for l in levels):
            errors.append(f"{p}: confidence=official 但沒有等級 1–4 的來源")
        if conf == "secondary" and levels and all(isinstance(l, int) and l <= 4 for l in levels):
            warnings.append(f"{p}: 來源皆為官方，confidence 可升為 official")
        if conf == "rumor" and ev.get("status") == "scheduled":
            warnings.append(f"{p}: rumor 不建議寫入資料庫，請確認使用者有要求")

        # 狀態一致性
        if ev.get("status") == "cancelled" and any(x.get("status") == "scheduled" for x in perfs):
            warnings.append(f"{p}: 活動已取消，但仍有場次為 scheduled")
        if ev.get("status") == "scheduled" and perfs and all(x.get("status") == "ended" for x in perfs):
            warnings.append(f"{p}: 所有場次都已結束，活動 status 應改為 ended")
        if ev.get("status") == "scheduled" and dates and max(dates) < date.today():
            warnings.append(f"{p}: 最後場次 {max(dates)} 已過期，status 應更新為 ended")

        fs, lv = parse_dt(ev.get("first_seen_at")), parse_dt(ev.get("last_verified_at"))
        if fs and lv and fs > lv:
            errors.append(f"{p}: first_seen_at 晚於 last_verified_at")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="live_events.json 路徑")
    ap.add_argument("--artists", help="artists.json 路徑（預設：與 db 同資料夾）")
    args = ap.parse_args()

    errors, warnings = [], []
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        db = json.loads(Path(args.db).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[錯誤] 無法讀取或解析 {args.db}: {exc}")
        return 1

    check(db, schema, schema, "$", errors)

    artist_ids = None
    ap_path = Path(args.artists) if args.artists else Path(args.db).parent / "artists.json"
    if ap_path.exists():
        try:
            artists = json.loads(ap_path.read_text(encoding="utf-8"))
            ids = [a.get("id") for a in artists.get("artists", [])]
            artist_ids = set(ids)
            for dup in sorted({i for i in ids if ids.count(i) > 1}, key=str):
                errors.append(f"artists.json: id 重複 {dup!r}")
            for i in ids:
                if not isinstance(i, str) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i):
                    errors.append(f"artists.json: id 格式不正確 {i!r}")
        except json.JSONDecodeError as exc:
            errors.append(f"artists.json 無法解析: {exc}")

    if not errors:
        semantic_checks(db, artist_ids, errors, warnings)

    warnings = list(dict.fromkeys(warnings))  # 去除重複警告並保留順序
    for w in warnings:
        print(f"[警告] {w}")
    for e in errors:
        print(f"[錯誤] {e}")
    n = len(db.get("events", [])) if isinstance(db, dict) else 0
    print(f"檢查完成：{n} 筆活動，{len(errors)} 個錯誤，{len(warnings)} 個警告")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
