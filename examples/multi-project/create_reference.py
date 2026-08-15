from pathlib import Path

from PIL import Image, ImageDraw


root = Path(__file__).resolve().parent
image = Image.new("RGB", (320, 180), "#ece7dc")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 304, 164), radius=10, fill="#f7f2e8", outline="#b79a63", width=2)
draw.rounded_rectangle((80, 120, 240, 156), radius=6, fill="#426e68", outline="#b79a63", width=2)
draw.text((32, 32), "Multi-style UI", fill="#34322d")
draw.text((128, 132), "Build", fill="#fffdf6")
image.save(root / "reference.png")
print(root / "reference.png")
