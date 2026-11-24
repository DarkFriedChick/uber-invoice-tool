# -*- coding: utf-8 -*-
"""生成程序图标：蓝底圆角 + 白色小票 + 绿色对勾。输出 icon.ico（多尺寸）与预览图。"""
import os

from PIL import Image, ImageDraw

OUT = os.path.dirname(os.path.abspath(__file__))
S = 1024  # 超采样


def rounded_rect_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def gradient(size, top, bottom):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (size, y)], fill=c)
    return img


def main():
    # 背景：圆角 + 竖向渐变
    bg = gradient(S, (13, 88, 200), (74, 158, 240))
    mask = rounded_rect_mask(S, int(S * 0.22))
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    base.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(base)

    # 小票：白色圆角矩形 + 底部锯齿（用蒙版抠形，避免直接画透明色）
    left, right = int(S * 0.27), int(S * 0.73)
    top, bottom = int(S * 0.17), int(S * 0.80)
    receipt_mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(receipt_mask)
    md.rounded_rectangle([left, top, right, bottom], radius=int(S * 0.045), fill=255)
    teeth = 5
    w = (right - left) / (teeth * 2)
    zig = int(S * 0.038)
    for i in range(teeth):
        x0 = left + i * 2 * w
        md.polygon([(x0, bottom - zig), (x0 + w, bottom + int(S * 0.02)), (x0 + 2 * w, bottom - zig)],
                   fill=0)
    white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    base.paste(white, (0, 0), receipt_mask)

    # 票面文字线
    line_color = (150, 178, 214, 255)
    lx0, lx1 = left + int(S * 0.055), right - int(S * 0.055)
    y = top + int(S * 0.085)
    for i, frac in enumerate((1.0, 0.72, 0.9, 0.55)):
        d.rounded_rectangle([lx0, y, lx0 + int((lx1 - lx0) * frac), y + int(S * 0.022)],
                            radius=int(S * 0.011), fill=line_color)
        y += int(S * 0.062)

    # 金额条（更粗、更深一点）
    d.rounded_rectangle([lx0, y + int(S * 0.01), lx0 + int((lx1 - lx0) * 0.45), y + int(S * 0.036)],
                        radius=int(S * 0.014), fill=(90, 138, 200, 255))

    # 绿色对勾徽章
    cs = int(S * 0.30)
    cx, cy = int(S * 0.755), int(S * 0.775)
    d.ellipse([cx - cs // 2, cy - cs // 2, cx + cs // 2, cy + cs // 2],
              fill=(255, 255, 255, 255))
    d.ellipse([cx - cs // 2 + int(S * 0.018), cy - cs // 2 + int(S * 0.018),
               cx + cs // 2 - int(S * 0.018), cy + cs // 2 - int(S * 0.018)],
              fill=(22, 163, 74, 255))
    d.line([(cx - int(cs * 0.22), cy + int(cs * 0.02)),
            (cx - int(cs * 0.05), cy + int(cs * 0.19)),
            (cx + int(cs * 0.24), cy - int(cs * 0.18))],
           fill=(255, 255, 255, 255), width=max(3, int(S * 0.028)), joint="curve")

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    base.save(os.path.join(OUT, "icon.ico"), sizes=sizes)
    base.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "icon_preview.png"))
    base.resize((32, 32), Image.LANCZOS).resize((128, 128), Image.NEAREST).save(
        os.path.join(OUT, "icon_small_preview.png"))
    print("icon.ico written:", [f"{w}x{h}" for w, h in sizes])


if __name__ == "__main__":
    main()
