@echo off
setlocal
cd /d "%~dp0..\.."

set APP_MODE=pro
set PRO_KEY=Farzin-1234

echo APP_MODE=%APP_MODE%
echo PRO_KEY length: %PRO_KEY:~0,0%%=%%  (hidden)
call .venv\Scripts\activate
streamlit run app\app_streamlit_db.py
