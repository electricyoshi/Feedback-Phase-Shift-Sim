# Feedback Phase Shift Sim

Tier 1 teaching utility (EE3722 Module 4.2). Single-file tkinter GUI, stdlib only,
Python 3.8+. Intended for a **public** GitHub repo — keep it free of machine-specific
paths and personal details.

## Commands
- `Feedback Phase Sim.bat` — double-click launcher (no console window).
- `py feedback_phase_sim.py` — run with a console (use this to see tracebacks).

## Non-obvious decisions
- Launcher uses `start "" pyw ...`: without `start`, cmd waits on the GUI and leaves an
  empty console open. Falls back pyw → pythonw → py → python; the console fallbacks
  `pause` on error so students can read the message.
- No `.lnk` / `--install` (deviates from the Tier 1 bundle pattern on purpose): shortcuts
  embed absolute paths and don't survive a `git clone` onto another PC. `*.lnk` is
  gitignored.
- Loop model and why a pure delay is used for excess phase: see README.md "The model"
  and the constants at the top of `feedback_phase_sim.py`.

## Status
- Not yet pushed; GitHub remote (public) to be created later. No LICENSE chosen yet.
