@echo off
setlocal
cd /d "%~dp0..\.."

set APP_MODE=demo
call .venv\Scripts\activate
streamlit run app\app_streamlit_db.py
