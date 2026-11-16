@echo off
REM Launcher for feedback_phase_sim.py (double-click to run).
REM   - %~dp0 anchors the path to this .bat file's own folder, so the folder can
REM     be moved, copied to a classroom PC, or cloned from GitHub and still work.
REM   - "start" + pyw/pythonw runs the GUI without a console window and lets this
REM     window close immediately. (A plain "pyw ..." line would make cmd wait for
REM     the GUI to exit, leaving a blank console open behind it.)
REM   - Fallback order covers both python.org installs (py launcher) and
REM     Microsoft Store / other installs (pythonw/python on PATH).
REM   - If no windowless Python is found, run with a console so errors are visible.

where pyw >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pyw "%~dp0feedback_phase_sim.py" %*
    exit /b
)
where pythonw >nul 2>nul
if %ERRORLEVEL%==0 (
    start "" pythonw "%~dp0feedback_phase_sim.py" %*
    exit /b
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py "%~dp0feedback_phase_sim.py" %*
    goto :done
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python "%~dp0feedback_phase_sim.py" %*
    goto :done
)
echo Python 3.8+ was not found. Install it from https://www.python.org/downloads/
echo (tick "Add python.exe to PATH" during setup), then run this file again.

:done
REM Keep the window open if anything failed so the error can be read.
if not %ERRORLEVEL%==0 pause
