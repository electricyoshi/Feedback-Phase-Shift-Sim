#!/usr/bin/env python3
"""
Feedback & Phase Shift demo  (EE3722, Module 4.2 - "The stability problem")

Two views of the classic feedback block diagram  Vdiff = Vin - B*Vout :

  1. Summing junction only - the feedback signal is just a copy of Vin with an
     adjustable amplitude and phase lag.  Watch Vdiff shrink when the two are
     in phase and grow past |Vin| as the lag approaches and passes 180 degrees.

  2. Full closed loop - a time-domain simulation of an amplifier A with
     feedback B and +/-Vcc rails.  The slider sets the phase lag of the loop
     gain A*B at the frequency where |A*B| = 1.  Past 180 degrees the output
     oscillates and grows until it hits the rails.

Runs on the Python standard library only (tkinter).  Python 3.8+.
feedback_phase_sim.html is a parallel browser version: keep the two in step
(see "Parity" in CLAUDE.md).
    python feedback_phase_sim.py
"""

import bisect
import math
import random
import re
import time
import tkinter as tk
import tkinter.font as tkfont

# --------------------------------------------------------------------------
# Loop model:  A(s) = A0 * exp(-s*tau) / (1 + s/wp),  feedback factor BETA.
# The delay tau stands in for the "excess phase" of an amplifier's higher
# poles: it adds phase lag without changing |A*B|, so the phase slider moves
# the phase curve of the Bode plot and nothing else.
# --------------------------------------------------------------------------
A0 = 200.0          # open-loop DC gain (46 dB)
BETA = 0.5          # feedback factor -> ideal closed-loop gain 1/BETA = 2
FP = 1.0e3          # dominant pole, Hz
VCC = 5.0           # supply rails, +/- volts
L0 = A0 * BETA      # DC loop gain (40 dB)
FC = FP * math.sqrt(L0 * L0 - 1.0)              # |A*B| = 1 crossover, Hz
POLE_PHASE_FC = math.degrees(math.atan(FC / FP))  # lag of the pole alone at FC


def loop_mag(f):
    return L0 / math.hypot(1.0, f / FP)


def loop_phase(f, tau):
    """Phase LAG of A*B in degrees (positive number)."""
    return math.degrees(math.atan(f / FP)) + 360.0 * f * tau


def tau_for_crossover_phase(phi_deg):
    return max(0.0, phi_deg - POLE_PHASE_FC) / (360.0 * FC)


def freq_for_phase(phi_deg, tau):
    """Frequency at which the loop phase lag equals phi_deg (None if never)."""
    lo, hi = 0.0, 9.0   # log10 Hz
    if loop_phase(10 ** hi, tau) < phi_deg:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if loop_phase(10 ** mid, tau) < phi_deg:
            lo = mid
        else:
            hi = mid
    return 10 ** hi


# Fixed excess delay used for the Bode plot in view 1 (150 deg at crossover).
TAU_VIEW1 = tau_for_crossover_phase(150.0)


class LoopSim:
    """Time-domain closed loop with rail saturation (forward Euler + delay line)."""
    DT = 2.5e-8
    MASK = 1023
    NOISE = 2e-3     # tiny disturbance so an unstable loop can start by itself

    def __init__(self):
        self.reset()

    def reset(self):
        self.t = 0.0
        self.y = 0.0
        self.ph = 0.0
        self.i = 0
        self.cnt = 0
        self.hist = [0.0] * (self.MASK + 1)
        self.T, self.VIN, self.VOUT, self.VD = [], [], [], []

    def run(self, n, amp, freq, square, tau, rec):
        dt, mask, hist = self.DT, self.MASK, self.hist
        i, y, ph, t, cnt = self.i, self.y, self.ph, self.t, self.cnt
        # forward Euler lags an ideal integrator by half a sample: take it
        # out of the delay line so the loop phase is exactly what was asked.
        d = max(0.0, tau / dt - 0.5)
        k = int(d)
        fr = d - k
        fr1 = 1.0 - fr
        dph = 2.0 * math.pi * freq * dt
        g = dt * 2.0 * math.pi * FP
        pi, twopi, sin, rnd = math.pi, 2.0 * math.pi, math.sin, random.random
        noise, a0, beta, vcc = self.NOISE, A0, BETA, VCC
        T, VIN, VOUT, VD = self.T, self.VIN, self.VOUT, self.VD
        for _ in range(n):
            ph += dph
            if ph >= twopi:
                ph -= twopi
            if square:
                vin = amp if ph < pi else -amp
            else:
                vin = amp * sin(ph)
            j = (i - k) & mask
            vout = hist[j] * fr1 + hist[(j - 1) & mask] * fr
            vd = vin - beta * vout
            y += g * (a0 * (vd + (rnd() - 0.5) * noise) - y)
            if y > vcc:
                y = vcc
            elif y < -vcc:
                y = -vcc
            i = (i + 1) & mask
            hist[i] = y
            t += dt
            cnt += 1
            if cnt >= rec:
                cnt = 0
                T.append(t)
                VIN.append(vin)
                VOUT.append(vout)
                VD.append(vd)
        self.i, self.y, self.ph, self.t, self.cnt = i, y, ph, t, cnt

    def trim(self, span):
        i0 = bisect.bisect_left(self.T, self.t - span)
        if i0 > 200:
            del self.T[:i0], self.VIN[:i0], self.VOUT[:i0], self.VD[:i0]


# --------------------------------------------------------------------------
# Projector look: white background, bold type, thick lines, colour-blind-safe
# (Okabe-Ito) palette.  V_FB is black AND dashed so it reads without colour.
#
# Every size below is in "stage px" on a 1024 x 768 design stage and is
# multiplied by Z = min(win_w / 1024, win_h / 768) when drawn, so the layout
# fills whatever 4:3 window (or projector) it gets.  Z already includes the
# screen DPI because it comes from the window's real pixel size; fonts use
# negative (pixel) sizes so Tk doesn't scale them by DPI a second time.
# --------------------------------------------------------------------------
C_VIN = "#0072B2"
C_FB = "#111111"
C_DIFF = "#D55E00"
C_OUT = "#009E73"
C_OFF = "#6B7075"       # loop parts that aren't connected (view 1)
C_GRID = "#D0D4D9"
C_ZERO = "#777777"
C_INK = "#111111"       # frames, ticks, titles, wires
C_GOOD = "#00735C"
C_BAD = "#B84300"
C_MID = "#555555"       # neutral banner, |Aβ| = 1 markers, ±V_CC lines
C_CIRCLE = "#DDF3EC"    # phasor unit-circle fill
C_PAXIS = "#B0B5BB"     # phasor axes
BG = "#FFFFFF"
DASH = (9, 6)

STAGE_W, STAGE_H = 1024, 768
Z = 1.0                 # stage px -> screen px (see above)
FAMILY = "Arial"        # replaced by the Tk default if Arial is missing


def zs(v):
    """Stage px -> whole screen px (never 0, so borders don't vanish)."""
    return max(1, int(round(v * Z)))


def zdash(dash):
    return tuple(zs(d) for d in dash) if dash else None


def dashed_line(cv, x0, y0, x1, y1, width, dash, color, tags=()):
    """A wide dashed straight line.  Tk on Windows draws any dashed line
    wider than 1 px as dots, but 1-px dashes come out right - so stack 1-px
    dashed lines side by side (half-pixel steps so diagonals have no gaps)."""
    ln = math.hypot(x1 - x0, y1 - y0)
    if ln < 1:
        return
    nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
    n = max(1, int(round(width * 2)))
    for i in range(n):
        d = (i - (n - 1) / 2.0) * 0.5
        cv.create_line(x0 + nx * d, y0 + ny * d, x1 + nx * d, y1 + ny * d, fill=color,
                       width=1, dash=dash, capstyle="butt", tags=tags)


_fonts = {}             # stage px -> bold Font


def bold(px):
    f = _fonts.get(px)
    if f is None:
        f = _fonts[px] = tkfont.Font(family=FAMILY, size=-max(6, round(px * Z)),
                                     weight="bold")
    return f


def nice_ticks(lo, hi, n=6):
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = 10 * mag
    for m in (1, 2, 2.5, 5):
        if raw <= m * mag:
            step = m * mag
            break
    v = math.ceil(lo / step - 1e-9) * step
    out = []
    while v <= hi + step * 1e-6:
        out.append(0.0 if abs(v) < step * 1e-9 else v)
        v += step
    return out


def fmt_num(v):
    return ("%.3g" % v).replace("-", "−")


def fmt_freq(f):
    if f >= 1e6:
        return "%gM" % (f / 1e6)
    if f >= 1e3:
        return "%gk" % (f / 1e3)
    return "%g" % f


def fmt_hz(f):
    return fmt_freq(float("%.3g" % f)) + "Hz"


# --------------------------------------------------------------------------
# Subscripts.  UI strings use a tiny markup, "V_{DIFF}", for a subscript.
# Unicode has no uppercase subscript letters and Tk labels can't mix font
# sizes, so subscripts are drawn as separate runs in a smaller, lowered font:
# draw_rich() on canvases, RichText for wrapped text in the notes window.
# --------------------------------------------------------------------------
SUB_RE = re.compile(r"_\{([^}]*)\}")
_sub_fonts = {}         # str(main font) -> (main font, subscript font)


def rich_parts(markup):
    """'V_{DIFF} = x' -> [('V', False), ('DIFF', True), (' = x', False)]"""
    return [(p, i % 2 == 1) for i, p in enumerate(SUB_RE.split(markup)) if p]


def _sub_size(font):
    size = int(round(int(font.cget("size")) * 0.68))   # negative = pixels
    if abs(size) < 6:
        size = 6 if size >= 0 else -6
    return size


def sub_font(font):
    key = str(font)
    if key not in _sub_fonts:
        a = font.actual()
        _sub_fonts[key] = (font, tkfont.Font(family=a["family"], size=_sub_size(font),
                                             weight=a["weight"], slant=a["slant"]))
    return _sub_fonts[key][1]


def rescale_fonts():
    """Resize every font for the current Z.  Named fonts update in place, so
    widgets already using them follow; canvases still need a redraw."""
    for px, f in _fonts.items():
        f.configure(size=-max(6, round(px * Z)))
    for main, sub in _sub_fonts.values():
        sub.configure(size=_sub_size(main))


def sub_drop(font):
    """How far a subscript's baseline sits below the main baseline, px
    (about 0.3 x the font size)."""
    return int(round(font.metrics("ascent") * 0.33))


def rich_width(font, markup):
    return sum((sub_font(font) if sub else font).measure(t)
               for t, sub in rich_parts(markup))


def draw_rich(cv, x, y, markup, font, fill, anchor="center", tags=()):
    """Canvas create_text() that understands V_{SUB} (single line only)."""
    w = rich_width(font, markup)
    if anchor == "center":      # its letters include "n" and "e" - not a compass point
        anchor = ""
    asc, h = font.metrics("ascent"), font.metrics("linespace")
    left = x if "w" in anchor else x - w if "e" in anchor else x - w / 2
    top = y if "n" in anchor else y - h if "s" in anchor else y - h / 2
    base, sf, drop = top + asc, sub_font(font), sub_drop(font)
    for text, sub in rich_parts(markup):
        f = sf if sub else font
        # anchor "sw" puts the bottom of the line box (baseline + descent) at y
        cv.create_text(left, base + (drop if sub else 0) + f.metrics("descent"),
                       text=text, anchor="sw", font=f, fill=fill, tags=tags)
        left += f.measure(text)


def draw_runs(cv, x, y, runs, font, anchor="w", tags=()):
    """draw_rich() for several differently coloured runs on one line.
    runs = [(markup, colour), ...]; anchor is "w", "e" or "center"."""
    w = sum(rich_width(font, m) for m, _ in runs)
    left = x if anchor == "w" else x - w if anchor == "e" else x - w / 2
    for m, color in runs:
        draw_rich(cv, left, y, m, font, color, "w", tags)
        left += rich_width(font, m)
    return w


# --------------------------------------------------------------------------
# Minimal plotting on a tk Canvas
# --------------------------------------------------------------------------
class Plot:
    def __init__(self, parent, title="", xrange=(0, 1), yrange=(-1, 1), logx=False,
                 xunit="", xticks=None, yticks=None, xfmt=fmt_num, show_x=True):
        # tiny requested size: the grid's weights decide the real size
        self.cv = tk.Canvas(parent, bg=BG, highlightthickness=0, width=10, height=10)
        self.title, self.xunit = title, xunit
        self.xr, self.yr = xrange, yrange
        self.logx, self.xticks, self.yticks = logx, xticks, yticks
        self.xfmt, self.show_x = xfmt, show_x
        self.hlines = []          # (y, color, text, text_below_line)
        self.series = {}          # name -> dict
        self.dyn = {}             # name -> (kind, kwargs)
        self.dyn_items = {}
        self.fast = False
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self._geom()

    # geometry / transforms
    def _geom(self):
        w, h = max(self.cv.winfo_width(), 50), max(self.cv.winfo_height(), 50)
        self.l, self.r = 46 * Z, w - 10 * Z
        self.t, self.b = 30 * Z, h - (24 if self.show_x else 8) * Z
        x0, x1 = self.xr
        if self.logx:
            x0, x1 = math.log10(x0), math.log10(x1)
        self._x0, self._ax = x0, (self.r - self.l) / (x1 - x0)
        self._y0, self._ay = self.yr[0], (self.b - self.t) / (self.yr[1] - self.yr[0])

    def px(self, x):
        if self.logx:
            x = math.log10(max(x, 1e-12))
        return min(self.r, max(self.l, self.l + (x - self._x0) * self._ax))

    def py(self, y):
        return min(self.b, max(self.t, self.b - (y - self._y0) * self._ay))

    # configuration
    def configure(self, xrange=None, yrange=None, xunit=None, title=None, yticks=None):
        new = (xrange or self.xr, yrange or self.yr,
               self.xunit if xunit is None else xunit,
               self.title if title is None else title,
               self.yticks if yticks is None else yticks)
        if new != (self.xr, self.yr, self.xunit, self.title, self.yticks):
            self.xr, self.yr, self.xunit, self.title, self.yticks = new
            self.redraw()

    def add_series(self, name, color, label=None, width=2.0, dash=None):
        self.series[name] = dict(item=None, thin=[], built=None, color=color,
                                 label=label, width=width, dash=dash, xs=(), ys=(),
                                 visible=True)

    def style(self, name, width=None, dash=False, label=None):
        """Change a series' width / dash / legend label (takes effect on redraw)."""
        s = self.series[name]
        if width is not None:
            s["width"] = width
        if dash is not False:
            s["dash"] = dash
        if label is not None:
            s["label"] = label

    def _build(self, s):
        """(Re)create a series' canvas lines for the current width, dash and Z."""
        cv = self.cv
        for item in [s["item"]] + s["thin"]:
            if item is not None:
                cv.delete(item)
        dash = zdash(s["dash"])
        s["item"] = cv.create_line(-9, -9, -9, -9, fill=s["color"], width=s["width"] * Z,
                                   dash=dash, joinstyle="miter", capstyle="butt")
        # Tk draws wide polylines very slowly, and wide dashed ones as dots
        # on Windows; for animated or dashed traces the same thickness is
        # built from 1-px lines offset both sideways and up/down - one
        # direction alone goes thin on slopes.
        n = max(2, int(round(s["width"] * Z)))
        ds = [i - (n - 1) / 2.0 for i in range(n)]
        offs = sorted({(d, 0.0) for d in ds} | {(0.0, d) for d in ds})
        s["thin"] = [cv.create_line(-9, -9, -9, -9, fill=s["color"], width=1, dash=dash)
                     for _ in offs]
        s["offs"] = offs
        s["built"] = (s["width"], s["dash"], Z)

    def set_fast(self, fast):
        self.fast = fast
        for s in self.series.values():
            self._plot(s)

    def show(self, name, visible):
        s = self.series[name]
        if s["visible"] != visible:
            s["visible"] = visible
            self.redraw()

    def set_data(self, name, xs, ys):
        s = self.series[name]
        s["xs"], s["ys"] = xs, ys
        self._plot(s)

    def _plot(self, s):
        if s["item"] is None:
            return
        if not s["visible"] or len(s["xs"]) < 2:
            for item in [s["item"]] + s["thin"]:
                self.cv.coords(item, -9, -9, -9, -9)
            return
        l, r, t, b = self.l, self.r, self.t, self.b
        x0, ax, y0, ay = self._x0, self._ax, self._y0, self._ay
        pts = []
        add = pts.append
        if self.logx:
            xs = [math.log10(x) for x in s["xs"]]
        else:
            xs = s["xs"]
        for x, y in zip(xs, s["ys"]):
            p = l + (x - x0) * ax
            q = b - (y - y0) * ay
            add(l if p < l else r if p > r else p)
            add(t if q < t else b if q > b else q)
        if self.fast or s["dash"]:      # dashed: see dashed_line()
            self.cv.coords(s["item"], -9, -9, -9, -9)
            for item, (ox, oy) in zip(s["thin"], s["offs"]):
                if ox:
                    c = pts[:]
                    c[0::2] = [v + ox for v in pts[0::2]]
                elif oy:
                    c = pts[:]
                    c[1::2] = [v + oy for v in pts[1::2]]
                else:
                    c = pts
                self.cv.coords(item, *c)
        else:
            self.cv.coords(s["item"], *pts)
            for item in s["thin"]:
                self.cv.coords(item, -9, -9, -9, -9)

    # dynamic annotations: kind in {"vline", "dot", "text"}
    def put(self, name, kind, **kw):
        self.dyn[name] = (kind, kw)
        self._place(name)

    def _place(self, name):
        kind, kw = self.dyn[name]
        cv = self.cv
        if kind == "vline":     # several items when dashed: redrawn each time
            tag = "dyn_" + name
            cv.delete(tag)
            x = kw.get("x")
            if x is None or not (self.xr[0] <= x <= self.xr[1]):
                return
            p, tags = self.px(x), (tag, "vline")
            if kw.get("dash"):
                dashed_line(cv, p, self.t, p, self.b, 3 * Z, zdash(kw["dash"]),
                            kw["color"], tags)
            else:
                cv.create_line(p, self.t, p, self.b, fill=kw["color"], width=3 * Z,
                               tags=tags)
            self._restack()
            return
        item = self.dyn_items.get(name)
        if item is None:
            if kind == "dot":
                item = cv.create_oval(0, 0, 0, 0, outline=BG, tags="dot")
            else:
                item = cv.create_text(0, 0, tags="dot")
            self.dyn_items[name] = item
        x = kw.get("x")
        if x is None or not (self.xr[0] <= x <= self.xr[1]):
            cv.itemconfigure(item, state="hidden")
            return
        cv.itemconfigure(item, state="normal")
        p = self.px(x)
        if kind == "dot":
            q, rad = self.py(kw["y"]), 8 * Z
            cv.coords(item, p - rad, q - rad, p + rad, q + rad)
            cv.itemconfigure(item, fill=kw["color"], width=2.5 * Z)
        else:
            q = self.py(kw["y"]) if "y" in kw else self.t
            cv.coords(item, p + kw.get("dx", 0) * Z, q + kw.get("dy", 0) * Z)
            cv.itemconfigure(item, text=kw["text"], fill=kw["color"], font=bold(16),
                             anchor=kw.get("anchor", "w"))

    def _restack(self):
        """Back to front: grid/axes, marker lines, traces, frame + labels, dots."""
        cv = self.cv
        cv.tag_lower("vline")
        cv.tag_lower("static")
        cv.tag_raise("top")
        cv.tag_raise("dot")

    # static decorations
    def redraw(self):
        self._geom()
        cv = self.cv
        cv.delete("static")
        for s in self.series.values():
            if s["built"] != (s["width"], s["dash"], Z):
                self._build(s)
        l, r, t, b = self.l, self.r, self.t, self.b
        st, top = ("static",), ("static", "top")
        ft = bold(15)
        if self.xticks:
            xt = [v for v in self.xticks if self.xr[0] <= v <= self.xr[1]]
        else:
            xt = [v for v in nice_ticks(self.xr[0], self.xr[1], 4)
                  if self.xr[0] <= v <= self.xr[1]]
        for i, v in enumerate(xt):
            p = self.px(v)
            cv.create_line(p, t, p, b, fill=C_GRID, width=2 * Z, tags=st)
            if self.show_x:
                # the unit rides on the last tick label instead of an axis title
                txt = self.xfmt(v)
                if i == len(xt) - 1 and self.xunit:
                    txt += " " + self.xunit
                tw = ft.measure(txt)
                cv.create_text(min(r - tw, max(l, p - tw / 2)), b + 14 * Z, text=txt,
                               anchor="w", font=ft, fill=C_INK, tags=st)
        for v in (self.yticks or nice_ticks(self.yr[0], self.yr[1], 5)):
            q = self.py(v)
            cv.create_line(l, q, r, q, fill=C_ZERO if v == 0 else C_GRID, width=2 * Z,
                           tags=st)
            cv.create_text(l - 6 * Z, q, text=fmt_num(v), anchor="e", font=ft,
                           fill=C_INK, tags=st)
        for y, color, text, below in self.hlines:
            q = self.py(y)
            dashed_line(cv, l, q, r, q, 3 * Z, zdash(DASH), color, st)
            if text:
                # drawn above the traces on a white box: a clipped output
                # sitting on the rail can't hide its own label
                fa = bold(16)
                q += (14 if below else -14) * Z
                cv.create_rectangle(l + 5 * Z, q - 10 * Z, l + 13 * Z + rich_width(fa, text),
                                    q + 11 * Z, fill=BG, outline="", tags=top)
                draw_rich(cv, l + 9 * Z, q, text, fa, color, "w", top)
        cv.create_rectangle(l, t, r, b, outline=C_INK, width=3 * Z, tags=top)
        fl = bold(19)
        draw_rich(cv, l, 14 * Z, self.title, fl, C_INK, "w", st)
        x = r
        for s in reversed(list(self.series.values())):
            if s["visible"] and s["label"]:
                x -= rich_width(fl, s["label"])
                draw_rich(cv, x, 14 * Z, s["label"], fl, s["color"], "w", st)
                x -= 6 * Z
                if s["dash"]:
                    dashed_line(cv, x - 30 * Z, 13 * Z, x, 13 * Z, 5 * Z,
                                zdash(s["dash"]), s["color"], st)
                else:
                    cv.create_line(x - 30 * Z, 13 * Z, x, 13 * Z, fill=s["color"],
                                   width=5 * Z, capstyle="butt", tags=st)
                x -= 46 * Z
        self._restack()
        for s in self.series.values():
            self._plot(s)
        for name in self.dyn:
            self._place(name)


# --------------------------------------------------------------------------
# Flat controls drawn on canvases.  ttk widgets are too small to see or grab
# on a projector, and on Windows they can't take a solid fill or a 4 px black
# border; canvases give square corners and the same look on every OS.
# --------------------------------------------------------------------------
class ButtonBar:
    """A row of flat buttons on one canvas.  gap < 0 makes them share borders
    (a segmented control).  on_click(index)."""

    def __init__(self, parent, labels, on_click, size=17, height=40, border=3,
                 padx=12, gap=8, width=None):
        self.cv = tk.Canvas(parent, bg=BG, highlightthickness=0, cursor="hand2",
                            width=1, height=1)
        self.labels, self.on_click = list(labels), on_click
        self.size, self.height, self.border = size, height, border
        self.padx, self.gap, self.width = padx, gap, width
        self.active = None
        self.cells = []
        self.cv.bind("<Button-1>", self._click)
        self.rescale()

    def set_active(self, i):
        if i != self.active:
            self.active = i
            self.draw()

    def set_label(self, i, text):
        self.labels[i] = text
        self.rescale()

    def rescale(self):
        f = bold(self.size)
        widths = [self.width * Z if self.width else rich_width(f, s) + 2 * self.padx * Z
                  for s in self.labels]
        x, self.cells = 0.0, []
        for w in widths:
            self.cells.append((x, x + w))
            x += w + self.gap * Z
        self.cv.configure(width=int(round(x - self.gap * Z)), height=zs(self.height))
        self.draw()

    def draw(self):
        cv = self.cv
        cv.delete("all")
        f, bw, h = bold(self.size), zs(self.border), zs(self.height)
        for i, ((x0, x1), text) in enumerate(zip(self.cells, self.labels)):
            on = i == self.active
            cv.create_rectangle(x0 + bw / 2, bw / 2, x1 - bw / 2, h - bw / 2, width=bw,
                                outline=C_INK, fill=C_INK if on else BG)
            draw_rich(cv, (x0 + x1) / 2, h / 2, text, f, BG if on else C_INK)

    def _click(self, e):
        for i, (x0, x1) in enumerate(self.cells):
            if x0 <= e.x <= x1:
                self.on_click(i)
                return


class CheckBox:
    def __init__(self, parent, text, var, command):
        self.cv = tk.Canvas(parent, bg=BG, highlightthickness=0, cursor="hand2",
                            width=1, height=1)
        self.text, self.var, self.command = text, var, command
        self.cv.bind("<Button-1>", self._click)
        self.rescale()

    def rescale(self):
        self.cv.configure(width=zs(34) + int(rich_width(bold(17), self.text)) + 2,
                          height=zs(40))
        self.draw()

    def draw(self):
        cv = self.cv
        cv.delete("all")
        h, s, bw = zs(40), 26 * Z, zs(3)
        y0 = (h - s) / 2
        on = self.var.get()
        cv.create_rectangle(bw / 2, y0 + bw / 2, s - bw / 2, y0 + s - bw / 2, width=bw,
                            outline=C_INK, fill=C_INK if on else BG)
        if on:
            cv.create_line(6 * Z, y0 + 13 * Z, 11 * Z, y0 + 19 * Z, 20 * Z, y0 + 7 * Z,
                           fill=BG, width=4 * Z, joinstyle="miter", capstyle="butt")
        draw_rich(cv, 34 * Z, h / 2, self.text, bold(17), C_INK, "w")

    def _click(self, e):
        self.var.set(not self.var.get())
        self.draw()
        self.command()


class _Track:
    """Value logic shared by the sliders: linear or log, optional step,
    click or drag anywhere along the rail."""
    H = 40

    def __init__(self, parent, lo, hi, init, on_change, step=None, log=False):
        self.cv = tk.Canvas(parent, bg=BG, highlightthickness=0, cursor="hand2",
                            width=1, height=1)
        self.lo, self.hi, self.step, self.log = lo, hi, step, log
        self.on_change = on_change
        self.cv.configure(height=zs(self.H))
        self.pos = self._p(lo)
        self._dragging = False
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._motion)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.set(init)

    def _p(self, v):
        return math.log10(v) if self.log else v

    def get(self):
        v = 10 ** self.pos if self.log else self.pos
        if self.step:
            v = round(v / self.step) * self.step
        return min(self.hi, max(self.lo, v))

    def set(self, v):
        self.pos = self._p(min(self.hi, max(self.lo, v)))
        self.draw()

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.set(self.get())

    def frac(self, v=None):
        p0, p1 = self._p(self.lo), self._p(self.hi)
        return (self._p(self.get() if v is None else v) - p0) / (p1 - p0)

    def rail(self):
        raise NotImplementedError

    def rescale(self):
        self.cv.configure(height=zs(self.H))
        self.draw()

    def draw(self):
        raise NotImplementedError

    def _press(self, e):
        x0, x1 = self.rail()
        self._dragging = x0 - 24 * Z <= e.x <= x1 + 24 * Z
        self._motion(e)

    def _release(self, e):
        self._dragging = False

    def _motion(self, e):
        if not self._dragging:
            return
        x0, x1 = self.rail()
        f = min(1.0, max(0.0, (e.x - x0) / max(1.0, x1 - x0)))
        p0, p1 = self._p(self.lo), self._p(self.hi)
        self.pos = p0 + f * (p1 - p0)
        self.pos = self._p(self.get())          # snap the thumb to the step
        self.draw()
        self.on_change()


class Slider(_Track):
    """Footer slider: label left, value right, flat rail underneath."""
    H = 44

    def __init__(self, parent, text, lo, hi, init, fmt, on_change, step=None, log=False):
        self.text, self.fmt = text, fmt
        super().__init__(parent, lo, hi, init, on_change, step, log)

    def rail(self):
        return 11 * Z, self.cv.winfo_width() - 11 * Z

    def draw(self):
        cv = self.cv
        w = cv.winfo_width()
        cv.delete("all")
        if w < 30:
            return
        f = bold(17)
        draw_rich(cv, 0, 11 * Z, self.text, f, C_INK, "w")
        draw_rich(cv, w, 11 * Z, self.fmt(self.get()), f, C_INK, "e")
        x0, x1 = self.rail()
        y = 32 * Z
        cv.create_rectangle(x0, y - 2 * Z, x1, y + 2 * Z, fill=C_INK, outline="")
        x, r, bw = x0 + self.frac() * (x1 - x0), 10 * Z, 3 * Z
        cv.create_oval(x - r + bw / 2, y - r + bw / 2, x + r - bw / 2, y + r - bw / 2,
                       fill=BG, outline=C_INK, width=bw)


class PhaseBar(_Track):
    """The big phase-lag slider: 'Phase lag' + sub-line, a thick rail that
    turns orange past 180 deg, and a large readout.  One canvas, 76 stage px."""
    H = 76

    def __init__(self, parent, lo, hi, init, on_change):
        self.sub, self.alert = "", False
        super().__init__(parent, lo, hi, init, on_change, step=1.0)

    def rail(self):
        # border 4 + pad 16 + label block 176 + gap 16 + thumb room 22 = 234;
        # right side the same with the 128-wide readout
        return 234 * Z, self.cv.winfo_width() - 186 * Z

    def set_sub(self, text):
        self.sub = text
        self.draw()

    def set_alert(self, on):
        if on != self.alert:
            self.alert = on
            self.draw()

    def draw(self):
        cv = self.cv
        w, h = cv.winfo_width(), zs(self.H)
        cv.delete("all")
        if w < 300:
            return
        ink = C_DIFF if self.alert else C_INK
        bw = zs(4)
        cv.create_rectangle(bw / 2, bw / 2, w - bw / 2, h - bw / 2, width=bw, outline=C_INK)
        draw_rich(cv, 20 * Z, 28 * Z, "Phase lag", bold(26), C_INK, "w")
        draw_rich(cv, 20 * Z, 52 * Z, self.sub, bold(17), C_INK, "w")
        x0, x1 = self.rail()
        xm = x0 + self.frac(180.0) * (x1 - x0)
        cv.create_rectangle(x0, 24 * Z, x1, 36 * Z, fill=C_INK, outline="")
        cv.create_rectangle(xm, 24 * Z, x1, 36 * Z, fill=C_DIFF, outline="")
        cv.create_rectangle(xm - 2 * Z, 12 * Z, xm + 2 * Z, 48 * Z, fill=C_DIFF, outline="")
        cv.create_text(xm, 60 * Z, text="180°", font=bold(17), fill=C_DIFF)
        x, r, rw = x0 + self.frac() * (x1 - x0), 22 * Z, 7 * Z
        cv.create_oval(x - r + rw / 2, 30 * Z - r + rw / 2, x + r - rw / 2,
                       30 * Z + r - rw / 2, fill=BG, outline=ink, width=rw)
        cv.create_text(w - 20 * Z, 38 * Z, text="%.0f°" % self.get(), anchor="e",
                       font=bold(56), fill=ink)


def parent_bg(widget):
    try:
        return widget.cget("background")
    except tk.TclError:
        return BG


class RichText(tk.Frame):
    """Read-only label that understands V_{SUB} markup.

    A tk.Text does the drawing (its tags can change font and baseline offset,
    which a Label can't).  It sits in a fixed-size Frame sized to the text's
    real pixel height, because a Text's own height is counted in whole lines
    of the main font and would clip a subscript hanging below the last line.
    wrap_px=None: one line per \\n, sized to fit.  wrap_px=N: word-wrapped,
    N pixels wide.  wrap_px=0: word-wrapped to whatever width it is packed to.
    """

    def __init__(self, parent, font, markup="", fg=C_INK, wrap_px=None):
        bg = parent_bg(parent)
        super().__init__(parent, bg=bg, width=max(1, wrap_px or 1), height=1)
        self.pack_propagate(False)
        self.font, self.wrap_px, self._markup = font, wrap_px, None
        self.text = tk.Text(self, font=font, fg=fg, bg=bg, bd=0, relief="flat",
                            highlightthickness=0, padx=0, pady=0, width=1, height=1,
                            wrap="none" if wrap_px is None else "word",
                            cursor="arrow", takefocus=0, exportselection=False)
        self.text.tag_configure("sub", font=sub_font(font), offset=-sub_drop(font))
        # drop the Text class bindings: no caret, selection or typing
        self.text.bindtags((str(self.text), "all"))
        self.text.pack(fill="both", expand=True)
        self.text.bind("<Configure>", lambda e: self._fit())
        self.set(markup)

    def set(self, markup, fg=None):
        if fg:
            self.text.configure(fg=fg)
        if markup == self._markup:
            return
        self._markup = markup
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for s, sub in rich_parts(markup):
            t.insert("end", s, ("sub",) if sub else ())
        t.configure(state="disabled")
        if self.wrap_px is None:
            w = max([rich_width(self.font, ln) for ln in markup.split("\n")] + [1])
            self.configure(width=int(w) + 2)
        self._fit()

    def _fit(self):
        n = self.text.count("1.0", "end", "update", "ypixels")
        n = n[0] if isinstance(n, tuple) else n
        h = max(n or 0, self.font.metrics("linespace"))
        if h != int(self.cget("height")):
            self.configure(height=h)


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------
# Notes behind the "?" button: (heading, body) pairs.  Instructor-facing; the
# main window keeps text to a minimum so it reads from the back of the room.
NOTES = (
    ("The phase slider means something different in each view",
     "• View 1: the lag of the feedback signal relative to V_{IN}.\n"
     "• View 2: the phase of the loop gain Aβ at crossover (|Aβ| = 1). That is "
     "what decides stability, not the phase at the input frequency."),
    ("The amplifier model uses a delay for the extra phase",
     "A = 200 with one pole at 1 kHz and β = 0.5, so the closed-loop gain is "
     "about 2 and crossover is near 100 kHz. A pure time delay stands in for "
     "the amplifier's higher poles. A delay adds lag without changing |Aβ|, "
     "which is what lets one slider move only the phase curve."),
    ("Feedback size in view 1 is manual",
     "\"Link phase to frequency\" ties only the phase to the Bode plot. The "
     "amplitude of the feedback signal stays wherever the Feedback size "
     "slider puts it."),
    ("Keys",
     "• ← / →  nudge the phase 1°  (Shift: 10°)\n"
     "• Space  pause / run\n"
     "• F11  full screen    Esc  leave full screen"),
)


class App:
    SWEEP_S = 6.0     # real seconds for one screen-width of simulated time

    def __init__(self, root, z0=1.0):
        global Z, FAMILY
        Z = z0
        self.root = root
        # The OS title bar is plain text (no subscripts), so no equation here.
        root.title("Feedback & Phase Shift")
        if "Arial" not in tkfont.families(root):
            FAMILY = tkfont.nametofont("TkDefaultFont").actual("family")
        root.configure(bg=BG)

        self.mode = tk.IntVar(value=1)
        self.link = tk.BooleanVar(value=False)
        self.shape = tk.StringVar(value="sine")
        self.paused = False
        self.phase_by_mode = {1: 0.0, 2: 120.0}
        self.sim = LoopSim()
        self.dirty = True
        self.busy = False
        self.last = time.perf_counter()
        self.carry = 0.0
        self.span2 = None
        self.banner_state = (C_MID, [])
        self.help_win = None
        self._rescale_pending = False

        main = self.main = tk.Frame(root, bg=BG)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        # ---- header: view tabs, equation, "?" -------------------------------
        header = tk.Frame(main, bg=BG)
        header.grid(row=0, column=0, sticky="ew")
        self.tabs = ButtonBar(header, ["1 · Summing junction", "2 · Closed loop"],
                              self.tab_clicked, size=22, height=52, border=4,
                              padx=18, gap=10)
        self.tabs.cv.pack(side="left")
        self.help_btn = ButtonBar(header, ["?"], lambda i: self.toggle_help(),
                                  size=28, height=52, border=4, width=52)
        self.help_btn.cv.pack(side="right")
        self.eq = tk.Canvas(header, bg=BG, highlightthickness=0, width=1, height=1)
        self.eq.pack(side="right")

        # ---- block diagram + status banner -----------------------------------
        self.mid = tk.Frame(main, bg=BG)
        self.mid.grid(row=1, column=0, sticky="ew")
        self.diagram = tk.Canvas(self.mid, bg=BG, highlightthickness=0)
        self.diagram.pack(side="left")
        self.banner = tk.Canvas(self.mid, bg=BG, highlightthickness=0, width=1)
        self.banner.pack(side="left", fill="x", expand=True)
        self.banner.bind("<Configure>", lambda e: self.draw_banner())

        # ---- the phase slider ------------------------------------------------
        self.s_phase = PhaseBar(main, 0.0, 360.0, 0.0, self.phase_changed)
        self.s_phase.cv.grid(row=2, column=0, sticky="ew")

        # ---- plots: time domain left; phasor / Bode right --------------------
        plots = self.plots = tk.Frame(main, bg=BG)
        plots.grid(row=3, column=0, sticky="nsew")
        plots.rowconfigure(0, weight=1)
        plots.columnconfigure(0, weight=582, uniform="col")
        plots.columnconfigure(1, weight=410, uniform="col")
        left = self.left = tk.Frame(plots, bg=BG, width=1, height=1)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1, uniform="row")
        left.rowconfigure(1, weight=1, uniform="row")
        self.pa = Plot(left)
        self.pb = Plot(left)
        self.pa.cv.grid(row=0, column=0, sticky="nsew")
        self.pb.cv.grid(row=1, column=0, sticky="nsew")
        self.pa.add_series("vin", C_VIN, "V_{IN}")
        self.pa.add_series("vfb", C_FB, "V_{FB}")
        self.pa.add_series("vd", C_DIFF, "V_{DIFF}")
        self.pb.add_series("vin", C_VIN, "V_{IN}")
        self.pb.add_series("vd", C_DIFF, "V_{DIFF}")
        self.pb.add_series("vout", C_OUT, "V_{OUT}")

        right = self.right = tk.Frame(plots, bg=BG, width=1, height=1)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        self.phasor = tk.Canvas(right, bg=BG, highlightthickness=0, width=10, height=10)
        self.phasor.bind("<Configure>", lambda e: self.draw_phasor())
        bode = dict(xrange=(100, 1e6), logx=True, xfmt=fmt_freq,
                    xticks=[100, 1e3, 1e4, 1e5, 1e6])
        self.bm = Plot(right, title="|Aβ|  (dB)", yrange=(-30, 50),
                       yticks=[-20, 0, 20, 40], show_x=False, **bode)
        self.bp = Plot(right, title="Phase of Aβ  (°)", yrange=(-360, 0), xunit="Hz",
                       yticks=[-360, -180, 0], **bode)
        self.bm.hlines = [(0, C_MID, "", False)]
        self.bp.hlines = [(-180, C_DIFF, "", False)]
        self.bm.add_series("mag", C_INK, width=3.5)
        self.bp.add_series("ph", C_INK, width=3.5)
        self.bode_f = [10 ** (2 + 4 * i / 240.0) for i in range(241)]
        self.bm.set_data("mag", self.bode_f, [20 * math.log10(loop_mag(f)) for f in self.bode_f])

        # ---- footer: per-view controls ---------------------------------------
        footer = tk.Frame(main, bg=BG)
        footer.grid(row=4, column=0, sticky="ew")
        self.footer_line = tk.Frame(footer, bg=C_INK, height=4)
        self.footer_line.pack(fill="x")
        self.footer_row = tk.Frame(footer, bg=BG)
        self.footer_row.pack(fill="x")
        ch = self.changed

        self.f1 = tk.Frame(self.footer_row, bg=BG)
        self.s_k = Slider(self.f1, "Feedback size", 0.0, 1.5, 0.9,
                          lambda v: "%.2f" % v, ch, step=0.01)
        self.cb_link = CheckBox(self.f1, "Link phase to frequency", self.link,
                                self.link_toggled)
        self.s_f1 = Slider(self.f1, "Signal frequency", 100.0, 3e5, 1e3, fmt_hz,
                           self.freq1_changed, log=True)

        self.f2 = tk.Frame(self.footer_row, bg=BG)
        self.seg_shape = ButtonBar(self.f2, ["Sine", "Square"], self.shape_clicked,
                                   gap=-3)
        self.seg_shape.set_active(0)
        self.s_amp = Slider(self.f2, "V_{IN} amplitude", 0.0, 3.0, 1.0,
                            lambda v: "%.1f V" % v, ch, step=0.1)
        self.s_f2 = Slider(self.f2, "V_{IN} frequency", 1e3, 1e5, 5e3, fmt_hz, ch,
                           log=True)
        self.s_speed = Slider(self.f2, "Speed", 0.25, 4.0, 1.0,
                              lambda v: "%.2g×" % v, ch, log=True)
        self.run_btns = ButtonBar(self.f2, ["Pause", "Restart"], self.run_clicked,
                                  width=86)

        # (widget, stretches?) in footer order; gaps are set in _layout()
        self.footer_items = []
        for frame, items in ((self.f1, (self.s_k, self.cb_link, self.s_f1)),
                             (self.f2, (self.seg_shape, self.s_amp, self.s_f2,
                                        self.s_speed, self.run_btns))):
            for i, w in enumerate(items):
                grow = isinstance(w, Slider)
                w.cv.pack(side="left", fill="x" if grow else None, expand=grow)
                if i:
                    self.footer_items.append(w.cv)
        self.scalables = [self.tabs, self.help_btn, self.s_phase, self.s_k, self.cb_link,
                          self.s_f1, self.seg_shape, self.s_amp, self.s_f2, self.s_speed,
                          self.run_btns]

        # ---- keys -----------------------------------------------------------
        root.bind_all("<Left>", lambda e: self.nudge(-1))
        root.bind_all("<Right>", lambda e: self.nudge(1))
        root.bind_all("<Shift-Left>", lambda e: self.nudge(-10))
        root.bind_all("<Shift-Right>", lambda e: self.nudge(10))
        root.bind_all("<space>", lambda e: self.toggle_pause())
        root.bind("<F11>", lambda e: self.set_fullscreen(None))
        root.bind("<Escape>", lambda e: self.set_fullscreen(False))
        root.bind("<Configure>", self._on_configure)

        self._layout()
        self.draw_eq()
        self.set_mode()
        self.tick()

    # ---- scaling ---------------------------------------------------------------
    def _layout(self):
        """Paddings and fixed sizes that depend on Z."""
        self.main.configure(padx=zs(12), pady=zs(12))
        self.eq.pack_configure(padx=(0, zs(16)))
        self.mid.grid_configure(pady=(zs(8), 0))
        self.diagram.configure(width=zs(292), height=zs(112))
        self.banner.configure(height=zs(112))
        self.banner.pack_configure(padx=(zs(8), 0))
        self.s_phase.cv.grid_configure(pady=(zs(8), 0))
        self.plots.grid_configure(pady=zs(8))
        self.left.grid_configure(padx=(0, zs(8)))
        self.pb.cv.grid_configure(pady=(zs(6), 0))
        self.footer_line.configure(height=zs(4))
        self.footer_row.pack_configure(pady=(zs(6), 0))
        for w in self.footer_items:
            w.pack_configure(padx=(zs(22), 0))
        self.arrange_right()

    def _on_configure(self, e):
        if e.widget is not self.root or self._rescale_pending:
            return
        z = max(0.4, min(e.width / STAGE_W, e.height / STAGE_H))
        if abs(z - Z) > 0.005 * Z:
            # debounce: a window drag sends a stream of these
            self._rescale_pending = True
            self.root.after(80, self._rescale)

    def _rescale(self):
        global Z
        self._rescale_pending = False
        r = self.root
        z = max(0.4, min(r.winfo_width() / STAGE_W, r.winfo_height() / STAGE_H))
        if abs(z - Z) <= 0.005 * Z:
            return
        Z = z
        rescale_fonts()
        for w in self.scalables:
            w.rescale()
        self._layout()
        for p in (self.pa, self.pb, self.bm, self.bp):
            p.redraw()
        self.draw_eq()
        self.draw_diagram()
        self.dirty = True

    def set_fullscreen(self, on):
        r = self.root
        if on is None:
            on = not r.tk.getboolean(r.attributes("-fullscreen"))
        r.attributes("-fullscreen", bool(on))

    # ---- help notes -----------------------------------------------------------
    def toggle_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.close_help()
            return
        win = tk.Toplevel(self.root, bg=BG)
        self.help_win = win
        win.title("Notes")
        win.transient(self.root)
        win.resizable(False, False)
        body = tk.Frame(win, bg=BG, padx=zs(20), pady=zs(16))
        body.pack(fill="both", expand=True)
        wrap = zs(620)
        for i, (head, text) in enumerate(NOTES):
            RichText(body, bold(20), head, wrap_px=wrap).pack(
                anchor="w", pady=(0 if i == 0 else zs(14), zs(4)))
            RichText(body, bold(17), text, fg=C_MID, wrap_px=wrap).pack(anchor="w")
        close = ButtonBar(body, ["Close"], lambda i: self.close_help(), padx=16)
        close.cv.pack(anchor="e", pady=(zs(16), 0))
        win.bind("<Escape>", lambda e: self.close_help())
        win.protocol("WM_DELETE_WINDOW", self.close_help)
        win.update_idletasks()
        r = self.root
        x = r.winfo_rootx() + r.winfo_width() - win.winfo_reqwidth() - zs(16)
        y = r.winfo_rooty() + zs(72)
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        if r.tk.getboolean(r.attributes("-fullscreen")):
            win.attributes("-topmost", True)    # else it can open behind
        win.focus_set()
        self.help_btn.set_active(0)

    def close_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.destroy()
        self.help_win = None
        self.help_btn.set_active(None)

    # ---- control callbacks --------------------------------------------------
    def changed(self):
        self.dirty = True

    def tab_clicked(self, i):
        if self.mode.get() != i + 1:
            self.mode.set(i + 1)
            self.set_mode()

    def shape_clicked(self, i):
        self.shape.set(("sine", "square")[i])
        self.seg_shape.set_active(i)

    def run_clicked(self, i):
        if i == 0:
            self.toggle_pause()
        else:
            self.restart()

    def arrange_right(self):
        """View 1: phasor (+ Bode phase when linked).  View 2: both Bode plots."""
        m = self.mode.get()
        if m == 1:
            items = [(self.phasor, 22)]
            if self.link.get():
                items.append((self.bp.cv, 10))
        else:
            items = [(self.bm.cv, 1), (self.bp.cv, 1)]
        for w in (self.phasor, self.bm.cv, self.bp.cv):
            w.grid_forget()
        for r in range(2):
            self.right.rowconfigure(r, weight=0, uniform="")
        for r, (w, weight) in enumerate(items):
            w.grid(row=r, column=0, sticky="nsew", pady=(zs(6) if r else 0, 0))
            self.right.rowconfigure(r, weight=weight, uniform="row")

    def set_mode(self):
        m = self.mode.get()
        self.tabs.set_active(m - 1)
        self.f1.pack_forget()
        self.f2.pack_forget()
        (self.f1 if m == 1 else self.f2).pack(fill="x")
        pa, pb = self.pa, self.pb
        if m == 1:
            self.s_phase.set_range(0.0, 360.0)
            self.s_phase.set_sub("of feedback signal")
            pa.configure(title="Into the summer")
            pb.configure(title="Out of the summer")
            pb.hlines = []
            pa.style("vin", 3.5)
            pa.style("vfb", 3.0, (11, 7), "V_{FB}")
            pb.style("vin", 2.5)
            pb.style("vd", 4.0)
        else:
            self.s_phase.set_range(95.0, 270.0)
            self.s_phase.set_sub("of Aβ where |Aβ| = 1")
            lim = VCC * 1.2
            pa.configure(title="At the summer", yrange=(-lim, lim), yticks=[-VCC, 0, VCC])
            pb.hlines = [(VCC, C_MID, "+V_{CC}", True), (-VCC, C_MID, "−V_{CC}", False)]
            pb.configure(title="Output", yrange=(-lim, lim), yticks=[-VCC, 0, VCC])
            pa.style("vin", 3.0)
            pa.style("vfb", 2.5, DASH, "βV_{OUT}")
            pa.style("vd", 3.0)
            pb.style("vin", 2.5)
            pb.style("vout", 3.5)
            self.span2 = None
            self.restart()
        pa.fast = pb.fast = (m == 2)
        pa.show("vd", m == 2)
        pb.show("vd", m == 1)
        pb.show("vout", m == 2)
        pa.redraw()
        pb.redraw()
        self.arrange_right()
        self.s_phase.set(self.phase_by_mode[m])
        self.draw_diagram()
        self.dirty = True

    def phase_changed(self):
        if self.busy:
            return
        m = self.mode.get()
        ph = self.s_phase.get()
        if m == 1 and self.link.get():
            self.busy = True
            f = freq_for_phase(ph, TAU_VIEW1) or self.s_f1.hi
            self.s_f1.set(f)
            ph = min(360.0, loop_phase(self.s_f1.get(), TAU_VIEW1))
            self.s_phase.set(ph)
            self.busy = False
        self.phase_by_mode[m] = self.s_phase.get()
        self.dirty = True

    def freq1_changed(self):
        if self.busy:
            return
        if self.link.get():
            self.busy = True
            self.s_phase.set(min(360.0, loop_phase(self.s_f1.get(), TAU_VIEW1)))
            self.phase_by_mode[1] = self.s_phase.get()
            self.busy = False
        self.dirty = True

    def link_toggled(self):
        self.arrange_right()
        self.freq1_changed()

    def nudge(self, d):
        self.s_phase.set(self.s_phase.get() + d)
        self.phase_changed()
        return "break"

    def toggle_pause(self):
        self.paused = not self.paused
        self.run_btns.set_label(0, "Run" if self.paused else "Pause")
        return "break"

    def restart(self):
        self.sim.reset()
        self.carry = 0.0

    # ---- drawing ------------------------------------------------------------
    def draw_eq(self):
        cv, f = self.eq, bold(28)
        runs = [("V_{DIFF}", C_DIFF), (" = ", C_INK), ("V_{IN}", C_VIN),
                (" − βV_{OUT}", C_INK)]
        w = sum(rich_width(f, m) for m, _ in runs)
        cv.configure(width=int(w) + 2, height=zs(52))
        cv.delete("all")
        draw_runs(cv, 1, zs(52) / 2, runs, f)

    def draw_banner(self):
        """Solid good/bad/neutral block with white text: readable from the
        back of the room, and the colour is backed up by the words."""
        cv = self.banner
        cv.delete("all")
        w, h = cv.winfo_width(), zs(112)
        color, lines = self.banner_state
        cv.create_rectangle(0, 0, w, h, fill=color, outline="")
        gap = 3 * Z
        heights = [px * lh * Z for _, px, lh in lines]
        y = (h - sum(heights) - gap * (len(lines) - 1)) / 2
        for (text, px, _), lh in zip(lines, heights):
            draw_rich(cv, 18 * Z, y + lh / 2, text, bold(px), BG, "w")
            y += lh + gap

    def draw_diagram(self):
        """The block diagram, in the original 400 x 154 coordinates scaled by
        0.73 to fit its 292 x 112 slot."""
        cv, m = self.diagram, self.mode.get()
        cv.delete("all")
        u = 0.73 * Z
        loop = C_INK if m == 2 else C_OFF
        lw = 3.6 * u
        f_lab, f_txt, f_big, f_small = bold(17.5), bold(15.8), bold(19.3), bold(14.9)

        def line(pts, color=C_INK, arrow=False):
            p = [v * u for v in pts]
            ex, ey = p[-2], p[-1]
            if arrow:
                dx, dy = ex - p[-4], ey - p[-3]
                ln = math.hypot(dx, dy)
                ux, uy = dx / ln, dy / ln
                p[-2], p[-1] = ex - ux * 8 * u, ey - uy * 8 * u
            cv.create_line(*p, fill=color, width=lw, joinstyle="miter", capstyle="butt")
            if arrow:
                a, b = 13 * u, 6 * u
                cv.create_polygon(ex, ey, ex - ux * a - uy * b, ey - uy * a + ux * b,
                                  ex - ux * a + uy * b, ey - uy * a - ux * b,
                                  fill=color, outline="")

        def circ(x, y, r, stroke=None, fill=""):
            cv.create_oval((x - r) * u, (y - r) * u, (x + r) * u, (y + r) * u,
                           outline=stroke or "", fill=fill, width=lw if stroke else 0)

        def text(x, y, s, color=C_INK, font=f_txt):
            draw_rich(cv, x * u, y * u, s, font, color)

        y, fy = 50, 112
        text(22, y, "V_{IN}", C_VIN, f_lab)
        circ(46, y, 4, C_INK)
        line([50, y, 101, y], arrow=True)
        circ(116, y, 15, C_INK, BG)
        text(116, y + 1, "Σ")
        text(90, y - 13, "+")
        text(101, y + 27, "−", font=f_big)
        line([131, y, 205, y], arrow=True)
        text(168, y - 18, "V_{DIFF}", C_DIFF, f_lab)
        cv.create_polygon(205 * u, (y - 22) * u, 205 * u, (y + 22) * u, 250 * u, y * u,
                          outline=loop, fill=BG, width=lw, joinstyle="miter")
        text(220, y + 1, "A", loop)
        line([250, y, 330, y], loop, arrow=True)
        circ(334, y, 4, loop)
        text(367, y, "V_{OUT}", C_OUT if m == 2 else C_OFF, f_lab)
        if m == 2:
            circ(290, y, 5, None, C_INK)
            line([290, y, 290, fy, 240, fy], arrow=True)
            cv.create_rectangle(206 * u, (fy - 15) * u, 240 * u, (fy + 15) * u,
                                outline=C_INK, width=lw, fill=BG)
            text(223, fy + 1, "β")
            line([206, fy, 116, fy, 116, y + 15], arrow=True)
            text(165, fy + 18, "βV_{OUT}", C_FB, f_lab)
        else:
            line([290, y, 290, fy, 240, fy], C_OFF)
            cv.create_rectangle(206 * u, (fy - 15) * u, 240 * u, (fy + 15) * u,
                                outline=C_OFF, width=lw)
            text(223, fy + 1, "β", C_OFF)
            circ(182, fy, 12, C_FB, BG)
            text(182, fy, "~", C_FB, f_big)
            line([170, fy, 116, fy, 116, y + 15], C_FB, arrow=True)
            text(143, fy + 18, "V_{FB}", C_FB, f_lab)
            text(292, fy + 30, "loop not connected", C_OFF, f_small)

    def draw_phasor(self):
        cv = self.phasor
        cv.delete("all")
        if self.mode.get() != 1:
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        k = self.s_k.get()
        phi = math.radians(self.s_phase.get())
        top, bot = 30 * Z, 26 * Z
        sc = min(w / 3.9, (h - top - bot) / 3.15)
        ox, oy = w / 2 - 0.7 * sc, top + (h - top - bot) / 2

        def P(x, y):
            return ox + x * sc, oy - y * sc

        def arrow(a, b, color, width, dash=None):
            (xa, ya), (xb, yb) = P(*a), P(*b)
            ln = math.hypot(xb - xa, yb - ya)
            if ln < 1:
                return
            ux, uy, hl, hw = (xb - xa) / ln, (yb - ya) / ln, min(18 * Z, ln), 8 * Z
            # shaft stops short of the tip and the head is a separate polygon:
            # Tk's own arrowheads go odd on wide or dashed lines
            xe, ye = xb - ux * hl * 0.8, yb - uy * hl * 0.8
            if dash:
                dashed_line(cv, xa, ya, xe, ye, width * Z, zdash(dash), color)
            else:
                cv.create_line(xa, ya, xe, ye, fill=color, width=width * Z,
                               capstyle="butt")
            cv.create_polygon(xb, yb, xb - ux * hl - uy * hw, yb - uy * hl + ux * hw,
                              xb - ux * hl + uy * hw, yb - uy * hl - ux * hw,
                              fill=color, outline="")

        draw_rich(cv, 4 * Z, 14 * Z, "V_{DIFF} = V_{IN} − V_{FB}", bold(19), C_INK, "w")
        cv.create_oval(ox - sc, oy - sc, ox + sc, oy + sc, fill=C_CIRCLE, outline="")
        if sc > 5:      # dashed outline as solid arcs (see dashed_line())
            on, step = math.degrees(10 * Z / sc), math.degrees(17 * Z / sc)
            a = 0.0
            while a < 360 - step / 2:
                cv.create_arc(ox - sc, oy - sc, ox + sc, oy + sc, start=a, extent=on,
                              style="arc", outline=C_OUT, width=3.5 * Z)
                a += step
        cv.create_line(*P(-1.25, 0), *P(2.6, 0), fill=C_PAXIS, width=2 * Z)
        cv.create_line(*P(0, -1.6), *P(0, 1.6), fill=C_PAXIS, width=2 * Z)
        dx, dy = 1 - k * math.cos(phi), k * math.sin(phi)
        mag = math.hypot(dx, dy)
        arrow((0, 0), (1, 0), C_VIN, 6)
        if k > 0.02:
            arrow((1, 0), (dx, dy), C_FB, 5, (10, 6))
        if mag > 0.03:
            arrow((0, 0), (dx, dy), C_DIFF, 7)
        # labels: V_IN on the side of the axis away from V_DIFF, V_DIFF just
        # past its own tip, -V_FB beside its midpoint away from the origin
        f = bold(20)
        below = dy >= 0
        draw_rich(cv, P(0.5, 0)[0], oy + (18 if below else -18) * Z, "V_{IN}", f, C_VIN)
        # a short V_DIFF (near 0 deg) would put its label on top of V_IN and
        # -V_FB, so it moves up and left instead
        tiny = mag < 0.35
        if tiny:
            ux, uy = 0.0, (1.0 if below else -1.0)
        else:
            ux, uy = dx / mag, dy / mag
        tx, ty = P(dx, dy)
        draw_rich(cv, tx + (ux * 34 - (26 if tiny else 0)) * Z,
                  ty - uy * (26 if tiny else 20) * Z, "V_{DIFF}", f, C_DIFF)
        if k > 0.02:
            nx, ny = math.sin(phi), math.cos(phi)      # normal to -V_FB
            mx, my = (1 + dx) / 2, dy / 2
            if nx * mx + ny * my < 0:
                nx, ny = -nx, -ny
            qx, qy = P(mx, my)
            draw_rich(cv, qx + nx * 34 * Z, qy - ny * 20 * Z, "−V_{FB}", f, C_FB)
        draw_rich(cv, w / 2, h - 12 * Z, "inside the circle:  |V_{DIFF}| < |V_{IN}|",
                  bold(17), C_GOOD)

    def refresh(self):
        """Everything that only changes when a control moves."""
        m = self.mode.get()
        ph = self.s_phase.get()
        if m == 1:
            k = self.s_k.get()
            f = self.s_f1.get()
            phi = math.radians(ph)
            ratio = math.hypot(1 - k * math.cos(phi), k * math.sin(phi))
            n = 300
            th = [2 * math.pi * 2.5 * i / n for i in range(n + 1)]
            span = 2.5 / f
            unit, mul = ("ms", 1e3) if span >= 2e-3 else ("µs", 1e6)
            xs = [t / (2 * math.pi * f) * mul for t in th]
            vin = [math.sin(t) for t in th]
            vfb = [k * math.sin(t - phi) for t in th]
            vd = [a - b for a, b in zip(vin, vfb)]
            lim = math.ceil((1 + k) * 1.05 * 2) / 2.0
            for p in (self.pa, self.pb):
                p.configure(xrange=(0, span * mul), yrange=(-lim, lim),
                            yticks=[-lim, 0, lim], xunit=unit)
            self.pa.set_data("vin", xs, vin)
            self.pa.set_data("vfb", xs, vfb)
            self.pb.set_data("vin", xs, vin)
            self.pb.set_data("vd", xs, vd)
            self.draw_phasor()
            if ratio < 0.995:
                color, msg = C_GOOD, "Negative feedback — the difference shrinks"
            elif ratio > 1.005:
                color, msg = C_BAD, "Positive feedback — the difference grows"
            else:
                color, msg = C_MID, "Rotated, but not shrunk"
            self.banner_state = (color, [("|V_{DIFF}| = %.2f × |V_{IN}|" % ratio, 36, 1.25),
                                         (msg, 22, 1.1)])
            self.s_phase.set_alert(ph >= 180)
            tau, fsig = TAU_VIEW1, (f if self.link.get() else None)
        else:
            tau = tau_for_crossover_phase(ph)
            pm = 180.0 - ph
            f180 = freq_for_phase(180.0, tau)
            gm = -20 * math.log10(loop_mag(f180)) if f180 else None
            if pm > 0.5:
                color = C_GOOD
                msg = ("Stable — ringing dies out" if pm >= 45
                       else "Stable, but barely — heavy ringing")
            elif pm < -0.5:
                color = C_BAD
                msg = "Unstable — grows until it hits the ±%g V rails" % VCC
            else:
                color, msg = C_MID, "On the edge — sustained oscillation"
            sign = "+" if pm > 0 else "−" if pm < 0 else ""
            lines = [("Phase margin %s%.0f°" % (sign, abs(pm)), 36, 1.15), (msg, 22, 1.1)]
            if gm is not None:
                lines.append(("Gain margin %s%.1f dB" % ("+" if gm >= 0 else "−", abs(gm)),
                              18, 1.1))
            self.banner_state = (color, lines)
            self.s_phase.set_alert(ph > 180)
            fsig = self.s_f2.get()
        self.draw_banner()
        # Bode plots
        self.bp.set_data("ph", self.bode_f, [-loop_phase(f, tau) for f in self.bode_f])
        f180 = freq_for_phase(180.0, tau)
        for p in (self.bm, self.bp):
            p.put("fc", "vline", x=FC, color=C_MID, dash=DASH)
            p.put("f180", "vline", x=f180, color=C_DIFF, dash=DASH)
            p.put("fsig", "vline", x=fsig, color=C_VIN)
        self.bm.put("fc_t", "text", x=FC, text="|Aβ| = 1", color=C_MID, anchor="e",
                    dx=-8, dy=16)
        self.bm.put("fc_d", "dot", x=FC, y=0, color=C_MID)
        self.bp.put("fc_d", "dot", x=FC, y=-loop_phase(FC, tau), color=C_MID)
        self.bm.put("f180_d", "dot", x=f180,
                    y=20 * math.log10(loop_mag(f180)) if f180 else 0, color=C_DIFF)
        self.bp.put("f180_d", "dot", x=f180, y=-180, color=C_DIFF)
        if fsig:
            self.bm.put("fsig_d", "dot", x=fsig, y=20 * math.log10(loop_mag(fsig)), color=C_VIN)
            self.bp.put("fsig_d", "dot", x=fsig, y=-loop_phase(fsig, tau), color=C_VIN)
        else:
            self.bm.put("fsig_d", "dot", x=None, y=0, color=C_VIN)
            self.bp.put("fsig_d", "dot", x=None, y=0, color=C_VIN)

    def tick(self):
        now = time.perf_counter()
        elapsed = min(now - self.last, 0.1)
        self.last = now
        if self.dirty:
            self.dirty = False
            self.refresh()
        if self.mode.get() == 2:
            sim = self.sim
            f = self.s_f2.get()
            span = min(1e-3, max(1e-4, 2.5 / f))
            if span != self.span2:
                self.span2 = span
                self.pa.configure(xrange=(-span * 1e3, 0), xunit="ms")
                self.pb.configure(xrange=(-span * 1e3, 0), xunit="ms")
            if not self.paused:
                steps = elapsed * span * self.s_speed.get() / self.SWEEP_S / sim.DT + self.carry
                n = int(steps)
                self.carry = steps - n
                rec = max(1, int(round(span / sim.DT / 1600)))
                sim.run(n, self.s_amp.get(), f, self.shape.get() == "square",
                        tau_for_crossover_phase(self.s_phase.get()), rec)
                sim.trim(span)
            i0 = bisect.bisect_left(sim.T, sim.t - span)
            t1 = sim.t
            xs = [(t - t1) * 1e3 for t in sim.T[i0:]]
            vout = sim.VOUT[i0:]
            self.pa.set_data("vin", xs, sim.VIN[i0:])
            self.pa.set_data("vfb", xs, [BETA * v for v in vout])
            self.pa.set_data("vd", xs, sim.VD[i0:])
            self.pb.set_data("vin", xs, sim.VIN[i0:])
            self.pb.set_data("vout", xs, vout)
        self.root.after(25, self.tick)


def main():
    try:   # crisp text on high-DPI Windows displays
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    dpi = max(1.0, root.winfo_fpixels("1i") / 96.0)
    # 4:3, the design stage scaled by the DPI factor, shrunk to fit the screen
    z = min(dpi, (sw - 40) / STAGE_W, (sh - 90) / STAGE_H)
    w, h = int(STAGE_W * z), int(STAGE_H * z)
    root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 2 - 20)))
    root.minsize(min(800, w), min(600, h))
    App(root, z)
    root.mainloop()


if __name__ == "__main__":
    main()
