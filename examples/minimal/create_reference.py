from pathlib import Path

from PIL import Image, ImageDraw


output = Path(__file__).with_name("reference.png")
image = Image.new("RGB", (320, 180), "#E9E3D6")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((16, 16, 304, 164), radius=10, fill="#F7F2E8", outline="#B79A63", width=2)
draw.rectangle((80, 120, 240, 156), fill="#426E68", outline="#B79A63", width=2)
draw.line((40, 92, 280, 92), fill="#CFC3A8", width=2)
image.save(output)
print(output)
