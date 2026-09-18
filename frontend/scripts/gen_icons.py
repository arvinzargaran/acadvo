"""Raster app icons from the same 512-grid the SVG mark uses.

Kept as a script rather than hand-exported PNGs so the icon set can be
regenerated from one source of truth if the mark ever changes.
"""
from PIL import Image, ImageDraw

BLUE = (27, 98, 240, 255)          # --wf-live / #1B62F0
CLEAR = (0, 0, 0, 0)
SS = 4                              # supersample factor

STROKE, NODE, HOLE = 44, 44, 22     # width, node radius, hole radius
ROUTE = [((139, 416), (373, 96)), ((373, 96), (373, 416)), ((227, 296), (373, 296))]
NODES = [(373, 96), (227, 296), (373, 296), (139, 416), (373, 416)]
HOLES = [(227, 296), (373, 296), (139, 416), (373, 416)]   # apex stays solid


def draw_mark(px, scale=1.0):
    """Return an RGBA image of the mark, `px` square, mark scaled about centre."""
    n = px * SS
    img = Image.new("RGBA", (n, n), CLEAR)
    d = ImageDraw.Draw(img)
    k = (n / 512) * scale
    off = (n - 512 * k) / 2

    def p(pt):
        return (pt[0] * k + off, pt[1] * k + off)

    def disc(pt, r, fill):
        x, y = p(pt)
        rr = r * k
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)

    for a, b in ROUTE:
        d.line([p(a), p(b)], fill=BLUE, width=int(round(STROKE * k)))
        for end in (a, b):                       # round caps
            disc(end, STROKE / 2, BLUE)
    for pt in NODES:
        disc(pt, NODE, BLUE)
    for pt in HOLES:                             # punched, not painted white
        disc(pt, HOLE, CLEAR)

    return img.resize((px, px), Image.LANCZOS)


def on_white(px, scale=1.0):
    bg = Image.new("RGBA", (px, px), (255, 255, 255, 255))
    bg.alpha_composite(draw_mark(px, scale))
    return bg.convert("RGB")


OUT = "public/"
on_white(192).save(OUT + "pwa-192x192.png")
on_white(512).save(OUT + "pwa-512x512.png")
on_white(180).save(OUT + "apple-touch-icon.png")
# Maskable: platforms crop to a circle inscribed in the middle ~80%, so the
# mark is scaled down to sit inside the safe zone and the ground is full-bleed.
on_white(512, scale=0.62).save(OUT + "maskable-512x512.png")
print("wrote 4 icons")
