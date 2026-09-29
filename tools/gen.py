#!/usr/bin/env python3
"""Generate every SVG used by the profile README (github.com/INo-xious).

    python3 tools/gen.py      # writes ../assets/*.svg, then audits them

Rules the output follows:
  * all lettering is outlined to <path> via textpath.FONTS (no <text>, no fonts, no external refs)
  * root <svg> has width/height == viewBox, role="img" and a <title>
  * only title-card.svg animates: CSS @keyframes inside @media (prefers-reduced-motion: no-preference),
    one-shot, and its default styling is the settled final frame. Everything else sits below the fold,
    where an on-load animation would finish before anyone scrolls to it, so it is static.
"""
import html
import math
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textpath import FONTS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets"))
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- palette
FIELD = "#AC0008"      # the GIF's final red field; the dither filter speckles it like the GIF's #AD0008/#B50008
GIF_EDGE = "#B31A21"   # the GIF's 1px outer frame colour
RED = "#AD0008"        # brand red: fills, and text on light backgrounds (7.5:1 on white)
RED_HI = "#FF4D4D"     # red for text/thin strokes on dark backgrounds (5.8:1 on #0d1117)
LETTER = "#E7E7E7"     # the GIF logo's letter colour
NIGHT = "#0A0A0C"      # near-black film

THEMES = {
    "light": dict(ink="#0B0B0D", muted="#59636E", red=RED),
    "dark": dict(ink="#F0F3F6", muted="#9198A1", red=RED_HI),
}

MOTION_GATE = "@media (prefers-reduced-motion: no-preference){%s}"

# smallest lettering size used per output file, checked by the audit
_min_size = {}
_current = [None]


def _track(size):
    k = _current[0]
    if k is not None:
        _min_size[k] = min(_min_size.get(k, 1e9), size)


def T(font, s, size, x, y, anchor="start", tracking=0.0, fill="#000", extra="", sx=1.0):
    """Outlined text -> (<path/>, width)."""
    _track(size)
    d, w = FONTS[font].path(s, size=size, x=x, y=y, anchor=anchor, tracking=tracking, sx=sx)
    return f'<path d="{d}" fill="{fill}"{(" " + extra) if extra else ""}/>', w


def W(font, s, size, tracking=0.0):
    return FONTS[font].measure(s, size, tracking)


def cap(font, size):
    f = FONTS[font]
    return f.cap_height / f.upem * size


def caption(font, s, size, x, y, anchor="start", tracking=0.0, fill="#000", word=0.5, dot=0.65):
    """Tracked caption set word by word -> (paths, width). A mono space plus tracking is ~0.66 em and reads
    as a double space in tracked caps, so words are `word` em apart, and each " · " becomes a small circle at
    cap-middle with `dot` em on each side."""
    toks = s.split(" ")
    ws = [0.0 if t == "·" else W(font, t, size, tracking) for t in toks]
    gaps = [(dot if "·" in (a, b) else word) * size for a, b in zip(toks, toks[1:])]
    total = sum(ws) + sum(gaps)
    if anchor == "middle":
        x -= total / 2
    elif anchor == "end":
        x -= total
    r, mid = max(1.4, 0.073 * size), y - cap(font, size) / 2
    out = []
    for i, t in enumerate(toks):
        if t == "·":
            out.append(f'<circle cx="{n(x)}" cy="{n(mid)}" r="{n(r)}" fill="{fill}"/>')
        else:
            out.append(T(font, t, size, x, y, tracking=tracking, fill=fill)[0])
        x += ws[i] + (gaps[i] if i < len(gaps) else 0)
    return "".join(out), total


def letters(font, s, size, x0, y, tracking=0.0, sx=1.0):
    """Per-glyph paths (kerning kept) so each letter can animate on its own."""
    _track(size)
    f = FONTS[font]
    out = []
    for i, ch in enumerate(s):
        if ch == " ":
            continue
        off = (f.measure(s[: i + 1], size, tracking) - f.measure(ch, size, 0)) * sx
        d, w = f.path(ch, size=size, x=x0 + off, y=y, sx=sx)
        out.append((d, x0 + off, w))
    return out


def n(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def svg(w, h, title, body, style="", desc=""):
    title = html.escape(title, quote=False)
    labelled = "title desc" if desc else "title"
    d = f'<desc id="desc">{html.escape(desc, quote=False)}</desc>' if desc else ""
    st = f"<style>{style}</style>" if style else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="{labelled}">\n<title id="title">{title}</title>{d}{st}\n{body}\n</svg>\n')


def begin(name):
    _current[0] = name


def save(name, content):
    p = os.path.join(OUT, name)
    with open(p, "w") as fh:
        fh.write(content)
    _current[0] = None
    print(f"{name:40s} {len(content.encode()) / 1024:6.1f} KB")


def grain(fid, opacity=0.07, freq=0.85):
    """Film grain as an SVG filter (no bitmap)."""
    return (f'<filter id="{fid}" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="7" stitchTiles="stitch"/>'
            f'<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 {opacity} 0"/></filter>')


# =====================================================================================
# 1. TITLE CARD: sits flush right of the GIF (400x225) and finishes the name on its red
# =====================================================================================
def title_card():
    name_ = "title-card.svg"
    begin(name_)
    # the GIF's own box, so the two panels are flush when the hero stacks (any column narrower than 800 px)
    Wd, Hd = 400, 225
    # The GIF's final frame: flat #E7E7E7 letters, cap top y=86, baseline y=139, stems 9.5-10 px, letters
    # ~25 wide. sx .80 and a hairline stroke match that weight and width (stems ~10, cap rows 85-139).
    size, sx, tr, base = 66.4, 0.80, -0.025, 139.3
    word = "HARISSON"
    wname = W("display", word, size, tr) * sx
    x0 = (Wd - wname) / 2
    glyphs = letters("display", word, size, x0, base, tracking=tr, sx=sx)
    outline = "".join(f'<path class="o" d="{d}"/>' for d, _, _ in glyphs)
    filled = "".join(f'<path class="l l{i}" d="{d}"/>' for i, (d, _, _) in enumerate(glyphs))
    clip = "".join(f'<path d="{d}"/>' for d, _, _ in glyphs)

    # captions are 16 units: the card shrinks to 278/400 = 0.70x on a 360 px phone, so they stay ~11.1 px.
    # Ink rows 48-59 / 85-139 / 165-176: equal 48-unit outer margins and 25-unit gaps around the name.
    top_p, _ = caption("mono-bold", "INo-xious · OSAKA", 16, Wd / 2, 60, anchor="middle", tracking=0.05,
                       fill=LETTER)
    tag_p, _ = caption("mono-bold", "PERCEPTION · ROBOTICS · SYSTEMS", 16, Wd / 2, 177, anchor="middle",
                       tracking=0.08, fill=LETTER)

    stagger = "".join(f".l{i}{{animation-delay:{2.75 + i * 0.07:.2f}s}}" for i in range(len(glyphs)))
    style = (
        # the outline is only the motion start state; hidden when settled and under reduced motion
        f".o{{fill:none;stroke:{LETTER};stroke-width:1.6;opacity:0}}"
        f".l{{fill:{LETTER};stroke:{LETTER};stroke-width:0.4;stroke-linejoin:miter}}"
        ".shine{opacity:0}"
        + MOTION_GATE % (
            ".o{opacity:1;animation:drop .01s linear 4s forwards}@keyframes drop{to{opacity:0}}"
            ".l{animation:fill .8s cubic-bezier(.2,.8,.2,1) both}"
            "@keyframes fill{from{opacity:0;transform:translateY(10px)}}"
            + stagger +
            ".shine{animation:sweep 1.5s ease-in-out 4.1s both}"
            "@keyframes sweep{0%{opacity:1;transform:translateX(-120px)}85%{opacity:1}"
            "100%{opacity:0;transform:translateX(330px)}}"
        )
    )
    body = f"""
<defs>
  <!-- matches the GIF's dithered field: #AD0008 speckled with #B50008 -->
  <filter id="dither" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="1" seed="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .71  0 0 0 0 0  0 0 0 0 .031  0 0 0 -6 3.3 "/></filter>
  <clipPath id="letters">{clip}</clipPath>
  <linearGradient id="sh" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
</defs>
<rect width="{Wd}" height="{Hd}" fill="{FIELD}"/>
<rect width="{Wd}" height="{Hd}" filter="url(#dither)"/>
<path d="M0 .5H{Wd - .5}V{Hd - .5}H0" fill="none" stroke="{GIF_EDGE}" stroke-width="1"/>
<g>{top_p}{tag_p}</g>
{outline}
{filled}
<g clip-path="url(#letters)"><g transform="skewX(-20)"><rect class="shine" x="{n(x0)}" y="70" width="90" height="80" fill="url(#sh)"/></g></g>
"""
    save(name_, svg(Wd, Hd, "HARISSON. Perception, robotics, systems. INo-xious, Osaka.", body, style,
                    "Title card on the red field that ends the MARVEL logo animation to its left, completing the "
                    "name Marvel Harisson."))


# =====================================================================================
# 2. SECTION SLATES: number chip + condensed title + right-aligned mono caption
# =====================================================================================
SLATES = [
    ("01", "in-production", "IN PRODUCTION", "CURRENT WORK", "01 In production: current work"),
    ("02", "now-showing", "NOW SHOWING", "OWN PROJECTS", "02 Now showing: own projects"),
    ("03", "guest-appearances", "GUEST APPEARANCES", "UPSTREAM PRS", "03 Guest appearances: upstream pull requests"),
    ("04", "credits", "CREDITS", "STACK · CONTACT", "04 Credits: stack and contact"),
]


def slate(num, slug, title, cap_text, alt, theme):
    fname = f"slate-{num}-{slug}-{theme}.svg"
    begin(fname)
    c = THEMES[theme]
    Wd, Hd = 846, 64
    base = 52
    cs = 31                        # chip number and caption: 31 x 278/846 = 10.2 CSS px in a 360 px phone's column
    num_p, _ = T("mono-xbold", num, cs, 30, 32 + cap("mono-xbold", cs) / 2, anchor="middle", fill="#FFFFFF")
    title_p, _ = T("display", title, 48, 78, base, tracking=0.03, fill=c["ink"])
    cap_p, cw = caption("mono-bold", cap_text, cs, Wd, base, anchor="end", tracking=0.06, fill=c["muted"])
    mid = base - cap("mono-bold", cs) / 2
    dx = Wd - cw - 14 - 4          # diamond centre: its right tip sits 14 units left of the caption
    body = (f'<rect x="0" y="6" width="60" height="52" fill="{RED}"/>{num_p}\n{title_p}\n'
            f'<path d="M{n(dx)} {n(mid - 4)}l4 4-4 4-4-4z" fill="{c["red"]}"/>\n{cap_p}')
    save(fname, svg(Wd, Hd, alt, body))


# =====================================================================================
# 3. PRODUCTION STILL: perception for robotic parcel picking (illustration, not data)
# =====================================================================================
STILL = {
    "light": dict(bg="#FFFFFF", frame="#D0D7DE", hair="#D0D7DE",
                  depth=["#1F2328", "#3D444D", "#59636E", "#818B96", "#AEB8C2"],
                  top="#F6F8FA", side="#EAEEF2", side2="#DFE4E9", edge="#AEB8C2",
                  mask="#57606A", red=RED, ink="#1F2328", muted="#59636E", glow=0.10),
    "dark": dict(bg=NIGHT, frame="#2C2C33", hair="#30363D",
                 depth=["#F4F4F5", "#C9CDD3", "#9BA1A9", "#6E747C", "#4A4F56"],
                 top="#16171B", side="#111215", side2="#0E0F12", edge="#2C2C33",
                 mask="#C9CDD3", red=RED_HI, ink="#F0F3F6", muted="#9198A1", glow=0.22),
}


class Cam:
    def __init__(self, pos, look, F, cx, cy):
        self.C = pos
        fw = norm(sub(look, pos))
        r = norm(cross(fw, (0, 0, 1)))
        u = cross(r, fw)
        self.f, self.r, self.u, self.F, self.cx, self.cy = fw, r, u, F, cx, cy

    def depth(self, P):
        return dot(sub(P, self.C), self.f)

    def __call__(self, P):
        d = sub(P, self.C)
        z = dot(d, self.f)
        return (self.cx + self.F * dot(d, self.r) / z, self.cy - self.F * dot(d, self.u) / z)


def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    ln = math.sqrt(dot(a, a))
    return (a[0] / ln, a[1] / ln, a[2] / ln)


def box(cx, cy, z0, w, d, h, yaw):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    pts = []
    for zz in (z0, z0 + h):
        for (dx, dy) in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            pts.append((cx + dx * c - dy * s, cy + dx * s + dy * c, zz))
    b0, b1, b2, b3, t0, t1, t2, t3 = pts
    faces = {
        "top": [t0, t1, t2, t3],
        "s0": [b0, b1, t1, t0],
        "s1": [b1, b2, t2, t1],
        "s2": [b2, b3, t3, t2],
        "s3": [b3, b0, t0, t3],
    }
    return faces, (cx, cy, z0 + h / 2)


def centroid(q):
    k = len(q)
    return (sum(p[0] for p in q) / k, sum(p[1] for p in q) / k, sum(p[2] for p in q) / k)


def face_normal(q):
    return norm(cross(sub(q[1], q[0]), sub(q[3], q[0])))


def poly(cam, q):
    return "M" + "L".join(f"{n(x)} {n(y)}" for x, y in (cam(p) for p in q)) + "Z"


def sample(q, step, rnd):
    """Jittered grid of points on a planar quad q (p0,p1,p2,p3)."""
    e1, e3 = sub(q[1], q[0]), sub(q[3], q[0])
    l1, l3 = math.sqrt(dot(e1, e1)), math.sqrt(dot(e3, e3))
    n1, n3 = max(2, int(l1 / step)), max(2, int(l3 / step))
    pts = []
    for i in range(n1):
        for j in range(n3):
            s = (i + 0.5 + rnd.uniform(-0.3, 0.3)) / n1
            t = (j + 0.5 + rnd.uniform(-0.3, 0.3)) / n3
            pts.append(add(q[0], add(mul(e1, s), mul(e3, t))))
    return pts


# scene, in centimetres: parcels of different sizes on the ground plane
PARCELS = [
    # cx, cy, z0, w, d, h, yaw
    (16, 14, 0, 24, 20, 10, 6),
    (80, 13, 0, 28, 18, 9, -4),
    (86, 42, 0, 20, 30, 12, 3),
    (19, 48, 0, 28, 28, 14, -5),
    (52, 33, 0, 30, 26, 21, 7),    # tallest: the grasp target
    (51, 58, 0, 30, 12, 8, -2),
    (79, 14, 9, 14, 11, 7, 16),    # small parcel stacked on #2
]
CAM_POS, CAM_LOOK = (42, -64, 84), (50, 30, 4)
TARGET = 4  # index of the parcel whose top is the grasp target
STILL_ALT = ("Illustration, not sensor data: parcels of different sizes drawn as a point cloud. Each parcel top has a "
             "class-agnostic instance mask, and one top surface is highlighted in red as the graspable target. "
             "Methods: RGB-D fusion and point-cloud segmentation; goal: the graspable top surface.")


def still_perception(theme):
    fname = f"still-perception-{theme}.svg"
    begin(fname)
    p = STILL[theme]
    Wd, Ht = 846, 340
    rnd = random.Random(7)
    VX0, VX1, VY0, VY1 = 24, 530, 60, 262          # scene viewport

    # ground grid under the parcels: the parcels' footprint, snapped out to the 10 cm grid
    foot = [pt for prm in PARCELS for pt in box(*prm)[0]["top"]]
    gx0 = math.floor(min(v[0] for v in foot) / 10) * 10
    gx1 = math.ceil(max(v[0] for v in foot) / 10) * 10
    gy0 = math.floor(min(v[1] for v in foot) / 10) * 10
    gy1 = math.ceil(max(v[1] for v in foot) / 10) * 10

    # fit the camera to the viewport (hud's fitting code, without the bin)
    probe = Cam(pos=CAM_POS, look=CAM_LOOK, F=1, cx=0, cy=0)
    corners = [pt for prm in PARCELS for q in box(*prm)[0].values() for pt in q]
    corners += [(x, y, 0) for x in (gx0, gx1) for y in (gy0, gy1)]
    pr = [probe(c) for c in corners]
    bx0, bx1 = min(v[0] for v in pr), max(v[0] for v in pr)
    by0, by1 = min(v[1] for v in pr), max(v[1] for v in pr)
    ax0, ax1, ay0, ay1 = VX0 + 4, VX1 - 4, VY0 + 4, VY1 - 4
    F = min((ax1 - ax0) / (bx1 - bx0), (ay1 - ay0) / (by1 - by0))
    cam = Cam(pos=CAM_POS, look=CAM_LOOK, F=F,
              cx=(ax0 + ax1) / 2 - F * (bx0 + bx1) / 2, cy=(ay0 + ay1) / 2 - F * (by0 + by1) / 2)

    out = [f'<rect width="{Wd}" height="{Ht}" fill="{p["bg"]}"/>',
           f'<rect x=".5" y=".5" width="{Wd - 1}" height="{Ht - 1}" fill="none" stroke="{p["frame"]}"/>']

    # header. Labels in this file are 31 units: 31 x 278/846 = 10.2 CSS px in a 360 px phone's column.
    LS = 31
    h1, _ = caption("mono-bold", "RGB-D · UNKNOWN PARCELS", LS, 24, 42, tracking=0.04, fill=p["muted"])
    tag_w = round(W("mono-bold", "ILLUSTRATION", LS, 0.08) + 24)
    tag_h = round(cap("mono-bold", LS) + 19)
    tag_cx = 822 - tag_w / 2
    tag_mid = 42 - cap("mono-bold", LS) / 2
    h2, _ = T("mono-bold", "ILLUSTRATION", LS, tag_cx, 42, anchor="middle", tracking=0.08, fill=p["muted"])
    out.append(h1)
    out.append(f'<rect x="{822 - tag_w + .75}" y="{n(tag_mid - tag_h / 2)}" width="{tag_w - 1.5}" height="{tag_h}" '
               f'fill="none" stroke="{p["muted"]}" stroke-width="1.5"/>{h2}')

    # ground grid
    gl = []
    for x in range(gx0, gx1 + 1, 10):
        a, b = cam((x, gy0, 0)), cam((x, gy1, 0))
        gl.append(f"M{n(a[0])} {n(a[1])}L{n(b[0])} {n(b[1])}")
    for y in range(gy0, gy1 + 1, 10):
        a, b = cam((gx0, y, 0)), cam((gx1, y, 0))
        gl.append(f"M{n(a[0])} {n(a[1])}L{n(b[0])} {n(b[1])}")
    out.append(f'<path d="{"".join(gl)}" fill="none" stroke="{p["hair"]}" stroke-width="0.8" opacity=".35"/>')

    # point cloud: sample every visible face, bucket points by depth
    boxes = []
    for i, prm in enumerate(PARCELS):
        faces, ctr = box(*prm)
        boxes.append((i, faces, ctr))
    boxes.sort(key=lambda b: -cam.depth(b[2]))
    face_pts, all_depths = {}, []
    for i, faces, _ in boxes:
        for k, q in faces.items():
            if dot(face_normal(q), sub(cam.C, centroid(q))) <= 0:
                continue
            pts = sample(q, 1.7 if k == "top" else 2.0, rnd)
            face_pts[(i, k)] = pts
            all_depths += [cam.depth(pt) for pt in pts]
    dmin, dmax = min(all_depths), max(all_depths)
    nb = len(p["depth"])

    def dots(pts, sw):
        buckets = [[] for _ in range(nb)]
        for pt in pts:
            x, y = cam(pt)
            t = (cam.depth(pt) - dmin) / (dmax - dmin)
            buckets[min(nb - 1, int(t * nb))].append(f"M{n(x)} {n(y)}h0")
        return "".join(f'<path d="{"".join(b)}" stroke="{p["depth"][j]}" stroke-width="{sw}" stroke-linecap="round"/>'
                       for j, b in enumerate(buckets) if b)

    scene, tops = [], {}
    for i, faces, _ in boxes:
        vis = [(k, q) for k, q in faces.items() if dot(face_normal(q), sub(cam.C, centroid(q))) > 0]
        vis.sort(key=lambda kq: (kq[0] == "top", -cam.depth(centroid(kq[1]))))
        for k, q in vis:
            fill = p["top"] if k == "top" else (p["side"] if k in ("s0", "s2") else p["side2"])
            d = poly(cam, q)
            scene.append(f'<path d="{d}" fill="{fill}" stroke="{p["edge"]}" stroke-width="1" stroke-linejoin="round"/>')
            scene.append(dots(face_pts[(i, k)], 2.1 if k == "top" else 1.7))
            if k == "top" and i != TARGET:
                # class-agnostic instance mask, in painter order so nearer parcels occlude it
                scene.append(f'<path d="{d}" fill="{p["mask"]}" fill-opacity=".08" stroke="{p["mask"]}" '
                             f'stroke-width="2.5" stroke-linejoin="round"/>')
        tops[i] = faces["top"]
    out.append("<g>" + "".join(scene) + "</g>")

    # grasp target: the tallest parcel's top face
    q = tops[TARGET]
    cx_, cy_ = cam(centroid(q))
    out.append(f'<defs><radialGradient id="glow"><stop offset="0" stop-color="{p["red"]}" stop-opacity="{p["glow"]}"/>'
               f'<stop offset="1" stop-color="{p["red"]}" stop-opacity="0"/></radialGradient></defs>')
    out.append(f'<ellipse cx="{n(cx_)}" cy="{n(cy_)}" rx="120" ry="72" fill="url(#glow)"/>')
    out.append(f'<path d="{poly(cam, q)}" fill="{p["red"]}" fill-opacity=".18" stroke="{p["red"]}" stroke-width="3" '
               f'stroke-linejoin="round"/>')

    # right column: callouts
    colx, lead_y = 553, 96
    sx_, sy_ = max((cam(pt) for pt in q), key=lambda v: v[0] - v[1])   # upper-right corner of the target top
    # the corner is the highest point of the scene, so the leader runs level from it (clearing the parcel
    # behind), then steps down 45 degrees to the label's cap height; a background halo keeps it off the art
    ex = colx - 12
    lead = f"M{n(sx_)} {n(sy_)}H{n(ex - 14 - (lead_y - sy_))}l{n(lead_y - sy_)} {n(lead_y - sy_)}H{ex}"
    out.append(f'<path d="{lead}" fill="none" stroke="{p["bg"]}" stroke-width="6" stroke-linejoin="round"/>'
               f'<path d="{lead}" fill="none" stroke="{p["red"]}" stroke-width="1.5"/>'
               f'<circle cx="{n(sx_)}" cy="{n(sy_)}" r="3.5" fill="{p["red"]}"/>'
               f'<circle cx="{ex}" cy="{lead_y}" r="3.5" fill="{p["red"]}"/>')
    out.append(T("display", "GRASPABLE", 40, colx, 110, tracking=0.03, fill=p["red"])[0])
    out.append(T("display", "TOP SURFACE", 40, colx, 154, tracking=0.03, fill=p["red"])[0])
    sw_mid = 212 - cap("display", 32) / 2
    # legend key drawn as a small parcel top (25x16 parallelogram with a few points), so it reads as a mask,
    # not an empty checkbox. 25 wide is the most the column allows: INSTANCE MASKS (235 units) must end by 822.
    sq = f"M{n(colx + 1.25)} {n(sw_mid + 8)}l8 -16h17l-8 16z"
    out.append(f'<path d="{sq}" fill="{p["top"]}"/><path d="{sq}" fill="{p["mask"]}" fill-opacity=".08" '
               f'stroke="{p["mask"]}" stroke-width="2.5" stroke-linejoin="round"/>'
               + "".join(f'<circle cx="{n(colx + 1.25 + dx)}" cy="{n(sw_mid + dy)}" r="1" fill="{p["depth"][1]}"/>'
                         for dx, dy in ((7, 4), (12, -3), (16, 3), (19, -4), (11, 1))))
    out.append(T("display", "INSTANCE MASKS", 32, 587, 212, tracking=0.03, fill=p["ink"])[0])
    out.append(T("mono", "CLASS-AGNOSTIC", LS, colx, 248, tracking=0.02, fill=p["muted"])[0])

    # bottom strip: the two model families, as a neutral list (LinkedIn states the models, not a pipeline
    # between them). Muted, so emphasis runs callout > masks > strip; the goal is already the red callout.
    out.append(f'<path d="M24 282H822" stroke="{p["hair"]}" stroke-width="1"/>')
    steps = [("RGB-D FUSION", p["muted"]), ("POINT-CLOUD SEGMENTATION", p["muted"])]
    gap, sy = 32, 322
    total = sum(W("display", s_, LS, 0.02) for s_, _ in steps) + gap * (len(steps) - 1)
    x = (Wd - total) / 2
    dot_mid = sy - cap("display", LS) / 2
    for k, (s_, col) in enumerate(steps):
        tp, tw = T("display", s_, LS, x, sy, tracking=0.02, fill=col)
        out.append(tp)
        x += tw
        if k < len(steps) - 1:
            out.append(f'<circle cx="{n(x + gap / 2)}" cy="{n(dot_mid)}" r="2" fill="{p["muted"]}"/>')
            x += gap

    save(fname, svg(Wd, Ht, "Illustration: perception for robotic parcel picking", "\n".join(out), desc=STILL_ALT))


# =====================================================================================
# 4. POSTERS (one-sheets, 272x400, opaque: identical in both themes)
# =====================================================================================
PW, PH = 272, 400
# every poster title, so the series shares one title size and baselines
POSTER_TITLES = (("STOCKBIT", "MCP"), ("MARVELOUS", "ENGINE"), ("IDX", "OWNERSHIP"))


def poster(fname, title, credit, pill, title_lines, art):
    """Full one-sheet, served at viewports >= 1012 px (182-266 px wide), plus a -thumb variant with only
    art and title, served below that through <source media="(max-width: 1011px)"> (87-182 px wide)."""
    _poster(fname, title, credit, pill, title_lines, art, thumb=False)
    _poster(fname.replace(".svg", "-thumb.svg"), title, credit, pill, title_lines, art, thumb=True)


def _poster(fname, title, credit, pill, title_lines, art, thumb):
    begin(fname)
    # sized over the whole series (widest: MARVELOUS), so all three posters share cap height and baselines;
    # full and thumb both use a 244-unit title width (14-unit side margins)
    widest = max(W("display", t, 1, 0.02) for tl in POSTER_TITLES for t in tl)
    if thumb:
        # title block fits between the rule (y 276-280) and a 14-unit bottom margin
        tsize = min(64, 244 / widest, (PH - 14 - 292) / (0.81 + 0.95))
        y1 = 292 + cap("display", tsize)
    else:
        tsize = min(54, 244 / widest)
        y1 = max(324, 274 + 14 + cap("display", tsize))   # keep >= 14 units under the pill (y 252-274)
    t1, _ = T("display", title_lines[0], tsize, PW / 2, y1, anchor="middle", tracking=0.02, fill="#F4F4F5")
    t2, _ = T("display", title_lines[1], tsize, PW / 2, y1 + tsize * 0.95, anchor="middle", tracking=0.02,
              fill=RED_HI)
    if thumb:
        top = f'<rect x="{PW / 2 - 22}" y="276" width="44" height="4" fill="{RED}"/>'
    else:
        # the handle keeps its real casing (INo-xious), so lowercase is tracked only .05
        cr, _ = caption("mono-bold", credit, 16.5, PW / 2, 34, anchor="middle", tracking=0.05, fill="#C4C4CA")
        # pill sits in the solid NIGHT band (y >= 250), clear of the art above (which ends by y 242)
        pp, pw_ = caption("mono-bold", pill, 16.5, PW / 2, 269, anchor="middle", tracking=0.12, fill="#FFFFFF")
        pw_ += 20
        top = f'{cr}<rect x="{n(PW / 2 - pw_ / 2)}" y="252" width="{n(pw_)}" height="22" fill="{RED}"/>{pp}'
    body = f"""
<defs>
  <radialGradient id="spot" cx="50%" cy="0%" r="85%"><stop offset="0" stop-color="{RED}" stop-opacity=".62"/><stop offset=".55" stop-color="{RED}" stop-opacity=".12"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient>
  <linearGradient id="fade" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{NIGHT}" stop-opacity="0"/><stop offset="1" stop-color="{NIGHT}"/></linearGradient>
  <pattern id="ht" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="2.5" cy="2.5" r=".9" fill="#fff"/></pattern>
  <radialGradient id="htm" cx="85%" cy="15%" r="60%"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
  <mask id="htmask"><rect width="{PW}" height="{PH}" fill="url(#htm)"/></mask>
  {grain("gr", 0.06)}
</defs>
<rect width="{PW}" height="{PH}" fill="{NIGHT}"/>
<rect width="{PW}" height="300" fill="url(#spot)"/>
<rect width="{PW}" height="{PH}" fill="url(#ht)" mask="url(#htmask)"/>
<g>{art}</g>
<rect y="190" width="{PW}" height="60" fill="url(#fade)"/>
<rect y="250" width="{PW}" height="{PH - 250}" fill="{NIGHT}"/>
{top}
{t1}{t2}
<rect width="{PW}" height="{PH}" filter="url(#gr)"/>
<rect x=".5" y=".5" width="{PW - 1}" height="{PH - 1}" fill="none" stroke="#2C2C33"/>
"""
    save(fname, svg(PW, PH, title, body))


def poster_stockbit():
    rnd = random.Random(11)
    # big outlined IDX behind the chart
    idx_d, _ = FONTS["display"].path("IDX", size=190, x=PW / 2, y=236, anchor="middle", tracking=0.01)
    art = [f'<path d="{idx_d}" fill="none" stroke="#FFFFFF" stroke-opacity=".09" stroke-width="1.2"/>']
    for gy in (96, 132, 168, 204, 240):
        art.append(f'<rect x="18" y="{gy}" width="{PW - 36}" height=".6" fill="#FFFFFF" fill-opacity=".07"/>')
    k = 17
    price = 100.0
    ohlc = []
    for i in range(k):
        o = price
        drift = 1.4 if i < 10 else (-2.2 if i < 12 else 2.4)
        c = o + drift + rnd.uniform(-3.2, 3.2)
        hi = max(o, c) + rnd.uniform(0.6, 2.6)
        lo = min(o, c) - rnd.uniform(0.6, 2.6)
        ohlc.append((o, hi, lo, c))
        price = c
    lo_all = min(x[2] for x in ohlc)
    hi_all = max(x[1] for x in ohlc)

    def py(v):   # lowest wick at y 236, 16 units above the pill
        return 236 - (v - lo_all) / (hi_all - lo_all) * 150

    x0, step, bw = 24, (PW - 48) / (k - 1), 7.2
    ma = []
    for i, (o, hi, lo, c) in enumerate(ohlc):
        x = x0 + i * step
        col = "#E9E9EC" if c >= o else RED_HI
        y1, y2 = py(max(o, c)), py(min(o, c))
        art.append(
            f'<rect x="{x - .5:.1f}" y="{py(hi):.1f}" width="1" height="{py(lo) - py(hi):.1f}" fill="{col}"/>'
            f'<rect x="{x - bw / 2:.1f}" y="{y1:.1f}" width="{bw}" height="{max(y2 - y1, 1.2):.1f}" fill="{col}"/>')
        window = [z[3] for z in ohlc[max(0, i - 3): i + 1]]
        ma.append((x, py(sum(window) / len(window))))
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in ma)
    art.append(f'<polyline points="{pts}" fill="none" stroke="#FFFFFF" stroke-opacity=".55" stroke-width="1.2"/>')
    poster("poster-stockbit-mcp.svg", "Stockbit MCP (unofficial), co-built by INo-xious and Garit32",
           "INo-xious × Garit32", "UNOFFICIAL", ("STOCKBIT", "MCP"), "".join(art))


def poster_engine():
    art = []
    cxp = PW / 2
    # search tree: root -> 3 -> 9 -> 27, principal variation in red
    levels = [[(cxp, 44)]]
    ys = [44, 78, 106, 128]
    for li in range(1, 4):
        k = 3 ** li
        span = [0, 150, 214, 246][li]
        levels.append([(cxp - span / 2 + span * (j + .5) / k, ys[li]) for j in range(k)])
    pv = [0, 2, 7, 22]  # principal variation: root -> right branch, drawn in red
    for li in range(1, 4):
        for j, (x, y) in enumerate(levels[li]):
            px_, py_ = levels[li - 1][j // 3]
            if not (j == pv[li] and j // 3 == pv[li - 1]):
                art.append(f'<path d="M{px_:.1f} {py_:.1f}L{x:.1f} {y:.1f}" stroke="#FFFFFF" stroke-opacity=".2" '
                           f'stroke-width=".8"/>')
    for li, row in enumerate(levels):
        for j, (x, y) in enumerate(row):
            if j != pv[li]:
                art.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{[3, 2.4, 1.8, 1.3][li]}" fill="#CFCFD4" '
                           f'fill-opacity=".55"/>')
    pv_pts = " ".join(f"{levels[li][pv[li]][0]:.1f},{levels[li][pv[li]][1]:.1f}" for li in range(4))
    art.append(f'<polyline points="{pv_pts}" fill="none" stroke="{RED_HI}" stroke-width="2"/>')
    for li in range(4):
        x, y = levels[li][pv[li]]
        art.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{[4, 3.2, 2.6, 2.2][li]}" fill="{RED_HI}"/>')
    # perspective board
    f_, cam_h, yh = 118.0, 3.0, 128.0

    def proj(X, Z):
        return cxp + f_ * X / Z, yh + f_ * cam_h / Z

    Zn, Zf = 3.6, 11.6
    for r in range(8):
        for q in range(8):
            X0, X1 = -4 + q, -3 + q
            Z0 = Zf - (Zf - Zn) * r / 8
            Z1 = Zf - (Zf - Zn) * (r + 1) / 8
            pp = [proj(X0, Z0), proj(X1, Z0), proj(X1, Z1), proj(X0, Z1)]
            if (r + q) % 2 == 0:
                fill, op = "#D8D8DD", 0.18 + 0.62 * r / 7
            else:
                fill, op = "#141418", 1
            d = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pp) + "Z"
            art.append(f'<path d="{d}" fill="{fill}" fill-opacity="{op:.2f}"/>')
    a, b = proj(-4, Zn), proj(4, Zn)
    art.append(f'<path d="M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}" stroke="{RED_HI}" stroke-width="1.4"/>')
    # king silhouette standing on the board (simple geometric chess king, silver gradient)
    kx, kb = cxp, proj(0, 6.3)[1] + 2
    king = (
        f"M{kx - 30} {kb}h60v-7h-4l-4-8h-44l-4 8h-4z"         # base
        f"M{kx - 21} {kb - 17}h42l-8-50h-26z"                 # body
        f"M{kx - 17} {kb - 70}h34v-7h-34z"                    # collar
        f"M{kx - 13} {kb - 80}h26l3-14h-32z"                  # crown
        f"M{kx - 3} {kb - 96}v-8h-7v-5h7v-7h6v7h7v5h-7v8z"    # cross
    )
    art.insert(0, '<linearGradient id="silver" x1="0" x2="1"><stop offset="0" stop-color="#7B7B83"/>'
                  '<stop offset=".38" stop-color="#F4F4F6"/><stop offset=".62" stop-color="#C9C9CF"/>'
                  '<stop offset="1" stop-color="#55555C"/></linearGradient>')
    art.append(f'<ellipse cx="{kx}" cy="{kb}" rx="54" ry="8" fill="#000" fill-opacity=".55"/>')
    art.append(f'<path d="{king}" fill="url(#silver)"/>')
    art.append(f'<path d="M{kx + 21} {kb - 17}l-8-50h-3l8 50z" fill="{RED_HI}" fill-opacity=".55"/>')
    # shifted down 8 units so the tree's root node clears the top credit
    poster("poster-marvelous-engine.svg", "Marvelous engine, in development",
           "INo-xious PRESENTS", "IN DEVELOPMENT", ("MARVELOUS", "ENGINE"),
           '<g transform="translate(0 8)">' + "".join(art) + "</g>")


def poster_idx():
    """A messy PDF page, scanned, rebuilt as a clean table with a confidence column. No text in the art."""
    rnd = random.Random(5)
    art = []
    # ghost letters behind the page, like Stockbit's ghost IDX
    pdf_d, _ = FONTS["display"].path("PDF", size=150, x=PW / 2, y=222, anchor="middle", tracking=0.01)
    art.append(f'<path d="{pdf_d}" fill="none" stroke="#FFFFFF" stroke-opacity=".07" stroke-width="1.2"/>')
    # the PDF page, rotated -6 degrees about its centre
    px, py, pw, ph = 22, 64, 118, 160
    rows = []
    for r in range(7):
        y = py + 22 + r * 19
        if r == 2:     # a wrapped address: the row breaks onto two short bars
            rows.append(f'<rect x="{px + 12}" y="{y}" width="{rnd.uniform(36, 44):.1f}" height="4" rx="1" fill="#5A5A63"/>')
            rows.append(f'<rect x="{px + 12}" y="{y + 7}" width="{rnd.uniform(22, 30):.1f}" height="4" rx="1" fill="#5A5A63"/>')
            x = px + 12 + 50 + rnd.uniform(-3, 3)
            rows.append(f'<rect x="{x:.1f}" y="{y}" width="{rnd.uniform(40, 48):.1f}" height="4" rx="1" fill="#5A5A63"/>')
            continue
        x = px + 10 + rnd.uniform(0, 6)
        for c in range(3):
            w = rnd.uniform(18, 34) if c < 2 else rnd.uniform(12, 22)
            rows.append(f'<rect x="{x:.1f}" y="{y + rnd.uniform(-1, 1):.1f}" width="{w:.1f}" height="4" rx="1" fill="#5A5A63"/>')
            if r == 4 and c == 1:   # duplicated glyphs: the same bar printed twice, slightly offset
                rows.append(f'<rect x="{x + 1.5:.1f}" y="{y + 1.5:.1f}" width="{w:.1f}" height="4" rx="1" fill="#5A5A63" '
                            f'fill-opacity=".5"/>')
            x += w + rnd.uniform(4, 10)
    art.append(f'<g transform="rotate(-6 {px + pw / 2} {py + ph / 2})">'
               f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="#16171B" stroke="#3A3A40"/>'
               f'<rect x="{px + 10}" y="{py + 10}" width="46" height="5" rx="1" fill="#6E6E78"/>'
               + "".join(rows) + '</g>')
    # scan beam across the page
    art.append(f'<rect x="{px - 6}" y="145" width="{126 - px + 6}" height="10" fill="{RED_HI}" fill-opacity=".18"/>'
               f'<rect x="{px - 6}" y="149" width="{126 - px + 6}" height="2" fill="{RED_HI}"/>')
    # clean table: 3 columns x 7 rows, 124 x 150 at (126, 84)
    tx, ty, tw, th = 126, 84, 124, 150
    cw, rh = tw / 3, th / 7
    tbl = [f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" fill="{NIGHT}"/>']
    lines = []
    for r in range(8):
        lines.append(f"M{tx} {ty + r * rh:.1f}H{tx + tw}")
    for c in range(4):
        lines.append(f"M{tx + c * cw:.1f} {ty}V{ty + th}")
    tbl.append(f'<path d="{"".join(lines)}" stroke="#E7E7E7" stroke-opacity=".45" stroke-width=".8"/>')
    conf = [0.90, 1.00, 0.70, 0.95, 0.60, 1.00, 0.85]
    for r in range(7):
        cy = ty + r * rh + rh / 2
        for c in range(2):
            tbl.append(f'<rect x="{tx + c * cw + 6:.1f}" y="{cy - 2.5:.1f}" width="{cw - 12:.1f}" height="5" rx="1" '
                       f'fill="#D9D9DE" fill-opacity=".7"/>')
        tbl.append(f'<rect x="{tx + 2 * cw + 6:.1f}" y="{cy - 2.5:.1f}" width="{(cw - 12) * conf[r]:.1f}" height="5" '
                   f'rx="1" fill="{RED_HI}"/>')
    art.append("".join(tbl))
    # chevron between the page and the table, at the end of the beam
    chev = "M111 140l10 10-10 10"
    art.append(f'<path d="{chev}" fill="none" stroke="#16171B" stroke-width="8"/>'
               f'<path d="{chev}" fill="none" stroke="#8B8B93" stroke-width="3"/>')
    poster("poster-idx-pipeline.svg", "IDX ownership pipeline",
           "INo-xious PRESENTS", "PDF → EXCEL", ("IDX", "OWNERSHIP"), "".join(art))


# =====================================================================================
# 5. AUDIT
# =====================================================================================
# (art width, smallest served CSS width): the card and 846-wide art shrink to the column of a 360 px phone
# (viewport - 82 = 278 px); full posters are only served at viewports >= 1012 px (182 px wide), thumbs below
# that (31.5% of 278 = 87 px on a 360 px phone)
SERVED = [("title-card.svg", 400, 278), ("slate-", 846, 278), ("still-", 846, 278),
          ("poster-*-thumb", 272, 87), ("poster-", 272, 182)]
MIN_PX = 10


def audit():
    bad = []
    names = sorted(f for f in os.listdir(OUT) if f.endswith(".svg"))
    for f in names:
        s = open(os.path.join(OUT, f), encoding="utf-8").read()
        size = len(s.encode())
        m = re.match(r'<svg xmlns="http://www.w3.org/2000/svg" width="([\d.]+)" height="([\d.]+)" '
                     r'viewBox="0 0 ([\d.]+) ([\d.]+)" role="img"', s)
        checks = {
            "root w/h == viewBox, role=img": bool(m) and m.group(1) == m.group(3) and m.group(2) == m.group(4),
            "no <text": "<text" not in s,
            "no http besides xmlns": s.count("http") == 1,
            "no href/url() to files": not re.search(r'href=|url\((?!#)', s),
            "<title> present": bool(re.search(r"<title[^>]*>[^<]+</title>", s)),
            "< 300 KB": size < 300 * 1024,
            "animates only if title card": (f == "title-card.svg") or ("animation" not in s and "@keyframes" not in s),
        }
        if f == "title-card.svg":
            checks["motion gated by prefers-reduced-motion"] = bool(
                re.search(r"@media \(prefers-reduced-motion: no-preference\)\{[^<]*@keyframes", s))
        art_w, served = next((w, sv) for k, w, sv in SERVED
                             if (f.endswith("-thumb.svg") if k == "poster-*-thumb" else f.startswith(k)))
        px = _min_size.get(f, 1e9) * served / art_w
        checks[f"smallest lettering >= {MIN_PX} CSS px when served ({px:.1f})"] = px >= MIN_PX
        failed = [k for k, ok in checks.items() if not ok]
        print(f"  {'ok  ' if not failed else 'FAIL'} {f:40s} {size / 1024:6.1f} KB  "
              f"min text {_min_size.get(f, 0):5.1f} u = {px:4.1f} px at {served} px"
              + (f"  <- {failed}" if failed else ""))
        bad += [(f, k) for k in failed]
    if len(names) != 17:
        bad.append(("assets/", f"expected 17 SVGs, found {len(names)}"))
    print(f"audit: {len(names)} files, {'PASS' if not bad else 'FAIL ' + str(bad)}")
    return not bad


if __name__ == "__main__":
    for old in os.listdir(OUT):
        if old.endswith(".svg"):
            os.remove(os.path.join(OUT, old))
    title_card()
    for num, slug, title, cap_text, alt in SLATES:
        for th in ("light", "dark"):
            slate(num, slug, title, cap_text, alt, th)
    for th in ("light", "dark"):
        still_perception(th)
    poster_stockbit()
    poster_engine()
    poster_idx()
    sys.exit(0 if audit() else 1)
