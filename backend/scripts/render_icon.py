"""生成桌面应用使用的多尺寸品牌图标资源。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

# 生成桌面品牌资源时使用的仓库根目录。
REPO_ROOT = Path(__file__).resolve().parents[2]
# 图标脚本默认写入资源文件的目标目录。
DEFAULT_OUT = REPO_ROOT / "desktop" / "build"

# 将逻辑图标网格换算为最终画布像素的缩放倍数。
S = 8  # 128 网格 → 1024 画布

# ── 几何（128 网格；与 icon.svg 保持一致） ─────────────────────────
# 品牌图标中圆角底板的逻辑边界。
TILE = (6, 6, 122, 122)          # 磁贴
# 品牌图标底板使用的逻辑圆角半径。
TILE_R = 30
# 取景框线条的逻辑描边宽度。
BR_STROKE = 10                   # 取景框描边
# 根据取景框描边宽度计算的半宽。
BR_CAP = BR_STROKE / 2
# 品牌字母 Y 的逻辑描边宽度。
Y_STROKE = 12                    # Y 描边
# 根据字母描边宽度计算的半宽。
Y_CAP = Y_STROKE / 2

# 取景框左上角竖向线段的端点。
TL_V = ((24, 58), (24, 40))      # 左上：竖段
# 取景框左上角圆弧的中心、半径和角度。
TL_ARC = ((40, 40), 16, 180, 270)  # 左上：圆角
# 取景框左上角横向线段的端点。
TL_H = ((40, 24), (58, 24))      # 左上：横段
# 取景框右下角竖向线段的端点。
BR_V = ((104, 70), (104, 88))
# 取景框右下角圆弧的中心、半径和角度。
BR_ARC = ((88, 88), 16, 0, 90)
# 取景框右下角横向线段的端点。
BR_H = ((88, 104), (70, 104))

# 品牌字母 Y 的两条上臂坐标。
Y_ARM = ((45, 40), (64, 61), (83, 40))
# 品牌字母 Y 的竖直主干坐标。
Y_STEM = ((64, 61), (64, 88))

# 品牌图标背景渐变的上端墨色。
INK_TOP = (27, 37, 50, 255)      # #1B2532
# 品牌图标背景渐变的下端墨色。
INK_BOT = (12, 18, 27, 255)      # #0C121B
# 取景框线条使用的浅蓝灰颜色。
BR_COLOR = (167, 184, 204, 255)  # #A7B8CC
# 品牌字母渐变的上端琥珀色。
AMBER_TOP = (255, 194, 71, 255)  # #FFC247
# 品牌字母渐变的下端琥珀色。
AMBER_BOT = (242, 147, 17, 255)  # #F29311


def px(v: float) -> float:
    """把逻辑设计坐标按图标缩放比例换算为像素坐标。

    Args:
        v: 逻辑图标网格中的坐标或尺寸数值。

    Returns:
        按全局缩放倍数换算后的像素坐标或尺寸。
    """

    return v * S


def gradient(size: int, top: tuple, bottom: tuple, x1: float, y1: float, x2: float, y2: float) -> Image.Image:
    """生成指定尺寸和颜色端点之间的 RGBA 渐变图。

    Args:
        size: 输出图像的边长。
        top: 渐变起始 RGBA 颜色。
        bottom: 渐变结束 RGBA 颜色。
        x1: 渐变向量起点的横坐标。
        y1: 渐变向量起点的纵坐标。
        x2: 渐变向量终点的横坐标。
        y2: 渐变向量终点的纵坐标。

    Returns:
        按指定方向插值生成的 RGBA 渐变图像。
    """

    import numpy as np

    axis = np.linspace(0, 1, size, dtype=np.float32)
    xs, ys = np.meshgrid(axis, axis)
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy or 1.0
    t = np.clip(((xs - x1) * dx + (ys - y1) * dy) / denom, 0.0, 1.0)
    top_a = np.array(top, dtype=np.float32)
    bot_a = np.array(bottom, dtype=np.float32)
    arr = top_a[None, None, :] + (bot_a - top_a)[None, None, :] * t[:, :, None]
    return Image.fromarray(arr.round().astype("uint8"), "RGBA")


def draw_shape_mask(size: int) -> Image.Image:
    """绘制用于限制图标内容范围的圆角取景框遮罩。

    Args:
        size: 输出遮罩的边长。

    Returns:
        仅包含取景框和字母图形的灰度遮罩。
    """

    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    w_br = px(BR_STROKE)
    w_y = px(Y_STROKE)

    def line(a, b, w):
        d.line([px(a[0]), px(a[1]), px(b[0]), px(b[1])], fill=255, width=round(w))
        for p in (a, b):  # 圆头
            r = w / 2
            d.ellipse([px(p[0]) - r, px(p[1]) - r, px(p[0]) + r, px(p[1]) + r], fill=255)

    # 取景框：两段断角
    line(TL_V[0], TL_V[1], w_br)
    line(TL_H[0], TL_H[1], w_br)
    cx, cy = TL_ARC[0]
    r = TL_ARC[1]
    d.arc([px(cx - r), px(cy - r), px(cx + r), px(cy + r)], TL_ARC[2], TL_ARC[3], fill=255, width=round(w_br))

    line(BR_V[0], BR_V[1], w_br)
    line(BR_H[0], BR_H[1], w_br)
    cx, cy = BR_ARC[0]
    r = BR_ARC[1]
    d.arc([px(cx - r), px(cy - r), px(cx + r), px(cy + r)], BR_ARC[2], BR_ARC[3], fill=255, width=round(w_br))

    # 品牌字母 Y 的图形遮罩。
    line(Y_ARM[0], Y_ARM[1], w_y)
    line(Y_ARM[1], Y_ARM[2], w_y)
    line(Y_STEM[0], Y_STEM[1], w_y)
    return m


def render_icon(size: int) -> Image.Image:
    """按给定尺寸合成品牌底色、描边和字母图形。

    Args:
        size: 输出图标的边长。

    Returns:
        合成后的 RGBA 品牌图标。
    """

    base = 1024

    # 磁贴（垂直墨色渐变）
    ink = gradient(base, INK_TOP, INK_BOT, 6 / 128, 6 / 128, 46.6 / 128, 122 / 128)
    tile_mask = Image.new("L", (base, base), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        [px(TILE[0]), px(TILE[1]), px(TILE[2]), px(TILE[3])], radius=px(TILE_R), fill=255
    )
    tile = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    tile.paste(ink, (0, 0), tile_mask)

    # 磁贴内发丝高光（单独一层后合成，避免 ImageDraw 直接覆盖 alpha）
    hair = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    ImageDraw.Draw(hair).rounded_rectangle(
        [px(6.75), px(6.75), px(121.25), px(121.25)],
        radius=px(29.25),
        outline=(255, 255, 255, 23),
        width=round(px(1.5)),
    )
    tile = Image.alpha_composite(tile, hair)

    # 取景框（单色）
    br_mask = draw_shape_mask(base)
    br_layer = Image.new("RGBA", (base, base), BR_COLOR)
    tile.paste(br_layer, (0, 0), br_mask)

    # Y（琥珀渐变，仅覆盖 Y 区域）
    y_only = Image.new("L", (base, base), 0)
    yd = ImageDraw.Draw(y_only)

    def yline(a, b):
        yd.line([px(a[0]), px(a[1]), px(b[0]), px(b[1])], fill=255, width=round(px(Y_STROKE)))
        for p in (a, b):
            r = px(Y_CAP)
            yd.ellipse([px(p[0]) - r, px(p[1]) - r, px(p[0]) + r, px(p[1]) + r], fill=255)

    yline(Y_ARM[0], Y_ARM[1])
    yline(Y_ARM[1], Y_ARM[2])
    yline(Y_STEM[0], Y_STEM[1])
    amber = gradient(base, AMBER_TOP, AMBER_BOT, 22 / 128, 12 / 128, 102 / 128, 112 / 128)
    tile.paste(amber, (0, 0), y_only)

    return tile.resize((size, size), Image.LANCZOS) if size != base else tile


def main() -> None:
    """启动当前模块提供的命令行流程。"""

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)

    master = render_icon(1024)
    master.save(out / "icon-1024.png")
    for n in (512, 256, 128, 64, 48, 32, 24, 16):
        render_icon(n).save(out / f"icon-{n}.png")

    ico = [render_icon(n) for n in (256, 64, 48, 32, 24, 16)]
    ico[0].save(out / "icon.ico", sizes=[(n, n) for n in (256, 64, 48, 32, 24, 16)])
    print(f"icons written to {out}")


if __name__ == "__main__":
    main()
