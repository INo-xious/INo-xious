"""Text -> SVG path outlines with GPOS pair kerning, so SVGs render identically without webfonts.

GitHub serves README images through <img>, which can't load external fonts, so every piece of
lettering in the assets is converted to outlines with this module.

    from textpath import FONTS
    d, w = FONTS["display"].path("MARVEL", size=120, x=0, y=100, anchor="middle", tracking=0.02)
"""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

FONT_DIR = Path(__file__).parent / "fonts"

FONT_FILES = {
    # all SIL OFL 1.1: see fonts/OFL.txt
    "display": FONT_DIR / "Oswald-Bold.ttf",
    "mono": FONT_DIR / "JetBrainsMono-Regular.ttf",
    "mono-bold": FONT_DIR / "JetBrainsMono-Bold.ttf",
    "mono-xbold": FONT_DIR / "JetBrainsMono-ExtraBold.ttf",
}


def _fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class _RoundingPen(SVGPathPen):
    """SVGPathPen with 2-decimal output to keep files small."""

    def __init__(self, glyphSet):
        super().__init__(glyphSet, ntos=_fmt)


class Font:
    def __init__(self, path):
        self.tt = TTFont(path)
        self.upem = self.tt["head"].unitsPerEm
        self.cmap = self.tt.getBestCmap()
        self.gs = self.tt.getGlyphSet()
        self.hmtx = self.tt["hmtx"]
        self.ascender = self.tt["hhea"].ascent
        self.descender = self.tt["hhea"].descent
        os2 = self.tt["OS/2"]
        self.cap_height = getattr(os2, "sCapHeight", 0) or int(self.ascender * 0.7)
        self.x_height = getattr(os2, "sxHeight", 0) or int(self.ascender * 0.5)
        self._pairs = {}
        self._class_pairs = []
        self._load_kerning()

    def _load_kerning(self):
        if "GPOS" not in self.tt:
            return
        gpos = self.tt["GPOS"].table
        if not gpos.FeatureList:
            return
        idx = set()
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "kern":
                idx.update(fr.Feature.LookupListIndex)
        for li in sorted(idx):
            lookup = gpos.LookupList.Lookup[li]
            for st in lookup.SubTable:
                if lookup.LookupType == 9:
                    st = st.ExtSubTable
                if getattr(st, "LookupType", 2) != 2 and lookup.LookupType not in (2, 9):
                    continue
                if not hasattr(st, "Format"):
                    continue
                if st.Format == 1:
                    for g1, ps in zip(st.Coverage.glyphs, st.PairSet):
                        for rec in ps.PairValueRecord:
                            v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
                            if v and (g1, rec.SecondGlyph) not in self._pairs:
                                self._pairs[(g1, rec.SecondGlyph)] = v
                elif st.Format == 2:
                    self._class_pairs.append(st)

    def kern(self, g1, g2):
        if (g1, g2) in self._pairs:
            return self._pairs[(g1, g2)]
        for st in self._class_pairs:
            if g1 not in st.Coverage.glyphs:
                continue
            c1 = st.ClassDef1.classDefs.get(g1, 0)
            c2 = st.ClassDef2.classDefs.get(g2, 0)
            rec = st.Class1Record[c1].Class2Record[c2]
            v = getattr(rec.Value1, "XAdvance", 0) if rec.Value1 else 0
            if v:
                return v
        return 0

    def glyphs(self, text):
        return [self.cmap.get(ord(ch), ".notdef") for ch in text]

    def measure(self, text, size, tracking=0.0):
        s = size / self.upem
        names = self.glyphs(text)
        w = 0
        for i, g in enumerate(names):
            w += self.hmtx[g][0]
            if i + 1 < len(names):
                w += self.kern(g, names[i + 1])
        return w * s + tracking * size * max(len(names) - 1, 0)

    def path(self, text, size, x=0.0, y=0.0, anchor="start", tracking=0.0, skew=0.0, sx=1.0):
        """Return (d, width). y is the baseline. tracking is in em. skew (deg) fakes an oblique; sx squashes."""
        import math
        s = size / self.upem
        width = self.measure(text, size, tracking) * sx
        if anchor == "middle":
            x -= width / 2
        elif anchor == "end":
            x -= width
        pen = _RoundingPen(self.gs)
        names = self.glyphs(text)
        cx = 0.0
        k = math.tan(math.radians(skew))
        for i, g in enumerate(names):
            # TransformPen matrix (xx, xy, yx, yy, dx, dy): x' = sx*s*gx + k*s*gy + X, y' = -s*gy + Y
            tp = TransformPen(pen, (sx * s, 0, k * s, -s, x + cx, y))
            self.gs[g].draw(tp)
            adv = self.hmtx[g][0]
            if i + 1 < len(names):
                adv += self.kern(g, names[i + 1])
            cx += (adv * s + tracking * size) * sx
        return pen.getCommands(), width


class _Fonts(dict):
    def __missing__(self, key):
        f = Font(FONT_FILES[key])
        self[key] = f
        return f


FONTS = _Fonts()
