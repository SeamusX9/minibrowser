"""生成 sea.ico（若已有同名文件则跳过）。"""
from pathlib import Path

from PIL import Image, ImageDraw

ICON = Path(__file__).resolve().parent / "sea.ico"


def main() -> None:
    if ICON.is_file():
        print(f"已存在: {ICON}")
        return
    size = 256
    img = Image.new("RGBA", (size, size), (30, 120, 180, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 80, 216, 200], fill=(20, 80, 140, 255))
    draw.polygon([(60, 100), (200, 100), (128, 40)], fill=(180, 220, 255, 255))
    img.save(ICON, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print(f"已生成: {ICON}")


if __name__ == "__main__":
    main()
