"""Parity: feedback_phase_sim.html must give the same numbers and words as
feedback_phase_sim.py (see "Parity" in CLAUDE.md).

The page's script is run by tests/js_harness.mjs under node or deno.  With
neither installed these tests are SKIPPED, not passed - install one before
relying on them.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import feedback_phase_sim as m  # noqa: E402

HTML = os.path.join(ROOT, "feedback_phase_sim.html")
HARNESS = os.path.join(ROOT, "tests", "js_harness.mjs")


def js_runtime():
    if shutil.which("node"):
        return [shutil.which("node")]
    if shutil.which("deno"):
        return [shutil.which("deno"), "run", "--allow-read"]
    return None


def js(calls):
    """Run a batch of harness requests, return the list of answers."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "calls.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(calls, f)
        r = subprocess.run(js_runtime() + [HARNESS, HTML, path], capture_output=True,
                           encoding="utf-8", timeout=120)
    if r.returncode:
        raise AssertionError("JS harness failed:\n" + r.stderr)
    return json.loads(r.stdout)


def fn(name, *args):
    return {"fn": name, "args": list(args)}


@unittest.skipUnless(js_runtime(), "needs node or deno on PATH")
class Parity(unittest.TestCase):
    def close(self, a, b, msg=None):
        if a is None or b is None:
            self.assertEqual(a, b, msg)
        else:
            self.assertAlmostEqual(a, b, delta=1e-9 * max(1.0, abs(b)), msg=msg)

    def test_constants(self):
        names = ["A0", "BETA", "FP", "VCC", "L0", "FC", "POLE_PHASE_FC", "TAU_VIEW1",
                 "F1_MIN", "F1_MAX", "BODE_PER_DECADE", "SWEEP_S"]
        got = js([fn(n) for n in names] + [fn("BODE_X1"), fn("BODE_X2"), fn("DASH"),
                                           fn("C"), fn("S"), {"sim": dict(
                                               n=1, amp=0, freq=1, square=False, tau=0, rec=1)}])
        want = [getattr(m, n) for n in names[:-1]] + [m.App.SWEEP_S]
        for n, g, w in zip(names, got, want):
            self.close(g, w, n)
        self.assertEqual(got[12], list(m.BODE_X1))
        self.assertEqual(got[13], list(m.BODE_X2))
        self.assertEqual(got[14], list(m.DASH))
        self.assertEqual(got[15], {k[2:]: v for k, v in vars(m).items()
                                   if k.startswith("C_") and k[2:] in got[15]})
        self.assertEqual(len(got[15]), 13)
        self.assertEqual(got[16]["ph"], {"1": 0, "2": 120})     # start-up phases
        self.assertEqual((got[17]["DT"], got[17]["MASK"]), (m.LoopSim.DT, m.LoopSim.MASK))
        with open(HTML, encoding="utf-8") as f:
            self.assertIn("LoopSim.NOISE = %r;" % m.LoopSim.NOISE, f.read().replace("2e-3", "0.002"))

    def test_loop_functions(self):
        freqs = [1, 8, 100, 1e3, 5e3, 99995, 3e5, 1e6]
        phases = [0, 1, 45, 95, 120, 150, 179, 180, 181, 200, 270, 360]
        calls, want = [], []
        for f in freqs:
            calls += [fn("loopMag", f), fn("linkedPhase", f)]
            want += [m.loop_mag(f), m.linked_phase(f)]
            for ph in phases:
                tau = m.tau_for_crossover_phase(ph)
                calls.append(fn("loopPhase", f, tau))
                want.append(m.loop_phase(f, tau))
        for ph in phases:
            tau = m.tau_for_crossover_phase(ph)
            calls += [fn("tauFor", ph), fn("freqForPhase", 180, tau), fn("freqForPhase", ph, m.TAU_VIEW1)]
            want += [tau, m.freq_for_phase(180, tau), m.freq_for_phase(ph, m.TAU_VIEW1)]
        for k in (0, 0.5, 0.9, 1.5):
            for ph in phases:
                calls.append(fn("view1Ratio", k, ph))
                want.append(m.view1_ratio(k, ph))
        for c, g, w in zip(calls, js(calls), want):
            self.close(g, w, c)

    def test_bode_curves_and_ticks(self):
        got = js([fn("bodeFreqs", list(m.BODE_X1)), fn("bodeFreqs", list(m.BODE_X2)),
                  fn("niceTicks", 0, 2.5, 4), fn("niceTicks", -3, 3, 5), fn("niceTicks", 0, 8.33, 4)])
        want = [m.bode_freqs(m.BODE_X1), m.bode_freqs(m.BODE_X2),
                m.nice_ticks(0, 2.5, 4), m.nice_ticks(-3, 3, 5), m.nice_ticks(0, 8.33, 4)]
        for g, w in zip(got, want):
            self.assertEqual(len(g), len(w))
            for a, b in zip(g, w):
                self.close(a, b)

    def test_formatting(self):
        nums = [0, 0.5, 1, 2.5, -2.5, 5, -5, 25, 250, 1000, 2000, 2500, 0.125, 8.333333]
        freqs = [1, 1.2345, 8, 99.96, 100, 999.5, 1e3, 1234, 5e3, 99995, 148600, 3e5, 1e6]
        spans = [2.5 / f for f in (1, 1.25, 1.3, 100, 1250, 1300, 3e5)]
        calls = ([fn("fmtNum", v) for v in nums] + [fn("fmtFreq", v) for v in freqs]
                 + [fn("fmtHz", v) for v in freqs] + [fn("timeUnit", s) for s in spans])
        want = ([m.fmt_num(v) for v in nums] + [m.fmt_freq(v) for v in freqs]
                + [m.fmt_hz(v) for v in freqs] + [list(m.time_unit(s)) for s in spans])
        for c, g, w in zip(calls, js(calls), want):
            self.assertEqual(g, w, c)

    def test_banner_words_and_colours(self):
        calls, want = [], []
        for k in (0, 0.5, 0.9, 1.0, 1.5):
            for ph in range(0, 361, 5):
                calls.append(fn("view1Status", k, ph))
                want.append(m.view1_status(k, ph))
        for ph in range(95, 271):
            calls.append(fn("view2Status", ph))
            want.append(m.view2_status(ph))
        for c, g, (color, lines) in zip(calls, js(calls), want):
            self.assertEqual(g["bg"], color, c)
            self.assertEqual(g["lines"], [text for text, _, _ in lines], c)

    def test_view2_frequency_range_and_time_axis(self):
        freqs = [1e3, 2.5e3, 5e3, 2.5e4, 1e5, 100001, 2e5, 1e6, 2e6]
        got = js([fn("F2_MIN"), fn("F2_MAX")] + [fn("view2Time", f) for f in freqs])
        self.assertEqual(got[:2], [m.F2_MIN, m.F2_MAX])
        for f, g in zip(freqs, got[2:]):
            w = m.view2_time(f)
            self.close(g[0], w[0], f)
            self.assertEqual(g[1:], list(w[1:]), f)

    def test_phase_slider_label(self):
        got = js([fn("phaseLabel", 1), fn("phaseLabel", 2)])
        self.assertEqual(got, [list(m.phase_label(1)), list(m.phase_label(2))])
        self.assertEqual(m.phase_label(2)[0], "Feedback Phase Lag")

    def test_notes(self):
        notes = js([fn("NOTES")])[0]
        self.assertEqual(len(notes), len(m.NOTES))
        for (h, b), (wh, wb) in list(zip(notes, m.NOTES))[:-1]:
            self.assertEqual((h, b), (wh, wb))
        # "Keys" differs on purpose: Esc / full screen belong to the browser there
        self.assertEqual(notes[-1][0], m.NOTES[-1][0])

    def test_sim_traces_match(self):
        # noise off on both sides; a square wave so no sin() is involved and
        # the two should agree to the last bit
        for ph, amp in ((120, 1.0), (170, 1.0), (200, 0.5)):
            p = dict(n=100000, amp=amp, freq=5e3, square=True, tau=m.tau_for_crossover_phase(ph), rec=7)
            got = js([{"sim": p}])[0]
            noise = m.LoopSim.NOISE
            try:
                m.LoopSim.NOISE = 0.0
                sim = m.LoopSim()
                sim.run(p["n"], p["amp"], p["freq"], p["square"], p["tau"], p["rec"])
            finally:
                m.LoopSim.NOISE = noise
            for name in ("T", "VIN", "VOUT", "VD"):
                a, b = got[name], getattr(sim, name)
                self.assertEqual(len(a), len(b))
                self.assertLess(max(abs(x - y) for x, y in zip(a, b)), 1e-9, (ph, name))

    def test_linked_phase_can_reach_zero_in_the_page(self):
        got = js([{"link": 0}, {"dom": "phaseVal"}, {"link": 180}, {"link": 360}])
        self.assertEqual(got[0]["ph"], 0)
        self.assertAlmostEqual(got[0]["f1"], m.F1_MIN, places=6)
        self.assertEqual(got[1]["text"], "0°")
        self.assertEqual(got[2]["ph"], 180)
        self.assertEqual(got[3], {"f1": m.F1_MAX, "ph": round(m.linked_phase(m.F1_MAX))})

    def test_slider_markup_matches_python_ranges(self):
        with open(HTML, encoding="utf-8") as f:
            html = f.read()

        def attrs(id_):
            tag = re.search(r'<input id="%s"[^>]*>' % id_, html).group(0)
            return {k: float(v) for k, v in re.findall(r'(min|max|step|value)="([^"]+)"', tag)}

        self.assertEqual(attrs("k"), dict(min=0, max=1.5, step=0.01, value=0.9))
        self.assertEqual(attrs("amp"), dict(min=0, max=3, step=0.1, value=1))
        f1, f2, sp = attrs("f1in"), attrs("f2in"), attrs("speed")
        self.assertAlmostEqual(10 ** f1["min"], m.F1_MIN)
        self.assertGreaterEqual(10 ** f1["max"], m.F1_MAX)      # the script clamps to F1_MAX
        self.assertLess(10 ** (f1["max"] - f1["step"]), m.F1_MAX)
        self.assertAlmostEqual(10 ** f1["value"], 1e3)
        self.assertAlmostEqual(10 ** f2["min"], m.F2_MIN)
        self.assertGreaterEqual(10 ** f2["max"], m.F2_MAX)      # the script clamps to F2_MAX
        self.assertLess(10 ** (f2["max"] - f2["step"]), m.F2_MAX)
        self.assertAlmostEqual(10 ** f2["value"], 5e3, delta=1)
        self.assertAlmostEqual(10 ** sp["min"], 0.25, delta=1e-3)
        self.assertAlmostEqual(10 ** sp["max"], 4.0, delta=1e-2)
        self.assertEqual(sp["value"], 0)


if __name__ == "__main__":
    unittest.main()
