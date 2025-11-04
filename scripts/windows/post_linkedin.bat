
@echo off
REM قبل از اجرا، لینک Webhook زپییر را اینجا بگذار:
REM set ZAPIER_HOOK_URL=https://hooks.zapier.com/hooks/catch/xxxx/yyyy
call .venv\Scripts\activate
python post_summary.py
pause
