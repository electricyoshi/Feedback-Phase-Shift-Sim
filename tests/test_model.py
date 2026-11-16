"""Physics checks on the Python model: do the numbers the class sees agree
with the textbook formulas?  No GUI, no browser.

    py -m unittest discover -s tests -v
"""
import cmath
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import feedback_phase_sim as m  # noqa: E402


def loop_gain(f, tau):
    """A(jw) * BETA as a complex number, written out independently of the app."""
    w = 2 * math.pi * f
    return m.A0 * m.BETA * cmath.exp(-1j * w * tau) / (1 + 1j * f / m.FP)


class LoopModel(unittest.TestCase):
    def test_headline_numbers(self):
        # the figures quoted in the README / notes
        self.assertAlmostEqual(20 * math.log10(m.A0), 46.0, places=1)
        self.assertAlmostEqual(20 * math.log10(m.L0), 40.0, places=6)
        self.assertAlmostEqual(m.FC, 100e3, delta=10)            # "crosses 0 dB at 100 kHz"
        self.assertAlmostEqual(m.loop_mag(m.FC), 1.0, places=9)
        self.assertAlmostEqual(m.A0 / (1 + m.L0), 1.98, places=2)  # "closed-loop gain about 2"

    def test_mag_and_phase_match_complex_loop_gain(self):
        for ph in (95, 120, 150, 180, 220, 270):
            tau = m.tau_for_crossover_phase(ph)
            for f in (1, 100, 1e3, 2e4, 1e5):   # stay below 360 deg of lag (cmath.phase wraps)
                L = loop_gain(f, tau)
                self.assertAlmostEqual(m.loop_mag(f), abs(L), places=9)
                self.assertAlmostEqual(m.loop_phase(f, tau), -math.degrees(cmath.phase(L)) % 360,
                                       places=6)

    def test_slider_sets_phase_at_crossover(self):
        for ph in range(95, 271, 5):
            self.assertAlmostEqual(m.loop_phase(m.FC, m.tau_for_crossover_phase(ph)), ph, places=9)
        self.assertAlmostEqual(m.loop_phase(m.FC, m.TAU_VIEW1), 150.0, places=9)

    def test_freq_for_phase_is_the_inverse(self):
        tau = m.tau_for_crossover_phase(200)
        for ph in (10, 45, 90, 180, 300):
            self.assertAlmostEqual(m.loop_phase(m.freq_for_phase(ph, tau), tau), ph, places=6)
        self.assertIsNone(m.freq_for_phase(180, 0.0))    # one pole alone never reaches 180

    def test_gain_margin_sign_follows_phase_margin(self):
        for ph, good in ((120, True), (170, True), (190, False), (250, False)):
            f180 = m.freq_for_phase(180, m.tau_for_crossover_phase(ph))
            gm_db = -20 * math.log10(m.loop_mag(f180))
            self.assertEqual(gm_db > 0, good, ph)


class View1(unittest.TestCase):
    def test_ratio_is_the_phasor_difference(self):
        for k in (0.0, 0.5, 0.9, 1.0, 1.5):
            for ph in range(0, 361, 15):
                want = abs(1 - k * cmath.exp(-1j * math.radians(ph)))
                self.assertAlmostEqual(m.view1_ratio(k, ph), want, places=12)

    def test_landmarks(self):
        self.assertAlmostEqual(m.view1_ratio(0.9, 0), 0.1)      # in phase: subtracts
        self.assertAlmostEqual(m.view1_ratio(0.9, 180), 1.9)    # 180 deg: adds
        self.assertAlmostEqual(m.view1_ratio(1.0, 60), 1.0)     # equilateral triangle
        self.assertEqual(m.view1_status(0.9, 0)[0], m.C_GOOD)
        self.assertEqual(m.view1_status(0.9, 180)[0], m.C_BAD)
        self.assertEqual(m.view1_status(1.0, 60)[0], m.C_MID)

    def test_linked_phase_reaches_zero(self):
        # the point of F1_MIN: with the phase linked to frequency, the readout
        # (whole degrees) gets to 0, and asking for 0 lands on F1_MIN
        self.assertEqual(round(m.linked_phase(m.F1_MIN)), 0)
        self.assertAlmostEqual(m.freq_for_phase(0, m.TAU_VIEW1), m.F1_MIN, places=6)
        self.assertLess(m.linked_phase(m.F1_MAX), 360)
        self.assertLessEqual(m.BODE_X1[0], m.F1_MIN)            # marker stays on the plot

    def test_time_axis_never_needs_an_exponent(self):
        for f in (m.F1_MIN, 2, 10, 100, 1e3, 1e5, m.F1_MAX):
            unit, mul = m.time_unit(2.5 / f)
            for v in m.nice_ticks(0, 2.5 / f * mul, 4):
                self.assertNotIn("e", m.fmt_num(v), (f, v))


class View2Status(unittest.TestCase):
    def test_banner_colour_follows_phase_margin(self):
        for ph in range(95, 271):
            color, lines = m.view2_status(ph)
            want = m.C_GOOD if ph < 180 else m.C_BAD if ph > 180 else m.C_MID
            self.assertEqual(color, want, ph)
        self.assertEqual(m.view2_status(120)[1][0][0], "Phase margin +60°")
        self.assertEqual(m.view2_status(200)[1][0][0], "Phase margin −20°")


class Sim(unittest.TestCase):
    """The time-domain loop against the frequency-domain answer."""

    def setUp(self):
        self._noise = m.LoopSim.NOISE

    def tearDown(self):
        m.LoopSim.NOISE = self._noise

    def run_sim(self, ph, amp, freq, seconds, square=False, noise=0.0):
        m.LoopSim.NOISE = noise
        sim = m.LoopSim()
        sim.run(int(seconds / sim.DT), amp, freq, square, m.tau_for_crossover_phase(ph), 4)
        return sim

    def test_closed_loop_gain_matches_theory(self):
        # steady-state |Vout/Vin| = |A / (1 + A*B)|.  Near crossover this is
        # sensitive to loop phase, so it also guards the half-sample correction.
        for ph, f in ((120, 5e3), (120, 5e4), (150, 1e5), (165, 1e5)):
            tau = m.tau_for_crossover_phase(ph)
            L = loop_gain(f, tau)
            want = abs(L / m.BETA / (1 + L))
            sim = self.run_sim(ph, 0.05, f, 1.5e-3)
            n = int(2 / f / (4 * sim.DT))                       # last two cycles
            got = max(abs(v) for v in sim.VOUT[-n:]) / 0.05
            self.assertAlmostEqual(got / want, 1.0, delta=0.01, msg=(ph, f, got, want))

    def test_view2_range_fits_the_sim(self):
        # the longest delay the slider can ask for must fit the delay line
        tau = m.tau_for_crossover_phase(270)
        self.assertLess(tau / m.LoopSim.DT + 2, m.LoopSim.MASK + 1)
        self.assertGreaterEqual(1 / m.F2_MAX / m.LoopSim.DT, 100)      # samples per cycle
        self.assertLessEqual(m.F2_MAX, m.BODE_X2[1])                    # marker stays on the plot
        # time axis: unchanged up to 100 kHz, then 10 cycles in microseconds
        self.assertEqual(m.view2_time(1e3), (1e-3, "ms", 1e3))
        self.assertEqual(m.view2_time(1e5), (1e-4, "ms", 1e3))
        span, unit, _ = m.view2_time(m.F2_MAX)
        self.assertAlmostEqual(span * m.F2_MAX, 10)
        self.assertEqual(unit, "µs")

    def test_gain_above_crossover_matches_theory(self):
        # past crossover the loop gain is < 1, so Vout is just A * Vin
        for f in (5e5, m.F2_MAX):
            tau = m.tau_for_crossover_phase(120)
            L = loop_gain(f, tau)
            want = abs(L / m.BETA / (1 + L))
            sim = self.run_sim(120, 0.5, f, 3e-4)
            got = max(abs(v) for v in sim.VOUT[-int(2 / f / (4 * sim.DT)):]) / 0.5
            self.assertAlmostEqual(got / want, 1.0, delta=0.02, msg=(f, got, want))

    def test_stable_loop_stays_quiet(self):
        sim = self.run_sim(150, 0.0, 5e3, 2e-3, noise=self._noise)
        self.assertLess(max(abs(v) for v in sim.VOUT), 0.2)

    def test_unstable_loop_starts_itself_and_hits_the_rails(self):
        sim = self.run_sim(200, 0.0, 5e3, 2e-3, noise=self._noise)
        tail = sim.VOUT[len(sim.VOUT) // 2:]
        self.assertAlmostEqual(max(tail), m.VCC, places=6)
        self.assertAlmostEqual(min(tail), -m.VCC, places=6)

    def test_overshoot_grows_as_margin_shrinks(self):
        peaks = []
        for ph in (110, 135, 160):
            sim = self.run_sim(ph, 0.5, 5e3, 1e-4, square=True)   # first half-cycle: a +0.5 V step
            peaks.append(max(sim.VOUT))
        self.assertLess(peaks[0], peaks[1])
        self.assertLess(peaks[1], peaks[2])
        self.assertAlmostEqual(peaks[0], 0.5 * m.A0 / (1 + m.L0), delta=0.05)  # ~no overshoot


if __name__ == "__main__":
    unittest.main()
