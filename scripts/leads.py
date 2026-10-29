#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""leads.py — 线索台账：追加、去重、改状态、汇总。

用法:
    python leads.py add --number +60123456789 --nick SkyWhisper --time "昨天23:51" \
        --region 广东 --source "https://www.xiaohongshu.com/explore/xxxx"
    python leads.py import leads_raw.csv
    python leads.py status --number +60123456789 --to sent
    python leads.py list --status sent
    python leads.py stats

台账字段：号码, 昵称, 来源帖, 评论时间, 地区, 渠道, 状态, 发送时间, 备注
状态取值：new / verified / sent / replied / agreed / refused / no_whatsapp / dead
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

FIELDS = ["号码", "昵称", "来源帖", "评论时间", "地区", "渠道",
          "状态", "发送时间", "最后更新", "备注"]
DEFAULT_PATH = "leads.csv"
STATUSES = ("new", "verified", "sent", "replied", "agreed", "refused", "no_whatsapp", "dead")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def save(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def upsert(rows: list[dict], rec: dict) -> bool:
    """号码已存在则只补空字段，返回是否是新增。"""
    for row in rows:
        if row["号码"] == rec["号码"]:
            for k, v in rec.items():
                if v and not row.get(k):
                    row[k] = v
            row["最后更新"] = now()
            return False
    rec.setdefault("状态", "new")
    rec["最后更新"] = now()
    rows.append({k: rec.get(k, "") for k in FIELDS})
    return True


def cmd_add(args) -> None:
    rows = load(args.file)
    rec = {"号码": args.number, "昵称": args.nick, "来源帖": args.source,
           "评论时间": args.time, "地区": args.region, "渠道": args.channel,
           "备注": args.note}
    added = upsert(rows, rec)
    save(args.file, rows)
    print(("已新增 " if added else "已存在，已合并 ") + args.number)


def cmd_import(args) -> None:
    rows = load(args.file)
    added = merged = 0
    with open(args.csv, "r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            number = (row.get("号码") or "").strip()
            if not number:
                continue
            rec = {"号码": number, "昵称": row.get("昵称", ""),
                   "评论时间": row.get("时间", ""), "地区": row.get("地区", ""),
                   "渠道": row.get("类型", ""), "备注": row.get("备注", "")}
            if upsert(rows, rec):
                added += 1
            else:
                merged += 1
    save(args.file, rows)
    print(f"导入完成：新增 {added}，合并 {merged}，台账共 {len(rows)} 条")


def cmd_status(args) -> None:
    if args.to not in STATUSES:
        print(f"状态必须是 {STATUSES} 之一", file=sys.stderr)
        sys.exit(1)
    rows = load(args.file)
    hit = 0
    for row in rows:
        if row["号码"] == args.number:
            row["状态"] = args.to
            row["最后更新"] = now()
            if args.to == "sent" and not row.get("发送时间"):
                row["发送时间"] = now()
            if args.note:
                row["备注"] = args.note
            hit += 1
    if not hit:
        print(f"台账里没有 {args.number}", file=sys.stderr)
        sys.exit(2)
    save(args.file, rows)
    print(f"{args.number} -> {args.to}")


def cmd_list(args) -> None:
    rows = load(args.file)
    if args.status:
        rows = [r for r in rows if r.get("状态") == args.status]
    if not rows:
        print("（空）")
        return
    width = max(len(r["号码"]) for r in rows) + 2
    print(f"{'号码':<{width}}{'状态':<12}{'昵称':<16}{'评论时间':<14}{'地区'}")
    print("-" * (width + 52))
    for r in rows:
        print(f"{r['号码']:<{width}}{r.get('状态',''):<12}{r.get('昵称','')[:15]:<16}"
              f"{r.get('评论时间',''):<14}{r.get('地区','')}")


def cmd_stats(args) -> None:
    rows = load(args.file)
    if not rows:
        print("台账为空")
        return
    counter: dict[str, int] = {}
    for r in rows:
        counter[r.get("状态", "") or "new"] = counter.get(r.get("状态", "") or "new", 0) + 1
    print(f"台账共 {len(rows)} 条（{args.file}）")
    for status in STATUSES:
        if status in counter:
            print(f"  {status:<12}{counter[status]}")
    sent = counter.get("sent", 0) + counter.get("replied", 0) + counter.get("agreed", 0)
    if sent:
        reply = counter.get("replied", 0) + counter.get("agreed", 0)
        print(f"\n已发送 {sent} 条，其中回复 {reply} 条，回复率 {reply / sent:.0%}")
    print("\n提醒：单晚新增陌生会话不要超过 5 个（见 references/risk-control.md）")


def main() -> None:
    ap = argparse.ArgumentParser(description="线索台账管理")
    ap.add_argument("--file", default=DEFAULT_PATH, help=f"台账路径，默认 {DEFAULT_PATH}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="新增或合并一条线索")
    p.add_argument("--number", required=True)
    p.add_argument("--nick", default="")
    p.add_argument("--time", default="")
    p.add_argument("--region", default="")
    p.add_argument("--source", default="")
    p.add_argument("--channel", default="明文")
    p.add_argument("--note", default="")

    p = sub.add_parser("import", help="从 extract_contacts 的输出导入")
    p.add_argument("csv")

    p = sub.add_parser("status", help="更新状态")
    p.add_argument("--number", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--note", default="")

    p = sub.add_parser("list", help="列出线索")
    p.add_argument("--status", default="")

    sub.add_parser("stats", help="汇总统计")

    args = ap.parse_args()
    {"add": cmd_add, "import": cmd_import, "status": cmd_status,
     "list": cmd_list, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()
