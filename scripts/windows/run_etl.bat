@echo off
setlocal
REM برو به ریشه‌ی پروژه (دو پوشه بالاتر از scripts/windows)
cd /d "%~dp0..\.."

call .venv\Scripts\activate
python etl_to_sqlite.py
pause

