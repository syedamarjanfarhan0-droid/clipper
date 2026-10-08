@echo off
REM Drag a video onto this file to turn it into vertical clips.
cd /d "%~dp0"
python clipper.py "%~1"
pause
