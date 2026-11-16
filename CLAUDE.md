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
- **Projector UI (design handoff, Nov 2026):** every size is in "stage px" on a
  1024x768 stage, times global `Z = min(win_w/1024, win_h/768)` (`zs()`, `bold(px)`).
  Root `<Configure>` (debounced) recomputes Z, resizes the named fonts in place
  (`rescale_fonts()`) and redraws. Fonts use negative = pixel sizes so DPI isn't
  applied twice. Palette/widths are final per the handoff; don't drift them.
- **All controls are canvas-drawn** (`ButtonBar`, `CheckBox`, `Slider`, `PhaseBar`):
  ttk can't do solid fills / 4 px borders on Windows and is too small on a projector.
  No ttk widgets remain.
- **Windows Tk dashes:** any dashed line wider than 1 px renders as dots. Wide dashed
  lines go through `dashed_line()` (stack of 1-px dashed lines); dashed traces always
  use the 1-px-stack path in `Plot._plot`; the phasor's dashed circle is solid arcs.
- **Subscripts:** UI strings use `V_{DIFF}` markup (uppercase subscripts, e.g. V_{IN},
  V_{OUT}, V_{FB}, V_{CC}). Unicode has no uppercase subscripts and Tk can't mix fonts
  in one text item, so `draw_rich()` / `draw_runs()` draw runs on canvases; `RichText`
  (read-only tk.Text) is only used for wrapped text in the "?" notes window. Plain-text
  spots (window title, Plot.put() "text" annotations) can't use markup.
- Loop model and why a pure delay is used for excess phase: see README.md "The model"
  and the constants at the top of `feedback_phase_sim.py`.

## Status
- Not yet pushed; GitHub remote (public) to be created later. MIT licensed (holder: electricyoshi).
