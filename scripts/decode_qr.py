#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decode_qr.py — 多策略二维码解码，专门用来处理评论区里的手机截图。

用法:
    python decode_qr.py 图片1.jpg [图片2.jpg ...]
    python decode_qr.py --dir ~/Downloads --glob "*小红书*"

输出每种成功解码的 payload。只做解码，不联网、不解析号码。
"""
from __future__ import annotations

import argparse
import glob as globmod
import os
import sys

import cv2
import numpy as np


def _variants(img: np.ndarray):
    """由粗到细构造待测图，先便宜的、成功率高的。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    yield "原图", img
    yield "灰度", gray
    yield "灰度+Otsu", cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    big = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    yield "灰度x2", big
    sharpen = cv2.filter2D(big, -1, np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]]))
    yield "灰度x2+锐化", sharpen


def _center_crop(img: np.ndarray):
    """截图里二维码常在中间偏下，裁一刀往往能救回被边框干扰的图。"""
    h, w = img.shape[:2]
    for top, bottom in ((0.05, 0.95), (0.20, 0.85), (0.30, 0.80)):
        yield f"裁剪{int(top*100)}-{int(bottom*100)}", img[int(h * top):int(h * bottom), :]


def decode_image(img: np.ndarray) -> list[str]:
    det = cv2.QRCodeDetector()
    found: list[str] = []
    seen: set[str] = set()

    def collect(tag: str, data: str) -> bool:
        if data and data not in seen:
            seen.add(data)
            found.append(data)
            print(f"    [{tag}] -> {data}")
            return True
        return False

    for name, variant in _variants(img):
        ok = False
        try:
            data, _pts, _ = det.detectAndDecode(variant)
            ok = collect(f"{name}/single", data) or ok
        except cv2.error as exc:
            print(f"    {name}/single 失败: {exc}")
        try:
            success, infos, _pts, _ = det.detectAndDecodeMulti(variant)
            if success:
                for info in infos:
                    ok = collect(f"{name}/multi", info) or ok
        except cv2.error:
            pass
        if ok:
            return found  # 已拿到，不必继续加码

    # 兜底：裁剪后重试
    for name, cropped in _center_crop(img):
        for vname, variant in _variants(cropped):
            try:
                data, _pts, _ = det.detectAndDecode(variant)
                if collect(f"{name}+{vname}", data):
                    return found
            except cv2.error:
                pass
    return found


def run(path: str) -> list[str]:
    print(f"\n=== {os.path.basename(path)} ===")
    # 用 imdecode + fromfile，兼容中文路径（cv2.imread 在 Windows 上会挂）
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except OSError as exc:
        print(f"    读取失败: {exc}")
        return []
    if img is None:
        print("    不是有效图片")
        return []
    h, w = img.shape[:2]
    print(f"    尺寸 {w}x{h}  大小 {os.path.getsize(path) // 1024}KB")

    found = decode_image(img)
    if not found:
        print("    未识别：可能是缩略图、遮挡或已过期，换原图/换裁剪重试")
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="多策略二维码解码")
    ap.add_argument("images", nargs="*", help="图片路径（可多个）")
    ap.add_argument("--dir", help="在该目录下按 --glob 搜索图片")
    ap.add_argument("--glob", dest="pattern", default="*.jpg", help="与 --dir 搭配，默认 *.jpg")
    args = ap.parse_args()

    targets = list(args.images)
    if args.dir:
        targets += sorted(globmod.glob(os.path.join(os.path.expanduser(args.dir), args.pattern)),
                          key=os.path.getmtime, reverse=True)
    if not targets:
        ap.print_help()
        sys.exit(1)

    for path in targets:
        run(path)


if __name__ == "__main__":
    main()
