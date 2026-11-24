# -*- coding: utf-8 -*-
"""生成货币对应国家的小国旗位图（简化版，18x12），用于总计栏。

Windows 不渲染国旗 emoji，所以自己画。只画常见的几种，其余用灰底占位。
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
W, H = 18, 12
SS = 6
SW, SH = W * SS, H * SS

# emoji 里国旗的"等价物"：用简化色块表达，够辨识就行
# 颜色取自各国国旗主色
GREEN_SA = (0, 122, 61)
RED_AE = (255, 0, 0)
GREEN_AE = (0, 115, 47)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MAROON_QA = (139, 0, 0)
RED_BH = (206, 17, 38)
RED_KW = (0, 122, 61)
GOLD = (198, 160, 60)
BLUE_EU = (0, 51, 153)
YELLOW = (255, 204, 0)


def base(w=SW, h=SH, color=WHITE):
    img = Image.new("RGBA", (w, h), color + (255,))
    return img, ImageDraw.Draw(img)


def finish(img, name):
    img = img.resize((W, H), Image.LANCZOS)
    # 圆角裁切，避免方角太硬
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=2, fill=255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    out.save(f"{OUT}\\flag_{name}.png")


def flag_sa():
    img, d = base(color=GREEN_SA)
    d.rectangle([SW * 0.10, SH * 0.22, SW * 0.86, SH * 0.30], fill=WHITE)   # 清真言条
    d.rectangle([SW * 0.10, SH * 0.62, SW * 0.74, SH * 0.70], fill=WHITE)   # 剑身
    d.polygon([(SW * 0.74, SH * 0.58), (SW * 0.88, SH * 0.66),
               (SW * 0.74, SH * 0.74)], fill=WHITE)                          # 剑尖
    return img


def flag_ae():
    img, d = base()
    d.rectangle([0, 0, SW, SH * 0.34], fill=GREEN_AE)
    d.rectangle([0, SH * 0.34, SW, SH * 0.67], fill=WHITE)
    d.rectangle([0, SH * 0.67, SW, SH], fill=BLACK)
    d.rectangle([0, 0, SW * 0.28, SH], fill=RED_AE)
    return img


def flag_qa():
    img, d = base(color=MAROON_QA)
    d.rectangle([0, 0, SW * 0.30, SH], fill=WHITE)
    teeth = 5
    step = SH / teeth
    for i in range(teeth):
        y0 = i * step
        d.polygon([(SW * 0.30, y0), (SW * 0.46, y0 + step / 2), (SW * 0.30, y0 + step)], fill=WHITE)
    return img


def flag_bh():
    img, d = base(color=WHITE)
    d.rectangle([SW * 0.30, 0, SW, SH], fill=RED_BH)
    teeth = 5
    step = SH / teeth
    for i in range(teeth):
        y0 = i * step
        d.polygon([(SW * 0.30, y0), (SW * 0.16, y0 + step / 2), (SW * 0.30, y0 + step)], fill=RED_BH)
    return img


def flag_kw():
    img, d = base()
    d.rectangle([0, 0, SW, SH * 0.34], fill=GREEN_SA)
    d.rectangle([0, SH * 0.34, SW, SH * 0.67], fill=WHITE)
    d.rectangle([0, SH * 0.67, SW, SH], fill=RED_BH)
    d.polygon([(0, 0), (SW * 0.26, 0), (SW * 0.26, SH), (0, SH),
               (SW * 0.12, SH * 0.5)], fill=BLACK)
    return img


def flag_om():
    img, d = base()
    d.rectangle([0, 0, SW, SH * 0.34], fill=WHITE)
    d.rectangle([0, SH * 0.34, SW, SH * 0.67], fill=RED_BH)
    d.rectangle([0, SH * 0.67, SW, SH], fill=GREEN_SA)
    d.rectangle([0, 0, SW * 0.24, SH], fill=RED_BH)
    return img


def flag_eg():
    img, d = base()
    d.rectangle([0, 0, SW, SH * 0.34], fill=(206, 17, 38))
    d.rectangle([0, SH * 0.34, SW, SH * 0.67], fill=WHITE)
    d.rectangle([0, SH * 0.67, SW, SH], fill=BLACK)
    d.ellipse([SW * 0.44, SH * 0.42, SW * 0.56, SH * 0.58], fill=GOLD)
    return img


def flag_us():
    img, d = base()
    for i in range(7):
        d.rectangle([0, SH * i / 6.5, SW, SH * (i + 0.55) / 6.5], fill=(178, 34, 52))
    d.rectangle([0, 0, SW * 0.45, SH * 0.55], fill=(60, 59, 110))
    return img


def flag_gb():
    img, d = base(color=(1, 33, 105))
    d.line([(0, 0), (SW, SH)], fill=WHITE, width=int(SH * 0.16))
    d.line([(0, SH), (SW, 0)], fill=WHITE, width=int(SH * 0.16))
    d.rectangle([SW * 0.42, 0, SW * 0.58, SH], fill=WHITE)
    d.rectangle([0, SH * 0.40, SW, SH * 0.60], fill=WHITE)
    d.rectangle([SW * 0.46, 0, SW * 0.54, SH], fill=(200, 16, 46))
    d.rectangle([0, SH * 0.45, SW, SH * 0.55], fill=(200, 16, 46))
    return img


def flag_eu():
    img, d = base(color=BLUE_EU)
    d.ellipse([SW * 0.30, SH * 0.22, SW * 0.70, SH * 0.78], outline=YELLOW, width=int(SH * 0.06))
    return img


def flag_other(letter="•"):
    img, d = base(color=(150, 163, 184))
    d.rectangle([SW * 0.34, SH * 0.28, SW * 0.66, SH * 0.72], fill=WHITE)
    return img


FLAGS = {
    "SAR": flag_sa,
    "AED": flag_ae,
    "QAR": flag_qa,
    "BHD": flag_bh,
    "KWD": flag_kw,
    "OMR": flag_om,
    "EGP": flag_eg,
    "USD": flag_us,
    "GBP": flag_gb,
    "EUR": flag_eu,
}

if __name__ == "__main__":
    for code, fn in FLAGS.items():
        finish(fn(), code)
    finish(flag_other(), "OTHER")
    # 预览
    prev = Image.new("RGBA", (W * (len(FLAGS) + 1) + 10 * (len(FLAGS) + 2), H + 20), (255, 255, 255, 255))
    x = 8
    for code in list(FLAGS) + ["OTHER"]:
        im = Image.open(f"{OUT}\\flag_{code}.png")
        prev.paste(im, (x, 12), im)
        x += W + 10
    prev.resize((prev.width * 4, prev.height * 4), Image.NEAREST).save(f"{OUT}\\flag_preview.png")
    print("flags:", list(FLAGS) + ["OTHER"])
