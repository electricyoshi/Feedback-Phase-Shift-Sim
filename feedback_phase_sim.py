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
    python feedback_phase_sim.py
"""

import bisect
import math
import random
import re
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

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
# Minimal plotting on a tk Canvas
# --------------------------------------------------------------------------
C_VIN = "#1f6fd0"
C_FB = "#e07b00"
C_DIFF = "#d62728"
C_OUT = "#1a8f3a"
C_GRID = "#e3e6ea"
C_AXIS = "#555555"
C_OFF = "#b8bcc2"
C_GOOD = "#1a7f37"
C_BAD = "#c62828"
BG = "#ffffff"
S = 1.0             # UI scale (set from screen DPI at startup)


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


# --------------------------------------------------------------------------
# Subscripts.  UI strings use a tiny markup, "V_{DIFF}", for a subscript.
# Unicode has no uppercase subscript letters and Tk labels can't mix font
# sizes, so subscripts are drawn as separate runs in a smaller, lowered font:
# draw_rich() on canvases, RichText for text in the control panels.
# --------------------------------------------------------------------------
SUB_RE = re.compile(r"_\{([^}]*)\}")
_sub_fonts = {}


def rich_parts(markup):
    """'V_{DIFF} = x' -> [('V', False), ('DIFF', True), (' = x', False)]"""
    return [(p, i % 2 == 1) for i, p in enumerate(SUB_RE.split(markup)) if p]


def sub_font(font):
    key = str(font)
    if key not in _sub_fonts:
        a = font.actual()
        size = int(round(a["size"] * 0.72))       # negative size = pixels in Tk
        if abs(size) < 6:
            size = 6 if size >= 0 else -6
        _sub_fonts[key] = tkfont.Font(family=a["family"], size=size,
                                      weight=a["weight"], slant=a["slant"])
    return _sub_fonts[key]


def sub_drop(font):
    """How far a subscript's baseline sits below the main baseline, px."""
    return int(round(font.metrics("ascent") * 0.28))


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


def fmt_freq(f):
    if f >= 1e6:
        return "%gM" % (f / 1e6)
    if f >= 1e3:
        return "%gk" % (f / 1e3)
    return "%g" % f


class Plot:
    def __init__(self, parent, fonts, title="", xrange=(0, 1), yrange=(-1, 1),
                 logx=False, xlabel="", yticks=None, xfmt=fmt_num):
        self.cv = tk.Canvas(parent, bg=BG, highlightthickness=0,
                            width=int(200 * S), height=int(110 * S))
        self.f_small, self.f_bold = fonts
        self.title, self.xlabel = title, xlabel
        self.xr, self.yr = xrange, yrange
        self.logx, self.yticks, self.xfmt = logx, yticks, xfmt
        self.hlines = []          # (y, color, dash, text)
        self.series = {}          # name -> dict
        self.dyn = {}             # name -> (kind, kwargs)
        self.dyn_items = {}
        self.fast = False
        self.cv.bind("<Configure>", lambda e: self.redraw())
        self._geom()

    # geometry / transforms
    def _geom(self):
        w, h = max(self.cv.winfo_width(), 50), max(self.cv.winfo_height(), 50)
        self.l, self.r = 50 * S, w - 14 * S
        self.t, self.b = 26 * S, h - (36 * S if self.xlabel else 22 * S)
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
    def set_ranges(self, xrange=None, yrange=None, xlabel=None, title=None):
        new = (xrange or self.xr, yrange or self.yr,
               self.xlabel if xlabel is None else xlabel,
               self.title if title is None else title)
        if new != (self.xr, self.yr, self.xlabel, self.title):
            self.xr, self.yr, self.xlabel, self.title = new
            self.redraw()

    def add_series(self, name, color, label=None, width=2.0, dash=None):
        item = self.cv.create_line(-9, -9, -9, -9, fill=color, width=width * S,
                                   dash=dash)
        # Tk draws wide polylines very slowly; for animated traces ("fast"
        # mode) the same thickness is built from a few offset 1-px lines.
        thin = [self.cv.create_line(-9, -9, -9, -9, fill=color, width=1)
                for _ in range(max(2, int(round(width * S * 0.7))))]
        self.series[name] = dict(item=item, thin=thin, color=color, label=label,
                                 dash=dash, xs=(), ys=(), visible=True)

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
        if self.fast:
            self.cv.coords(s["item"], -9, -9, -9, -9)
            for i, item in enumerate(s["thin"]):
                self.cv.coords(item, *([v + i for v in pts] if i else pts))
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
        item = self.dyn_items.get(name)
        if item is None:
            if kind == "vline":
                item = cv.create_line(0, 0, 0, 0, fill=kw["color"], width=1.5 * S,
                                      dash=kw.get("dash"))
            elif kind == "dot":
                item = cv.create_oval(0, 0, 0, 0, fill=kw["color"], outline="white",
                                      width=1.5 * S)
            else:
                item = cv.create_text(0, 0, font=self.f_small)
            self.dyn_items[name] = item
        x = kw.get("x")
        if x is None or not (self.xr[0] <= x <= self.xr[1]):
            cv.itemconfigure(item, state="hidden")
            return
        cv.itemconfigure(item, state="normal")
        p = self.px(x)
        if kind == "vline":
            cv.coords(item, p, self.t, p, self.b)
        elif kind == "dot":
            q, rad = self.py(kw["y"]), 5 * S
            cv.coords(item, p - rad, q - rad, p + rad, q + rad)
        else:
            q = self.py(kw["y"]) if "y" in kw else self.t
            cv.coords(item, p + kw.get("dx", 0) * S, q + kw.get("dy", 0) * S)
            cv.itemconfigure(item, text=kw["text"], fill=kw["color"],
                             anchor=kw.get("anchor", "nw"))

    # static decorations
    def redraw(self):
        self._geom()
        cv = self.cv
        cv.delete("static")
        l, r, t, b = self.l, self.r, self.t, self.b
        fs = self.f_small
        if self.logx:
            d0 = math.floor(math.log10(self.xr[0]) + 1e-9)
            d1 = math.ceil(math.log10(self.xr[1]) - 1e-9)
            for d in range(d0, d1 + 1):
                for m in range(2, 10):
                    v = m * 10.0 ** d
                    if self.xr[0] < v < self.xr[1]:
                        cv.create_line(self.px(v), t, self.px(v), b, fill="#f0f1f3",
                                       tags="static")
            xt = [10.0 ** d for d in range(d0, d1 + 1)]
        else:
            xt = nice_ticks(self.xr[0], self.xr[1], 8)
        for v in xt:
            if self.xr[0] <= v <= self.xr[1]:
                p = self.px(v)
                cv.create_line(p, t, p, b, fill=C_GRID, tags="static")
                cv.create_text(p, b + 3 * S, text=self.xfmt(v), anchor="n", font=fs,
                               fill=C_AXIS, tags="static")
        for v in (self.yticks or nice_ticks(self.yr[0], self.yr[1], 5)):
            q = self.py(v)
            cv.create_line(l, q, r, q, fill="#b9bec6" if v == 0 else C_GRID,
                           tags="static")
            cv.create_text(l - 5 * S, q, text=fmt_num(v), anchor="e", font=fs,
                           fill=C_AXIS, tags="static")
        for y, color, dash, text in self.hlines:
            q = self.py(y)
            cv.create_line(l, q, r, q, fill=color, dash=dash, width=1.5 * S,
                           tags="static")
            if text:
                draw_rich(cv, l + 5 * S, q - 2 * S, text, fs, color, "sw", "static")
        cv.create_rectangle(l, t, r, b, outline=C_AXIS, tags="static")
        draw_rich(cv, l, t - 5 * S, self.title, self.f_bold, "#222", "sw", "static")
        if self.xlabel:
            cv.create_text((l + r) / 2, b + 19 * S, text=self.xlabel, anchor="n",
                           font=fs, fill=C_AXIS, tags="static")
        x = r
        for s in reversed(list(self.series.values())):
            if s["visible"] and s["label"]:
                x -= rich_width(self.f_bold, s["label"])
                draw_rich(cv, x, t - 5 * S, s["label"], self.f_bold, s["color"],
                          "sw", "static")
                x -= 5 * S
                cv.create_line(x - 20 * S, t - 13 * S, x, t - 13 * S, fill=s["color"],
                               width=3 * S, dash=s["dash"], tags="static")
                x -= 34 * S
        cv.tag_lower("static")
        for s in self.series.values():
            self._plot(s)
        for name in self.dyn:
            self._place(name)


class Slider:
    def __init__(self, parent, text, lo, hi, init, fmt, on_change, step=None,
                 log=False, bold=None, big=None):
        self.fmt, self.step, self.log, self.on_change = fmt, step, log, on_change
        self.lo, self.hi = lo, hi
        self.frame = ttk.Frame(parent)
        head = ttk.Frame(self.frame)
        head.pack(fill="x")
        self.label = RichText(head, big or tkfont.nametofont("TkDefaultFont"), text)
        self.label.pack(side="left")
        self.value = tk.Label(head, font=big or bold, bg=parent_bg(parent))
        self.value.pack(side="right")
        self.var = tk.DoubleVar()
        self.scale = ttk.Scale(self.frame, from_=self._pos(lo), to=self._pos(hi),
                               variable=self.var, command=self._moved, takefocus=0)
        self.scale.pack(fill="x", pady=(1, 0))
        self.set(init)

    def _pos(self, v):
        return math.log10(v) if self.log else v

    def get(self):
        v = self.var.get()
        v = 10 ** v if self.log else v
        if self.step:
            v = round(v / self.step) * self.step
        return min(self.hi, max(self.lo, v))

    def set(self, v):
        self.var.set(self._pos(min(self.hi, max(self.lo, v))))
        self._show()

    def set_range(self, lo, hi, text=None):
        self.lo, self.hi = lo, hi
        self.scale.configure(from_=self._pos(lo), to=self._pos(hi))
        if text:
            self.label.set(text)

    def _show(self):
        self.value.configure(text=self.fmt(self.get()))

    def _moved(self, _):
        self._show()
        self.on_change()


def parent_bg(widget):
    try:
        return ttk.Style().lookup("TFrame", "background") or widget.winfo_toplevel().cget("bg")
    except tk.TclError:
        return "#f0f0f0"


class RichText(tk.Frame):
    """Read-only label that understands V_{SUB} markup.

    A tk.Text does the drawing (its tags can change font and baseline offset,
    which a Label can't).  It sits in a fixed-size Frame sized to the text's
    real pixel height, because a Text's own height is counted in whole lines
    of the main font and would clip a subscript hanging below the last line.
    wrap_px=None: one line per \\n, sized to fit.  wrap_px=N: word-wrapped,
    N pixels wide.  wrap_px=0: word-wrapped to whatever width it is packed to.
    """

    def __init__(self, parent, font, markup="", fg="#000", wrap_px=None):
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
HELP1 = ("The feedback signal here is just a copy of V_{IN} with its own size and "
         "phase lag - no loop yet.\n\n"
         "• 0°: it subtracts, so V_{DIFF} is small.\n"
         "• Toward 180°: it cancels less and less.\n"
         "• At 180°: the subtraction has become an addition.\n\n"
         "In the phasor view, any time the tip of V_{DIFF} is outside the dashed "
         "circle, feedback has made V_{DIFF} bigger than V_{IN}.")
HELP2 = ("Now V_{DIFF} drives amplifier A (gain 200, ±5 V rails) and "
         "β = 0.5 feeds the output back.\n\n"
         "The slider sets the phase lag of Aβ at the frequency where "
         "|Aβ| = 1.\n\n"
         "• Use a square wave to see ringing grow as you approach 180°.\n"
         "• Go past 180° and wait.\n"
         "• Set V_{IN} to 0: it oscillates on its own.")

# Notes behind the "?" button: (heading, body) pairs.
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
)


class App:
    SWEEP_S = 6.0     # real seconds for one screen-width of simulated time

    def __init__(self, root):
        global S
        self.root = root
        # The OS title bar is plain text (no subscripts), so no equation here.
        root.title("Feedback & Phase Shift")
        S = max(1.0, root.winfo_fpixels("1i") / 96.0)
        base = tkfont.nametofont("TkDefaultFont")
        fam = base.actual("family")
        base.configure(size=11)
        self.f_small = tkfont.Font(family=fam, size=10)
        self.f_bold = tkfont.Font(family=fam, size=11, weight="bold")
        self.f_big = tkfont.Font(family=fam, size=14, weight="bold")
        self.f_huge = tkfont.Font(family=fam, size=17, weight="bold")
        fonts = (self.f_small, self.f_bold)
        self.bg = parent_bg(root)
        root.configure(bg=self.bg)

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

        root.columnconfigure(1, weight=3)
        root.columnconfigure(2, weight=2)
        root.rowconfigure(2, weight=1)

        # ---- left: controls -------------------------------------------------
        cp = ttk.Frame(root, padding=(12, 10))
        cp.grid(row=0, column=0, rowspan=3, sticky="ns")
        wrap = int(270 * S)
        ttk.Label(cp, text="View", font=self.f_bold).pack(anchor="w")
        for val, txt in ((1, "1 · Summing junction only"),
                         (2, "2 · Full closed loop")):
            ttk.Radiobutton(cp, text=txt, variable=self.mode, value=val,
                            command=self.set_mode).pack(anchor="w", pady=1)
        ttk.Separator(cp).pack(fill="x", pady=8)

        ch = self.changed
        self.f1 = ttk.Frame(cp)
        self.s_k = Slider(self.f1, "Feedback size  |V_{FB}| / |V_{IN}|", 0.0, 1.5, 0.9,
                          lambda v: "%.2f" % v, ch, step=0.01, bold=self.f_bold)
        self.s_k.frame.pack(fill="x", pady=4)
        ttk.Checkbutton(self.f1, text="Link phase to frequency\n(follow the Bode plot)",
                        variable=self.link, command=self.link_toggled).pack(anchor="w", pady=(8, 2))
        self.s_f1 = Slider(self.f1, "Signal frequency", 100.0, 3e5, 1e3,
                           lambda v: fmt_freq(float("%.3g" % v)) + "Hz", self.freq1_changed,
                           log=True, bold=self.f_bold)
        self.s_f1.frame.pack(fill="x", pady=4)
        RichText(self.f1, self.f_small, HELP1, wrap_px=wrap).pack(anchor="w", pady=(12, 0))

        self.f2 = ttk.Frame(cp)
        row = ttk.Frame(self.f2)
        row.pack(fill="x")
        ttk.Label(row, text="Input:").pack(side="left")
        for val in ("sine", "square"):
            ttk.Radiobutton(row, text=val, variable=self.shape, value=val).pack(side="left", padx=4)
        self.s_amp = Slider(self.f2, "V_{IN} amplitude", 0.0, 3.0, 1.0,
                            lambda v: "%.1f V" % v, ch, step=0.1, bold=self.f_bold)
        self.s_amp.frame.pack(fill="x", pady=4)
        self.s_f2 = Slider(self.f2, "V_{IN} frequency", 1e3, 1e5, 5e3,
                           lambda v: fmt_freq(float("%.3g" % v)) + "Hz", ch,
                           log=True, bold=self.f_bold)
        self.s_f2.frame.pack(fill="x", pady=4)
        self.s_speed = Slider(self.f2, "Playback speed", 0.25, 4.0, 1.0,
                              lambda v: "%.2g×" % v, ch, log=True, bold=self.f_bold)
        self.s_speed.frame.pack(fill="x", pady=4)
        row = ttk.Frame(self.f2)
        row.pack(fill="x", pady=(6, 0))
        self.b_pause = ttk.Button(row, text="Pause", command=self.toggle_pause)
        self.b_pause.pack(side="left", expand=True, fill="x", padx=(0, 3))
        ttk.Button(row, text="Restart", command=self.restart).pack(
            side="left", expand=True, fill="x", padx=(3, 0))
        RichText(self.f2, self.f_small, HELP2, wrap_px=wrap).pack(anchor="w", pady=(12, 0))

        ttk.Label(cp, text="← →  nudge phase 1°  (Shift: 10°)\nSpace  pause / run",
                  font=self.f_small, foreground="#666").pack(side="bottom", anchor="w")

        # ---- top: block diagram + readout ----------------------------------
        top = ttk.Frame(root, padding=(4, 8, int(40 * S), 0))   # room for "?"
        top.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.diagram = tk.Canvas(top, width=int(400 * S), height=int(154 * S),
                                 bg=self.bg, highlightthickness=0)
        self.diagram.pack(side="left")
        info = tk.Frame(top, bg=self.bg)
        info.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.l_line1 = RichText(info, self.f_huge, wrap_px=0)
        self.l_line1.pack(fill="x", pady=(14, 2))
        self.l_line2 = RichText(info, self.f_big, wrap_px=0)
        self.l_line2.pack(fill="x")

        # ---- the phase slider ----------------------------------------------
        pf = ttk.Frame(root, padding=(14, 2, 14, 6))
        pf.grid(row=1, column=1, columnspan=2, sticky="ew")
        self.s_phase = Slider(pf, "", 0.0, 360.0, 0.0, lambda v: "%.0f°" % v,
                              self.phase_changed, step=1.0, big=self.f_big)
        self.s_phase.frame.pack(fill="x")

        # ---- middle: time-domain plots -------------------------------------
        mid = ttk.Frame(root, padding=(4, 0, 0, 6))
        mid.grid(row=2, column=1, sticky="nsew")
        self.pa = Plot(mid, fonts, xlabel="time")
        self.pb = Plot(mid, fonts, xlabel="time")
        self.pa.cv.pack(fill="both", expand=True)
        self.pb.cv.pack(fill="both", expand=True)
        self.pa.add_series("vin", C_VIN, "V_{IN}", 2.5)
        self.pa.add_series("vfb", C_FB, "V_{FB}", 2.5)
        self.pa.add_series("vd", C_DIFF, "V_{DIFF}", 2.0)
        self.pb.add_series("vin", "#8db6ea", "V_{IN}", 1.5)
        self.pb.add_series("vd", C_DIFF, "V_{DIFF}", 3.0)
        self.pb.add_series("vout", C_OUT, "V_{OUT}", 2.5)

        # ---- right: phasor + Bode ------------------------------------------
        right = ttk.Frame(root, padding=(0, 0, 6, 6))
        right.grid(row=2, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=7)
        self.right = right
        right.rowconfigure(1, weight=3)
        right.rowconfigure(2, weight=3)
        self.phasor = tk.Canvas(right, bg=BG, highlightthickness=0,
                                width=int(260 * S), height=int(150 * S))
        self.phasor.grid(row=0, column=0, sticky="nsew")
        self.phasor.bind("<Configure>", lambda e: self.draw_phasor())
        self.bm = Plot(right, fonts, title="Loop gain |Aβ|  (dB)", xrange=(100, 1e6),
                       yrange=(-30, 50), logx=True, xfmt=fmt_freq,
                       yticks=[-20, 0, 20, 40])
        self.bp = Plot(right, fonts, title="Phase of Aβ  (deg)", xrange=(100, 1e6),
                       yrange=(-360, 0), logx=True, xfmt=fmt_freq, xlabel="frequency (Hz)",
                       yticks=[-360, -270, -180, -90, 0])
        self.bm.cv.grid(row=1, column=0, sticky="nsew")
        self.bp.cv.grid(row=2, column=0, sticky="nsew")
        self.bm.hlines = [(0, "#888", (4, 3), "")]
        self.bp.hlines = [(-180, C_BAD, (4, 3), "")]
        self.bm.add_series("mag", "#00a3d9", width=2.5)
        self.bp.add_series("ph", "#00a3d9", width=2.5)
        self.bode_f = [10 ** (2 + 4 * i / 240.0) for i in range(241)]
        self.bm.set_data("mag", self.bode_f, [20 * math.log10(loop_mag(f)) for f in self.bode_f])

        # ---- keys -----------------------------------------------------------
        for seq in ("<Left>", "<Right>", "<Up>", "<Down>"):
            root.unbind_class("TScale", seq)
        root.bind_all("<Left>", lambda e: self.nudge(-1))
        root.bind_all("<Right>", lambda e: self.nudge(1))
        root.bind_all("<Shift-Left>", lambda e: self.nudge(-10))
        root.bind_all("<Shift-Right>", lambda e: self.nudge(10))
        root.bind_all("<space>", lambda e: self.toggle_pause())
        root.unbind_class("TButton", "<space>")
        root.unbind_class("TRadiobutton", "<space>")
        root.unbind_class("TCheckbutton", "<space>")

        # ---- help button (upper right corner) -------------------------------
        self.help_win = None
        d = int(24 * S)
        hb = tk.Canvas(root, width=d, height=d, bg=self.bg, highlightthickness=0,
                       cursor="hand2")
        circ = hb.create_oval(1, 1, d - 1, d - 1, fill="#d4d7dc", outline="#a9aeb5")
        hb.create_text(d / 2, d / 2, text="?", fill="#555",
                       font=tkfont.Font(family=fam, size=11, weight="bold"))
        hb.bind("<Enter>", lambda e: hb.itemconfigure(circ, fill="#bfc3c9"))
        hb.bind("<Leave>", lambda e: hb.itemconfigure(circ, fill="#d4d7dc"))
        hb.bind("<Button-1>", lambda e: self.toggle_help())
        hb.place(relx=1.0, x=-int(10 * S), y=int(8 * S), anchor="ne")
        tk.Misc.tkraise(hb)     # Canvas.lift() means raise an item, not the widget

        self.set_mode()
        self.tick()

    # ---- help notes -----------------------------------------------------------
    def toggle_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.close_help()
            return
        win = tk.Toplevel(self.root)
        self.help_win = win
        win.title("Notes")
        win.transient(self.root)
        win.resizable(False, False)
        win.configure(bg=self.bg)
        body = ttk.Frame(win, padding=(16, 12, 16, 14))
        body.pack(fill="both", expand=True)
        wrap = int(420 * S)
        for i, (head, text) in enumerate(NOTES):
            ttk.Label(body, text=head, font=self.f_bold).pack(
                anchor="w", pady=(0 if i == 0 else 12, 3))
            RichText(body, tkfont.nametofont("TkDefaultFont"), text,
                     wrap_px=wrap).pack(anchor="w")
        ttk.Button(body, text="Close", command=self.close_help).pack(
            anchor="e", pady=(14, 0))
        win.bind("<Escape>", lambda e: self.close_help())
        win.protocol("WM_DELETE_WINDOW", self.close_help)
        win.update_idletasks()
        r = self.root
        x = r.winfo_rootx() + r.winfo_width() - win.winfo_reqwidth() - int(16 * S)
        y = r.winfo_rooty() + int(40 * S)
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        win.focus_set()

    def close_help(self):
        if self.help_win is not None and self.help_win.winfo_exists():
            self.help_win.destroy()
        self.help_win = None

    # ---- control callbacks --------------------------------------------------
    def changed(self):
        self.dirty = True

    def set_mode(self):
        m = self.mode.get()
        self.f1.pack_forget()
        self.f2.pack_forget()
        (self.f1 if m == 1 else self.f2).pack(fill="x")
        if m == 1:
            self.s_phase.set_range(0.0, 360.0, "Phase lag of the feedback signal")
            self.phasor.grid()
            self.right.rowconfigure(0, weight=7)
            self.pa.set_ranges(title="Into the summer")
            self.pb.set_ranges(title="Out of the summer")
            self.pb.hlines = []
        else:
            self.s_phase.set_range(95.0, 270.0,
                                   "Phase lag of Aβ where |Aβ| = 1 (crossover)")
            self.phasor.grid_remove()
            self.right.rowconfigure(0, weight=0)
            lim = VCC * 1.2
            self.pa.set_ranges(title="At the summing junction", yrange=(-lim, lim))
            self.pb.hlines = [(VCC, "#777", (6, 4), "+V_{CC}"), (-VCC, "#777", (6, 4), "−V_{CC}")]
            self.pb.set_ranges(title="Output", yrange=(-lim, lim))
            self.span2 = None
            self.restart()
        self.pa.series["vfb"]["label"] = "V_{FB}" if m == 1 else "βV_{OUT}"
        self.pa.fast = self.pb.fast = (m == 2)
        self.pa.show("vd", m == 2)
        self.pb.show("vd", m == 1)
        self.pb.show("vout", m == 2)
        self.pa.redraw()
        self.pb.redraw()
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
        self.freq1_changed()

    def nudge(self, d):
        self.s_phase.set(self.s_phase.get() + d)
        self.phase_changed()
        return "break"

    def toggle_pause(self):
        self.paused = not self.paused
        self.b_pause.configure(text="Run" if self.paused else "Pause")
        return "break"

    def restart(self):
        self.sim.reset()
        self.carry = 0.0

    # ---- drawing ------------------------------------------------------------
    def draw_diagram(self):
        cv, m = self.diagram, self.mode.get()
        cv.delete("all")
        u = S
        loop = "#222" if m == 2 else C_OFF
        w = 2 * u

        def line(*p, color="#222", arrow=None):
            cv.create_line(*[v * u for v in p], fill=color, width=w, arrow=arrow,
                           arrowshape=(9 * u, 11 * u, 4 * u))

        def text(x, y, s, color="#222", font=None, anchor="center"):
            draw_rich(cv, x * u, y * u, s, font or self.f_bold, color, anchor)

        y = 50
        text(22, y, "V_{IN}", C_VIN)
        cv.create_oval(42 * u, (y - 4) * u, 50 * u, (y + 4) * u, outline="#222", width=w)
        line(50, y, 101, y, arrow="last")
        cv.create_oval(101 * u, (y - 15) * u, 131 * u, (y + 15) * u, outline="#222",
                       width=w, fill="white")
        text(116, y, "Σ")
        text(90, y - 13, "+")
        text(101, y + 26, "−", font=self.f_big)
        line(131, y, 205, y, color="#222", arrow="last")
        text(168, y - 16, "V_{DIFF}", C_DIFF)
        cv.create_polygon(205 * u, (y - 22) * u, 205 * u, (y + 22) * u, 250 * u, y * u,
                          outline=loop, fill="white" if m == 2 else self.bg, width=w)
        text(220, y, "A", loop)
        line(250, y, 330, y, color=loop, arrow="last")
        cv.create_oval(330 * u, (y - 4) * u, 338 * u, (y + 4) * u, outline=loop, width=w)
        text(364, y, "V_{OUT}", C_OUT if m == 2 else C_OFF)
        fy = 112
        if m == 2:
            cv.create_oval(286 * u, (y - 4) * u, 294 * u, (y + 4) * u, fill="#222", outline="")
            line(290, y, 290, fy, 240, fy, arrow="last")
            cv.create_rectangle(206 * u, (fy - 15) * u, 240 * u, (fy + 15) * u,
                                outline="#222", width=w, fill="white")
            text(223, fy, "β")
            line(206, fy, 116, fy, 116, y + 15, arrow="last")
            text(160, fy + 14, "βV_{OUT}", C_FB)
        else:
            line(290, y, 290, fy, 240, fy, color=C_OFF)
            cv.create_rectangle(206 * u, (fy - 15) * u, 240 * u, (fy + 15) * u,
                                outline=C_OFF, width=w)
            text(223, fy, "β", C_OFF)
            cv.create_oval(170 * u, (fy - 12) * u, 194 * u, (fy + 12) * u, outline=C_FB,
                           width=w, fill="white")
            text(182, fy, "~", C_FB, self.f_big)
            line(170, fy, 116, fy, 116, y + 15, color=C_FB, arrow="last")
            text(143, fy + 14, "V_{FB}", C_FB)
            text(250, fy + 27, "(loop not connected)", C_OFF, self.f_small)

    def draw_phasor(self):
        cv = self.phasor
        cv.delete("all")
        if self.mode.get() != 1:
            return
        w, h = cv.winfo_width(), cv.winfo_height()
        k = self.s_k.get()
        phi = math.radians(self.s_phase.get())
        top = 28 * S
        sc = min(w / 3.9, (h - top - 22 * S) / 3.15)
        ox, oy = w / 2 - 0.7 * sc, top + (h - top - 22 * S) / 2

        def P(x, y):
            return ox + x * sc, oy - y * sc

        draw_rich(cv, 8 * S, 6 * S, "Phasor view:  V_{DIFF} = V_{IN} − V_{FB}",
                  self.f_bold, "#222", "nw")
        cv.create_oval(*P(-1, 1), *P(1, -1), outline="#3b9a57", dash=(5, 4), width=1.5 * S,
                       fill="#eef8f0")
        draw_rich(cv, *P(-0.71, -0.71), " |V_{IN}| ", self.f_small, "#3b9a57", "ne")
        cv.create_oval(*P(1 - k, k), *P(1 + k, -k), outline="#f0c48a", dash=(2, 4))
        cv.create_line(*P(-1.25, 0), *P(2.6, 0), fill=C_GRID)
        cv.create_line(*P(0, -1.6), *P(0, 1.6), fill=C_GRID)
        dx, dy = 1 - k * math.cos(phi), k * math.sin(phi)
        shape = (11 * S, 13 * S, 5 * S)
        cv.create_line(*P(0, 0), *P(1, 0), fill=C_VIN, width=3 * S, arrow="last", arrowshape=shape)
        if k > 0.02:
            cv.create_line(*P(1, 0), *P(dx, dy), fill=C_FB, width=3 * S, arrow="last",
                           arrowshape=shape)
        if math.hypot(dx, dy) > 0.03:
            cv.create_line(*P(0, 0), *P(dx, dy), fill=C_DIFF, width=4 * S, arrow="last",
                           arrowshape=shape)
        # labels: Vin on the side of the axis away from Vdiff, Vdiff just past
        # its own tip, -Vfb beside its midpoint on the side away from the origin
        below = dy >= 0
        draw_rich(cv, P(0.5, 0)[0], oy + (8 if below else -8) * S, "V_{IN}",
                  self.f_bold, C_VIN, "n" if below else "s")
        mag = math.hypot(dx, dy)
        ux, uy = (dx / mag, dy / mag) if mag > 0.03 else (0.0, 1.0)
        tx, ty = P(dx, dy)
        draw_rich(cv, tx + ux * 26 * S, ty - uy * 16 * S, "V_{DIFF}",
                  self.f_bold, C_DIFF)
        if k > 0.02:
            nx, ny = math.sin(phi), math.cos(phi)      # normal to -Vfb
            mx, my = (1 + dx) / 2, dy / 2
            if nx * mx + ny * my < 0:
                nx, ny = -nx, -ny
            qx, qy = P(mx, my)
            draw_rich(cv, qx + nx * 26 * S, qy - ny * 16 * S, "−V_{FB}",
                      self.f_bold, C_FB)
        draw_rich(cv, w / 2, h - 4 * S,
                  "inside the dashed circle: V_{DIFF} is smaller than V_{IN}",
                  self.f_small, "#3b9a57", "s")

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
                p.set_ranges(xrange=(0, span * mul), yrange=(-lim, lim),
                             xlabel="time (%s)" % unit)
            self.pa.set_data("vin", xs, vin)
            self.pa.set_data("vfb", xs, vfb)
            self.pb.set_data("vin", xs, vin)
            self.pb.set_data("vd", xs, vd)
            self.draw_phasor()
            if ratio < 0.995:
                color, msg = C_GOOD, "feedback is shrinking V_{DIFF}  (acting as negative feedback)"
            elif ratio > 1.005:
                color, msg = C_BAD, "feedback is enlarging V_{DIFF}  (acting as positive feedback)"
            else:
                color, msg = "#555", "feedback is rotating V_{DIFF} but not shrinking it"
            self.l_line1.set("|V_{DIFF}| = %.2f × |V_{IN}|" % ratio, fg=color)
            self.l_line2.set(msg, fg=color)
            self.s_phase.value.configure(fg=C_BAD if ph >= 180 else "#222")
            tau, fsig = TAU_VIEW1, (f if self.link.get() else None)
        else:
            tau = tau_for_crossover_phase(ph)
            pm = 180.0 - ph
            f180 = freq_for_phase(180.0, tau)
            gm = -20 * math.log10(loop_mag(f180)) if f180 else None
            if pm > 0.5:
                color = C_GOOD
                msg = "Stable — disturbances ring and die out"
                if pm < 45:
                    msg = "Stable, but barely — lots of overshoot and ringing"
            elif pm < -0.5:
                color = C_BAD
                msg = "Unstable — oscillation grows until it hits the ±%g V rails" % VCC
            else:
                color, msg = "#a15c00", "Right on the edge — a sustained oscillation"
            line1 = "Phase margin = 180° − %.0f° = %+.0f°" % (ph, pm)
            if gm is not None:
                msg += "\n(gain margin %+.1f dB)" % gm
            self.l_line1.set(line1.replace("-", "−"), fg=color)
            self.l_line2.set(msg.replace("-", "−"), fg=color)
            self.s_phase.value.configure(fg=C_BAD if ph > 180 else "#222")
            fsig = self.s_f2.get()
        # Bode plot
        self.bp.set_data("ph", self.bode_f, [-loop_phase(f, tau) for f in self.bode_f])
        f180 = freq_for_phase(180.0, tau)
        for p in (self.bm, self.bp):
            p.put("fc", "vline", x=FC, color="#888", dash=(4, 3))
            p.put("f180", "vline", x=f180, color=C_BAD, dash=(4, 3))
            p.put("fsig", "vline", x=fsig, color=C_VIN)
        self.bm.put("fc_t", "text", x=FC, text="|Aβ| = 1", color="#666", anchor="ne",
                    dx=-4, dy=3)
        self.bp.put("f180_t", "text", x=f180, text="−180°", color=C_BAD,
                    anchor="sw", y=-360, dx=4, dy=-2)
        self.bm.put("fc_d", "dot", x=FC, y=0, color="#555")
        self.bp.put("fc_d", "dot", x=FC, y=-loop_phase(FC, tau), color="#555")
        if f180:
            self.bm.put("f180_d", "dot", x=f180, y=20 * math.log10(loop_mag(f180)), color=C_BAD)
        self.bp.put("f180_d", "dot", x=f180, y=-180, color=C_BAD)
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
                label = "time (ms)   —   slow motion, newest at right"
                self.pa.set_ranges(xrange=(-span * 1e3, 0), xlabel=label)
                self.pb.set_ranges(xrange=(-span * 1e3, 0), xlabel=label)
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
    s = max(1.0, root.winfo_fpixels("1i") / 96.0)
    w, h = min(int(1340 * s), sw - 40), min(int(800 * s), sh - 90)
    root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 2 - 20)))
    root.minsize(int(900 * s), int(600 * s))
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
