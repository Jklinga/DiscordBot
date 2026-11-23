"""Makes the app icons from purgeBot.png. Run again if you change the picture:

    python assets/make_icons.py

Creates (in this folder):
    icon.png      square, transparent background (used by the app window and README)
    header.png    small version for the app's header
    purgebot.ico  Windows icon in several sizes (used for PurgeBot.exe)
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "purgeBot.png")
TOLERANCE = 40  # how different from the background color a pixel must be to be kept


def main():
    if not os.path.exists(SOURCE):
        sys.exit(f"Can't find {SOURCE}")
    img = Image.open(SOURCE).convert("RGBA")

    # Make the flat background transparent by flood-filling from each corner,
    # so gray parts inside the drawing are left alone.
    w, h = img.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if img.getpixel(corner)[3] != 0:
            ImageDraw.floodfill(img, corner, (0, 0, 0, 0), thresh=TOLERANCE)

    # Crop to the drawing and center it on a square canvas with a little padding
    img = img.crop(img.getchannel("A").getbbox())
    side = int(max(img.size) * 1.06)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)

    square.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "icon.png"))
    square.resize((60, 60), Image.LANCZOS).save(os.path.join(HERE, "header.png"))
    square.save(os.path.join(HERE, "purgebot.ico"),
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Created assets/icon.png, assets/header.png and assets/purgebot.ico")


if __name__ == "__main__":
    main()
