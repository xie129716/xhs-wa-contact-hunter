#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_contacts.py — 从文本/CSV 里抽出联系方式并规范化去重。

用法:
    # 一行一条评论，字段用 | 分隔：昵称|时间|地区|正文
    python extract_contacts.py comments.txt --out leads_raw.csv

    # 直接扫多份 CSV 的每一列
    python extract_contacts.py *.csv --out merged.csv

输出列：号码, 类型, 原始片段, 昵称, 时间, 地区, 备注
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

# 国际号：+xx / 00xx 开头，允许空格、横线、点、括号
RE_INTL = re.compile(r"(?:\+|00)\d[\d\s\-().]{6,18}\d")
# 中国大陆手机号（带 86 前缀但没写 +）
RE_CN86 = re.compile(r"(?<!\d)861[3-9]\d{9}(?!\d)")
# 中国大陆手机号（无国家码）
RE_CN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
# wa.me 短链
RE_WAME = re.compile(r"https?://wa\.me/(\d{6,15})", re.I)
# 微信提示词（号码需人工确认，避免误抓）
RE_WECHAT = re.compile(r"(?:微信|VX|vx|V信|威信)\s*[:：]?\s*([A-Za-z][-_A-Za-z0-9]{5,19})")

# 已知国家码前缀，用于判定「这是国际号」
CC = {
    "1": "US/CA", "7": "RU/KZ", "20": "EG", "27": "ZA", "31": "NL", "33": "FR",
    "34": "ES", "39": "IT", "44": "GB", "49": "DE", "52": "MX", "55": "BR",
    "60": "MY", "62": "ID", "63": "PH", "65": "SG", "66": "TH", "81": "JP",
    "82": "KR", "84": "VN", "86": "CN", "90": "TR", "91": "IN", "852": "HK",
    "853": "MO", "886": "TW", "971": "AE", "972": "IL", "966": "SA",
}


def norm(raw: str) -> tuple[str, str] | None:
    """把原始片段规范化成 (+CCxxxxxxxxxx, 国家/地区)。"""
    digits = re.sub(r"\D", "", raw)
    if not (7 <= len(digits) <= 15):
        return None
    if len(set(digits)) <= 2:      # 1111111 / 88888888 之类
        return None
    if not raw.strip().startswith(("+", "00")):
        # 无加号但写了 86 前缀：8613012345678
        if len(digits) == 13 and digits.startswith("86") and re.fullmatch(r"1[3-9]\d{9}", digits[2:]):
            return f"+{digits}", "CN"
        # 无国家码：只接受中国大陆手机号形态
        if re.fullmatch(r"1[3-9]\d{9}", digits):
            return f"+86{digits}", "CN"
        return None

    had_plus = raw.strip().startswith(("+", "00"))
    cc, rest = "", digits
    if had_plus:
        for length in (3, 2, 1):
            head = digits[:length]
            if head in CC:
                cc, rest = head, digits[length:]
                break
    if not cc:
        return None
    if not (6 <= len(rest) <= 12):
        return None
    return f"+{cc}{rest}", CC.get(cc, cc)


def parse_line(line: str) -> dict:
    parts = [p.strip() for p in line.split("|")]
    rec = {"昵称": "", "时间": "", "地区": "", "正文": line.strip()}
    if len(parts) >= 4:
        rec["昵称"], rec["时间"], rec["地区"] = parts[0], parts[1], parts[2]
        rec["正文"] = "|".join(parts[3:])
    return rec


def harvest(text: str) -> list[tuple[str, str, str]]:
    """返回 [(号码, 类型, 原始片段)]。"""
    out: list[tuple[str, str, str]] = []
    consumed: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e in consumed)

    for m in RE_WAME.finditer(text):
        out.append((f"+{m.group(1)}", "wa.me", m.group(0)))
        consumed.append((m.start(), m.end()))

    for regex, kind in ((RE_INTL, "intl"), (RE_CN86, "cn86"), (RE_CN, "cn")):
        for m in regex.finditer(text):
            if not free(m.start(), m.end()):
                continue
            normed = norm(m.group(0))
            if not normed:
                continue
            number, country = normed
            if any(number == o[0] for o in out):
                continue
            out.append((number, f"{kind}/{country}", m.group(0).strip()))
            consumed.append((m.start(), m.end()))

    for m in RE_WECHAT.finditer(text):
        out.append((m.group(1), "wechat", m.group(0)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="抽取联系方式并去重")
    ap.add_argument("inputs", nargs="+", help="文本或 CSV 文件")
    ap.add_argument("--out", default="leads_raw.csv")
    ap.add_argument("--encoding", default="utf-8-sig")
    args = ap.parse_args()

    rows: list[dict] = []
    seen: set[str] = set()

    for path in args.inputs:
        if not os.path.exists(path):
            print(f"跳过（不存在）: {path}", file=sys.stderr)
            continue
        with open(path, "r", encoding=args.encoding, errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = parse_line(line)
                for number, kind, raw in harvest(line):
                    if number in seen:
                        continue
                    seen.add(number)
                    rows.append({
                        "号码": number, "类型": kind, "原始片段": raw,
                        "昵称": rec["昵称"], "时间": rec["时间"],
                        "地区": rec["地区"], "备注": "",
                        "来源": os.path.basename(path),
                    })

    with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["号码", "类型", "原始片段", "昵称", "时间", "地区", "备注", "来源"])
        w.writeheader()
        w.writerows(rows)

    print(f"抽出 {len(rows)} 条唯一联系方式 -> {args.out}")
    by_type: dict[str, int] = {}
    for r in rows:
        key = r["类型"].split("/")[0]
        by_type[key] = by_type.get(key, 0) + 1
    for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {k:8s} {v}")


if __name__ == "__main__":
    main()
