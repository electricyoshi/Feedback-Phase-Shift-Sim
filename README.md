# Feedback Phase Shift Sim

Classroom demo for EE3722 Module 4.2, "The stability problem": what happens to
V<sub>DIFF</sub> = V<sub>IN</sub> − βV<sub>OUT</sub> as the fed-back signal's phase lag approaches and passes 180°.

## Run

On Windows, double-click `Feedback Phase Sim.bat`. Or from a terminal:

    python feedback_phase_sim.py

Python 3.8+ and nothing else — it uses only the standard library (tkinter).
On Linux, tkinter may need `sudo apt install python3-tk`.

**No Python?** Open `feedback_phase_sim.html` in any modern browser (double-click
it; works offline from the file). It's the same simulation and layout.

## The two views

**1 · Summing junction only.** The feedback signal is a copy of V<sub>IN</sub> with adjustable
size and phase lag; there is no loop. Shows V<sub>IN</sub>, V<sub>FB</sub> and V<sub>DIFF</sub> as waveforms and as
phasors. With "Link phase to frequency" checked, the phase follows the Bode plot at
the signal frequency (and dragging the phase moves the frequency).

**2 · Full closed loop.** A time-domain simulation of the whole block diagram with
±5 V rails, running in slow motion. The phase slider sets the lag of the loop gain
Aβ at the frequency where |Aβ| = 1, i.e. 180° minus the phase margin. Below 180° a
square-wave input shows growing overshoot and ringing; above 180° the output
oscillates and grows until it clips at the rails. With V<sub>IN</sub> at 0 it starts on its own.

Keys: ← / → nudge the phase 1° (Shift for 10°), Space pauses, F11 toggles full
screen (Esc leaves it). The **?** button opens instructor notes.

## Projector layout

Built for a low-resolution 4:3 classroom projector: white background, bold type,
thick lines and a colour-blind-safe (Okabe-Ito) palette, with V<sub>FB</sub> drawn black *and*
dashed. The whole layout is designed on a 1024 × 768 stage and scales to fill the
window, so maximise it or press F11 on the projector.

## The model

    A(s) = 200 · e^(−sτ) / (1 + s / 2π·1 kHz),   β = 0.5

so the loop gain is 40 dB at DC and crosses 0 dB at 100 kHz. The delay τ stands in
for the excess phase of an amplifier's higher-frequency poles: it adds lag without
changing |Aβ|, which is what lets one slider move the phase curve alone. The
constants are at the top of `feedback_phase_sim.py`.

## License

MIT — see [LICENSE](LICENSE).
