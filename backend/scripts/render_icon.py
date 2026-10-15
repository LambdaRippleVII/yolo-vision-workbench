"""Render YOLO Vision Workbench icon PNGs from the vector design (deterministic, not AI gen)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(r"D:\project\Toys\YOLO Vision Workbench\desktop\build")
OUT.mkdir(parents=True, exist_ok=True)


def draw_icon(size: int) -> Image.Image:
    s = size / 1024
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def px(v: float) -> int:
        return int(round(v * s))

    # tile
    d.rounded_rectangle(
        [px(64), px(64), px(960), px(960)],
        radius=px(200),
        fill=(27, 42, 58, 255),
        outline=(47, 62, 80, 255),
        width=max(1, px(2)),
    )

    # brackets
    br = (47, 111, 237, 255)  # #2F6FED
    lw = px(28)
    # corners as two segments each
    # TL
    d.line([px(220), px(340), px(220), px(240)], fill=br, width=lw)
    d.line([px(220), px(240), px(320), px(240)], fill=br, width=lw)
    # TR
    d.line([px(704), px(240), px(804), px(240)], fill=br, width=lw)
    d.line([px(804), px(240), px(804), px(340)], fill=br, width=lw)
    # BR
    d.line([px(804), px(684), px(804), px(784)], fill=br, width=lw)
    d.line([px(704), px(784), px(804), px(784)], fill=br, width=lw)
    # BL
    d.line([px(220), px(684), px(220), px(784)], fill=br, width=lw)
    d.line([px(220), px(784), px(320), px(784)], fill=br, width=lw)

    # lens rings
    cx, cy = px(512), px(512)
    d.ellipse([cx - px(148), cy - px(148), cx + px(148), cy + px(148)], outline=(143, 166, 191, 255), width=px(22))
    d.ellipse([cx - px(96), cy - px(96), cx + px(96), cy + px(96)], fill=(23, 34, 48, 255))
    d.ellipse([cx - px(62), cy - px(62), cx + px(62), cy + px(62)], fill=(47, 111, 237, 230))
    d.ellipse(
        [cx - px(22) - px(24), cy - px(22) - px(24), cx - px(24) + px(22), cy - px(24) + px(22)],
        fill=(62, 207, 219, 255),
    )
    return im


def main() -> None:
    for n in (256, 512, 1024):
        img = draw_icon(n)
        img.save(OUT / f"icon-{n}.png")
        print("wrote", OUT / f"icon-{n}.png")
    # multi-size ICO for Windows
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    base = draw_icon(1024)
    base.resize((256, 256), Image.Resampling.LANCZOS).save(
        OUT / "icon.ico", sizes=sizes
    )
    print("wrote", OUT / "icon.ico")


if __name__ == "__main__":
    main()
