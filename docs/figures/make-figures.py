"""Draw the repository's figures from the tree.

    python3 -I docs/figures/make-figures.py           # write docs/figures/*.svg
    python3 -I docs/figures/make-figures.py --check   # exit 1 if a committed figure is out of date

Each figure is written twice, `<name>-light.svg` and `<name>-dark.svg`, for a
`<picture>` element. The namespace names, the two grant labels and the
NetworkPolicy names in `owner-grants` are read from deploy/ and
steps/4-policy/README.md; the script refuses to draw if one is missing.
Standard library only; the output is deterministic.
"""

# ---- Hello Galaxy figure kit (shared by the series; standard library only) ----
# One visual language for every Hello Galaxy figure: the token palette, type
# sizes, boxes, stage dots and arrows below. Each figure is written twice,
# <name>-light.svg and <name>-dark.svg, for a <picture> element; each file is
# self-contained (its colors are declared inside it; no remote font).

import os
import sys
from xml.sax.saxutils import escape

THEMES = {
    "light": "--ink:#191c22; --quiet:#555c68; --rule:#dde1e6; --line:#878f9c; --paper:#ffffff; "
             "--panel:#f5f6f8; --accent:#0b5a72; --accent-soft:#e2f0f4; --on-accent:#ffffff; "
             "--good:#2a6a35; --good-bg:#e4f3e6; --warn:#875200; --warn-bg:#fcf0d7; --info:#285d9e; "
             "--info-bg:#e6eff9; --crit:#b0261d; --crit-bg:#fbeae8; --mute:#5a606a; --mute-bg:#efeeeb;",
    "dark": "--ink:#e7e9ec; --quiet:#a5acb7; --rule:#30363e; --line:#7b8592; --paper:#121417; "
            "--panel:#1a1d21; --accent:#6cc3da; --accent-soft:#14303a; --on-accent:#121417; "
            "--good:#6fc480; --good-bg:#1b2e20; --warn:#e2b04e; --warn-bg:#32291a; --info:#86b3ea; "
            "--info-bg:#1a2636; --crit:#f08b80; --crit-bg:#3a1f1f; --mute:#9ba2ac; --mute-bg:#24262b;",
}
SANS = "'Helvetica Neue',Helvetica,Arial,'Liberation Sans',sans-serif"
MONO = "Menlo,Consolas,'Liberation Mono',monospace"
CLASSES = """
.t{fill:var(--ink)} .tq{fill:var(--quiet)} .ta{fill:var(--accent)} .tg{fill:var(--good)}
.tw{fill:var(--warn)} .ti{fill:var(--info)} .tc{fill:var(--crit)} .tm{fill:var(--mute)} .ton{fill:var(--on-accent)}
.bx{fill:var(--paper);stroke:var(--line);stroke-width:1.25} .bxp{fill:var(--panel);stroke:var(--rule);stroke-width:1.25}
.bxa{fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.25} .bxg{fill:var(--good-bg);stroke:var(--good);stroke-width:1.25}
.bxw{fill:var(--warn-bg);stroke:var(--warn);stroke-width:1.25} .bxi{fill:var(--info-bg);stroke:var(--info);stroke-width:1.25}
.bxc{fill:var(--crit-bg);stroke:var(--crit);stroke-width:1.25} .bxm{fill:var(--mute-bg);stroke:var(--mute);stroke-width:1.25}
.bxd{fill:var(--paper);stroke:var(--line);stroke-width:1.25;stroke-dasharray:5 4}
.bxz{fill:none;stroke:var(--accent);stroke-width:1.25;stroke-dasharray:6 4}
.ln{stroke:var(--line);stroke-width:1.5;fill:none} .lna{stroke:var(--accent);stroke-width:2.25;fill:none}
.lng{stroke:var(--good);stroke-width:2;fill:none} .lnw{stroke:var(--warn);stroke-width:2;fill:none}
.lnc{stroke:var(--crit);stroke-width:2;fill:none} .lnx{stroke:var(--crit);stroke-width:2;fill:none;stroke-dasharray:4 5}
.lnd{stroke:var(--line);stroke-width:1.25;fill:none;stroke-dasharray:6 5} .lnr{stroke:var(--rule);stroke-width:1;fill:none}
.fa{fill:var(--accent)} .fg{fill:var(--good)} .fl{fill:var(--line)} .fw{fill:var(--warn)} .fi{fill:var(--info)}
.fc{fill:var(--crit)} .fm{fill:var(--mute)} .fp{fill:var(--panel)} .fs{fill:var(--accent-soft)} .fpaper{fill:var(--paper)}
.mono{font-family:%s}
""" % MONO
HEAD = {"ln": "fl", "lna": "fa", "lng": "fg", "lnw": "fw", "lnc": "fc", "lnx": "fc", "lnd": "fl"}

TITLE = 20      # the finding, top left
LABEL = 15      # a box's name
SUB = 15        # the line under the title
BODY = 14       # everything else; never smaller


def n(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def tw(s, size, mono=False, bold=False):
    """Text width estimate for a system sans; generous on purpose."""
    if mono:
        return len(s) * size * 0.62
    w = 0.0
    for c in s:
        if c in "il.,:;|!'`·1 ":
            w += 0.30
        elif c in "ft()[]/-":
            w += 0.37
        elif c in "mwMW@%":
            w += 0.88
        elif c.isupper() or c in "0123456789≤≥→←":
            w += 0.66
        else:
            w += 0.56
    return w * size * (1.07 if bold else 1.0)


def wrap(s, width, size, mono=False, bold=False):
    out, line = [], ""
    for word in s.split(" "):
        t = word if not line else line + " " + word
        if tw(t, size, mono, bold) <= width or not line:
            line = t
        else:
            out.append(line)
            line = word
    if line:
        out.append(line)
    return out


class Fig:
    def __init__(self, w, h, title, alt):
        self.w, self.h, self.alt, self.parts = w, h, alt, []
        self.text(24, 38, title, TITLE, bold=True, role="title")

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, size=BODY, cls="t", anchor="start", bold=False, mono=False, role=None):
        if not mono and size < 13:
            raise SystemExit("text under 13 units: %r" % s)
        a = ' text-anchor="%s"' % anchor if anchor != "start" else ""
        b = ' font-weight="700"' if bold else ""
        r = ' data-role="%s"' % role if role else ""
        c = cls + (" mono" if mono else "")
        self.add('<text x="%s" y="%s" class="%s" font-size="%s"%s%s%s>%s</text>'
                 % (n(x), n(y), c, n(size), a, b, r, escape(s)))

    def sub(self, s):
        """The line under the title."""
        if tw(s, SUB) > self.w - 48:
            raise SystemExit("subtitle too long: %r" % s)
        self.text(24, 66, s, SUB, "tq")

    def lines(self, x, y, rows, size=BODY, lead=1.45, **kw):
        for i, r in enumerate(rows):
            self.text(x, y + i * size * lead, r, size, **kw)
        return y + len(rows) * size * lead

    def rect(self, x, y, w, h, cls="bx", rx=8):
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" class="%s"/>'
                 % (n(x), n(y), n(w), n(h), n(rx), cls))

    def box(self, x, y, w, h, cls, name, rows=(), name_cls="t", mono_rows=False, pad=14, center=False):
        """A box with a bold name and quiet rows under it."""
        self.rect(x, y, w, h, cls)
        cx = x + w / 2 if center else x + pad
        anc = "middle" if center else "start"
        self.text(cx, y + pad + LABEL * 0.8, name, LABEL, name_cls, anc, bold=True)
        yy = y + pad + LABEL * 0.8 + BODY * 1.5
        for r in rows:
            self.text(cx, yy, r, BODY, "tq", anc, mono=mono_rows)
            yy += BODY * 1.45

    def circle(self, x, y, r, cls):
        self.add('<circle cx="%s" cy="%s" r="%s" class="%s"/>' % (n(x), n(y), n(r), cls))

    def dot(self, x, y, label, cls="fa"):
        """A numbered stage dot, as in every Hello Galaxy figure."""
        self.circle(x, y, 15, cls)
        self.text(x, y + 4.6, str(label), 13, "ton", "middle", bold=True)

    def path(self, d, cls="ln"):
        self.add('<path d="%s" class="%s"/>' % (d, cls))

    def arrow(self, pts, cls="ln", head=True, size=10):
        """A polyline through pts, with a filled head at the last point."""
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        if head:
            dx, dy = x2 - x1, y2 - y1
            L = (dx * dx + dy * dy) ** 0.5 or 1
            ux, uy = dx / L, dy / L
            bx, by = x2 - ux * size, y2 - uy * size
            pts = pts[:-1] + [(bx + ux, by + uy)]
            px, py = -uy * size * 0.5, ux * size * 0.5  # 10 long by 10 wide
            self.add('<path d="M%s %sL%s %sL%s %sz" class="%s"/>'
                     % (n(x2), n(y2), n(bx + px), n(by + py), n(bx - px), n(by - py), HEAD.get(cls, "fl")))
        d = "M" + "L".join("%s %s" % (n(x), n(y)) for x, y in pts)
        self.path(d, cls)

    def tick(self, x, y, cls="fg"):
        """A filled check mark disc."""
        self.circle(x, y, 10, cls)
        self.add('<path d="M%s %sl3.6 3.6l6.4-7.2" style="stroke:var(--paper);stroke-width:2.4;fill:none;'
                 'stroke-linecap:round;stroke-linejoin:round"/>' % (n(x - 5), n(y)))

    def cross(self, x, y, cls="fc"):
        """A filled cross disc."""
        self.circle(x, y, 10, cls)
        self.add('<path d="M%s %sl8 8M%s %sl-8 8" style="stroke:var(--paper);stroke-width:2.4;'
                 'stroke-linecap:round"/>' % (n(x - 4), n(y - 4), n(x + 4), n(y - 4)))

    def render(self, theme):
        style = "svg{%s font-family:%s}%s" % (THEMES[theme], SANS, CLASSES)
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s" '
                'role="img" aria-label="%s"><style>%s</style>\n%s\n</svg>\n'
                % (n(self.w), n(self.h), n(self.w), n(self.h), escape(self.alt, {'"': "&quot;"}),
                   style, "\n".join(self.parts)))


def write_all(figures, here, argv):
    """figures: {name: Fig}. Write <name>-light/-dark.svg, or with --check report drift."""
    check = "--check" in argv
    stale = []
    for name, fig in figures.items():
        for theme in ("light", "dark"):
            path = os.path.join(here, "%s-%s.svg" % (name, theme))
            body = fig.render(theme)
            if check:
                try:
                    with open(path, encoding="utf-8") as f:
                        if f.read() != body:
                            stale.append(path)
                except FileNotFoundError:
                    stale.append(path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
                print("wrote", os.path.relpath(path, os.path.dirname(os.path.dirname(here))))
    if check:
        for p in stale:
            print("out of date:", p, file=sys.stderr)
        if stale:
            print("run: python3 -I docs/figures/make-figures.py", file=sys.stderr)
            return 1
        print("figures up to date")
    return 0
# ---- end of the Hello Galaxy figure kit ----


import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def tree_text(*rel):
    out = []
    for r in rel:
        p = os.path.join(ROOT, r)
        if os.path.isdir(p):
            for d, _, fs in sorted(os.walk(p)):
                for f in sorted(fs):
                    if f.endswith((".yaml", ".yml")):
                        with open(os.path.join(d, f), encoding="utf-8") as h:
                            out.append(h.read())
        else:
            with open(p, encoding="utf-8") as h:
                out.append(h.read())
    return "\n".join(out)


def facts():
    deploy = tree_text("deploy")
    step4 = tree_text("steps/4-policy/README.md")
    want = {
        "app": "record-consumers", "edge": "record-edge", "viewer": "record-viewer",
        "stranger": "record-stranger", "posts": "record-consumers/posts-records",
        "reads": "record-consumers/reads-board", "np_post": "receiver-accepts-records",
        "np_read": "board-serves-readers",
    }
    for k, v in want.items():
        if v not in deploy and v not in step4:
            raise SystemExit("owner-grants: %r (%s) is no longer in deploy/ or step 4" % (v, k))
    m = re.search(r"\| \[\*\*3 cluster\*\*\].*?first-bite decoded (\d+) frames.*?receiver stored (\d+), "
                  r"the board shows (\d+) rows", tree_text("README.md"))
    if not m:
        raise SystemExit("owner-grants: step 3's proof line in README.md changed")
    want.update(frames=m.group(1), stored=m.group(2), rows=m.group(3))
    return want


def fig_owner_grants():
    F = facts()
    f = Fig(880, 462, "Records go in and the board comes out only where the owner puts a label",
            "In a kind cluster, first-bite in the namespace %s posts its decoded records to the "
            "receiver, which makes its tables from the dictionary's JSON Schema and writes PostgreSQL; "
            "the board reads with a role that cannot write and serves %s; the namespace %s, "
            "with no label, gets no answer from the receiver, the board or the database."
            % (F["edge"], F["viewer"], F["stranger"]))
    f.sub("Step 3 runs it in a kind cluster; step 4 tries every path with and without "
                   "the grant.")

    # the owner's namespace
    SW, GAP = 176, 66
    ZX = 20 + SW + GAP
    ZY, ZW, ZH = 96, 880 - 2 * (20 + SW + GAP), 346
    f.rect(ZX, ZY, ZW, ZH, "bxa", rx=12)
    f.text(ZX + 16, ZY + 26, "namespace " + F["app"], BODY, "ta", bold=True, mono=True)
    IX, IW = ZX + 16, ZW - 32
    f.box(IX, ZY + 42, IW, 62, "bxd", "JSON Schema", ["exported by bite schema"])
    RY, RW = ZY + 138, (IW - 24) / 2
    f.box(IX, RY, RW, 82, "bx", "receiver", ["a table per", "message"])
    BX = IX + RW + 24
    f.box(BX, RY, RW, 82, "bx", "board", ["latest per", "source"])
    DY = RY + 82 + 46
    f.box(IX, DY, IW, 62, "bxp", "PostgreSQL", ["two roles"])
    f.arrow([(IX + RW / 2, ZY + 104), (IX + RW / 2, RY)], "ln")
    f.arrow([(IX + RW / 2, RY + 82), (IX + RW / 2, DY)], "ln")
    f.text(IX + RW / 2 + 8, RY + 82 + 28, "writes", BODY, "tq")
    f.arrow([(BX + RW / 2, DY), (BX + RW / 2, RY + 82)], "ln")
    f.text(BX + RW / 2 + 8, RY + 82 + 28, "reads only", BODY, "tq")

    # granted: the decoder posts
    EX, EY, EH = 20, RY - 20, 122
    f.box(EX, EY, SW, EH, "bxg", F["edge"], [], name_cls="tg")
    f.text(EX + 14, EY + 56, "first-bite decoder", BODY, "t")
    f.text(EX + 14, EY + 78, "label", BODY, "tq")
    f.text(EX + 14 + tw("label ", BODY), EY + 78, "posts-records", BODY, "t", mono=True)
    f.text(EX + 14, EY + 102, "%s frames decoded" % F["frames"], BODY, "tq")
    f.arrow([(EX + SW, RY + 41), (IX, RY + 41)], "lng")
    f.text(EX + SW + GAP / 2 + 8, RY + 32, "POST", BODY, "tg", "middle", bold=True)

    # granted: a reader opens the board
    VX = 880 - 20 - SW
    f.box(VX, EY, SW, EH, "bxg", F["viewer"], [], name_cls="tg")
    f.text(VX + 14, EY + 56, "a reader", BODY, "t")
    f.text(VX + 14, EY + 78, "label", BODY, "tq")
    f.text(VX + 14 + tw("label ", BODY), EY + 78, "reads-board", BODY, "t", mono=True)
    f.text(VX + 14, EY + 102, "the board: %s rows" % F["rows"], BODY, "tq")
    f.arrow([(BX + RW, RY + 41), (VX, RY + 41)], "lng")
    f.text(VX - GAP / 2 - 8, RY + 32, "GET", BODY, "tg", "middle", bold=True)

    # not granted
    SY = EY + EH + 18
    f.box(EX, SY, SW, ZY + ZH - SY, "bxc", F["stranger"], [], name_cls="tc")
    f.text(EX + 14, SY + 56, "no label: no answer", BODY, "tq")
    f.text(EX + 14, SY + 76, "from any of the three", BODY, "tq")
    f.arrow([(EX + SW, SY + 46), (ZX, SY + 46)], "lnx", head=False)
    f.cross(ZX, SY + 46)
    return f


def main(argv):
    return write_all({"owner-grants": fig_owner_grants()}, HERE, argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
