"""Stitch Playwright frames into demo.gif (frames dir given as argv[1])."""
import sys
from pathlib import Path

from PIL import Image

frames = sorted(Path(sys.argv[1]).glob("f*.png"))
ims = [Image.open(f).convert("RGB").resize((960, 675)) for f in frames]
ims = [i.quantize(128, dither=Image.Dither.NONE) for i in ims]
ims[0].save(Path(__file__).parent / "demo.gif", save_all=True, append_images=ims[1:], duration=1000, loop=0, optimize=True)
print(len(ims), "frames")
