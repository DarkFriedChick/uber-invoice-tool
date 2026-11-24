# -*- coding: utf-8 -*-
"""合成"复选框 + 国旗"单元格图（40x18），供表格第一列使用。

ttk.Treeview 只有树列支持图片，所以把勾选框和国旗拼成一张图；
每个（币种 × 三种状态）组合生成一张，运行时直接查表加载。
"""
import os
from PIL import Image

OUT = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(OUT, "cells")
CHK = {"off": "chk_off.png", "on": "chk_on.png", "dis": "chk_disabled.png"}
FLAGS = ["SAR", "AED", "QAR", "BHD", "KWD", "OMR", "EGP", "USD", "GBP", "EUR", "OTHER"]

W, H, GAP = 40, 18, 4


def compose(chk_path, flag_path):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if os.path.exists(chk_path):
        chk = Image.open(chk_path).convert("RGBA")
        canvas.paste(chk, (0, (H - chk.height) // 2), chk)
    if os.path.exists(flag_path):
        flag = Image.open(flag_path).convert("RGBA")
        canvas.paste(flag, (18 + GAP, (H - flag.height) // 2), flag)
    return canvas


def main():
    os.makedirs(CELLS, exist_ok=True)
    names = []
    for cur in FLAGS:
        for state, chk_name in CHK.items():
            img = compose(os.path.join(OUT, chk_name), os.path.join(OUT, f"flag_{cur}.png"))
            name = f"cell_{cur}_{state}.png"
            img.save(os.path.join(CELLS, name))
            names.append(name)
    print(f"生成 {len(names)} 张单元格图 → {CELLS}")

    # 预览：三状态 × 四个币种
    rows = [("SAR", "off"), ("SAR", "on"), ("SAR", "dis"), ("AED", "on"), ("BHD", "on"), ("USD", "off")]
    prev = Image.new("RGBA", (W + 20, (H + 8) * len(rows)), (255, 255, 255, 255))
    for i, (cur, st) in enumerate(rows):
        im = Image.open(os.path.join(CELLS, f"cell_{cur}_{st}.png"))
        prev.paste(im, (10, (H + 8) * i + 4), im)
    prev.resize((prev.width * 4, prev.height * 4), Image.NEAREST).save(os.path.join(OUT, "cell_preview.png"))


if __name__ == "__main__":
    main()
