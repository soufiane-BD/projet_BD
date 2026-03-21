@echo off
REM Lance l'app avec Python 3.14 (là où Flask est installé). "python" seul pointe souvent vers 3.10 sans pip.
cd /d "%~dp0"
py -3.14 app.py
pause
