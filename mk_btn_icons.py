# -*- coding: utf-8 -*-
"""生成工具条按钮的彩色图标（16px）：绿色对勾 / 红色叉 / 琥珀色清空。"""
import os

from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
SIZE = 16
SS = 4
S = SIZE * SS

SPECS = {
    "btn_all.png": ((34, 139, 74, 255), "check"),
    "btn_none.png": ((200, 62, 54, 255), "cross"),
    "btn_clear.png": ((214, 138, 24, 255), "eraser"),
}


def draw(kind, color):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(S * 0.04)
    d.ellipse([pad, pad, S - pad - 1, S - pad - 1], fill=color)

    w = max(2, int(S * 0.085))
    if kind == "check":
        d.line([(S * 0.27, S * 0.52), (S * 0.44, S * 0.69), (S * 0.74, S * 0.33)],
               fill=(255, 255, 255, 255), width=w, joint="curve")
    elif kind == "cross":
        d.line([(S * 0.32, S * 0.32), (S * 0.68, S * 0.68)],
               fill=(255, 255, 255, 255), width=w, joint="curve")
        d.line([(S * 0.68, S * 0.32), (S * 0.32, S * 0.68)],
               fill=(255, 255, 255, 255), width=w, joint="curve")
    else:  # 清空：白色垃圾桶（描边版，小尺寸下更清楚）
        w = max(2, int(S * 0.055))
        white = (255, 255, 255, 255)
        d.line([(S * 0.25, S * 0.30), (S * 0.75, S * 0.30)], fill=white, width=w)
        d.line([(S * 0.42, S * 0.21), (S * 0.58, S * 0.21)], fill=white, width=w)
        d.line([(S * 0.33, S * 0.37), (S * 0.37, S * 0.77)], fill=white, width=w)
        d.line([(S * 0.67, S * 0.37), (S * 0.63, S * 0.77)], fill=white, width=w)
        d.line([(S * 0.37, S * 0.77), (S * 0.63, S * 0.77)], fill=white, width=w)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


if __name__ == "__main__":
    for name, (color, kind) in SPECS.items():
        draw(kind, color).save(f"{OUT}\\{name}")
    # 预览：放大 8 倍并排
    prev = Image.new("RGBA", (SIZE * 3 + 32, SIZE + 16), (255, 255, 255, 255))
    for i, (name, (color, kind)) in enumerate(SPECS.items()):
        img = draw(kind, color)
        prev.paste(img, (8 + i * (SIZE + 8), 8), img)
    prev.resize((prev.width * 8, prev.height * 8), Image.NEAREST).save(f"{OUT}\\btn_preview.png")
    print("btn icons written:", list(SPECS))
