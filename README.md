# Feedback Phase Shift Sim

Classroom demo for EE3722 Module 4.2, "The stability problem": what happens to
`Vdiff = Vin − βVout` as the fed-back signal's phase lag approaches and passes 180°.

## Run

    python feedback_phase_sim.py

Python 3.8+ and nothing else — it uses only the standard library (tkinter).
On Linux, tkinter may need `sudo apt install python3-tk`.

## The two views

**1 · Summing junction only.** The feedback signal is a copy of Vin with adjustable
size and phase lag; there is no loop. Shows Vin, Vfb and Vdiff as waveforms and as
phasors. With "Link phase to frequency" checked, the phase follows the Bode plot at
the signal frequency (and dragging the phase moves the frequency).

**2 · Full closed loop.** A time-domain simulation of the whole block diagram with
±5 V rails, running in slow motion. The phase slider sets the lag of the loop gain
Aβ at the frequency where |Aβ| = 1, i.e. 180° minus the phase margin. Below 180° a
square-wave input shows growing overshoot and ringing; above 180° the output
oscillates and grows until it clips at the rails. With Vin at 0 it starts on its own.

Keys: ← / → nudge the phase 1° (Shift for 10°), Space pauses.

## The model

    A(s) = 200 · e^(−sτ) / (1 + s / 2π·1 kHz),   β = 0.5

so the loop gain is 40 dB at DC and crosses 0 dB at 100 kHz. The delay τ stands in
for the excess phase of an amplifier's higher-frequency poles: it adds lag without
changing |Aβ|, which is what lets one slider move the phase curve alone. The
constants are at the top of `feedback_phase_sim.py`.
