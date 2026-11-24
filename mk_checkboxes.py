# -*- coding: utf-8 -*-
"""生成表格用的复选框位图（未选 / 选中 / 禁用），输出 18px PNG。

用 4 倍超采样再缩，边缘才干净；运行时只用 tk.PhotoImage 加载，不需要 Pillow。
"""
import os

from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
SIZE = 18
SS = 4          # 超采样倍数
S = SIZE * SS

BORDER = (154, 167, 184, 255)     # 未选：灰边框
BLUE = (26, 115, 232, 255)        # 选中：Win11 强调蓝
DIS_BG = (240, 243, 248, 255)     # 禁用：浅灰底
DIS_BD = (207, 214, 224, 255)


def canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def draw_off():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([SS, SS, S - SS - 1, S - SS - 1], radius=int(S * 0.16),
                        fill=(255, 255, 255, 255), outline=BORDER,
                        width=max(2, int(S * 0.055)))
    return img


def draw_on():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([SS, SS, S - SS - 1, S - SS - 1], radius=int(S * 0.16), fill=BLUE)
    d.line([(S * 0.26, S * 0.52), (S * 0.43, S * 0.70), (S * 0.75, S * 0.32)],
           fill=(255, 255, 255, 255), width=max(3, int(S * 0.10)), joint="curve")
    return img


def draw_disabled():
    img = canvas()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([SS, SS, S - SS - 1, S - SS - 1], radius=int(S * 0.16),
                        fill=DIS_BG, outline=DIS_BD, width=max(2, int(S * 0.055)))
    d.line([(S * 0.32, S * 0.50), (S * 0.68, S * 0.50)], fill=(190, 198, 210, 255),
           width=max(2, int(S * 0.055)))
    return img


def save(img, name):
    img.resize((SIZE, SIZE), Image.LANCZOS).save(f"{OUT}\\{name}")


if __name__ == "__main__":
    save(draw_off(), "chk_off.png")
    save(draw_on(), "chk_on.png")
    save(draw_disabled(), "chk_disabled.png")
    # 预览：三态并排放大，方便肉眼验
    prev = Image.new("RGBA", (SIZE * 3 + 24, SIZE + 16), (255, 255, 255, 255))
    for i, img in enumerate((draw_off(), draw_on(), draw_disabled())):
        prev.paste(img.resize((SIZE, SIZE), Image.LANCZOS), (6 + i * (SIZE + 6), 8), 
                   img.resize((SIZE, SIZE), Image.LANCZOS))
    prev.resize((prev.width * 6, prev.height * 6), Image.NEAREST).save(f"{OUT}\\chk_preview.png")
    print("checkbox png written")
