# -*- coding: utf-8 -*-
"""自检 v8：表格第一列是否按币种换成"勾选框+国旗"合成图。"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk  # noqa: E402
import uber_tool as U  # noqa: E402

root = tk.Tk()
try:
    app = U.App(root)
    app._demo_fill()
    root.update()
    print("币种 -> 第一列图名")
    for i, t in enumerate(app.trips):
        img = app.tree.item(str(i), "image")
        name = str(img[0]) if img else None
        print(f"  [{i}] {t.currency:4s} {t.amount:>7s} selected={t.selected!s:5s} => {name}")
    # 同一币种不同状态应是两张不同图
    sar_off = app._cell_img("SAR", "off")
    sar_on = app._cell_img("SAR", "on")
    aed_on = app._cell_img("AED", "on")
    print("\nSAR off / SAR on / AED on 互不相同 =",
          len({str(sar_off), str(sar_on), str(aed_on)}) == 3)
    print("未知币种回退 =", str(app._cell_img("XYZ", "on")) == str(app._cell_img("OTHER", "on")))
except Exception:
    traceback.print_exc()
root.after(400, root.destroy)
root.mainloop()
print("closed ok")
