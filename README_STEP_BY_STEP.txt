
=== راهنمای قدم‌به‌قدم (بدون نیاز به گیت‌هاب) ===

[۱] استخراج و نصب
- فایل ZIP را استخراج کن.
- پوشه را باز کن → وارد scripts/windows شو → روی setup_venv.bat دابل‌کلیک کن.
  (این کار محیط لازم را نصب می‌کند؛ بار اول ممکن است کمی طول بکشد چون مدل FinBERT دانلود می‌شود.)

[۲] اجرای دریافت خبرها (خودکارسازی ساده)
- روی run_etl.bat دابل‌کلیک کن → دیتابیس ساخته و به‌روزرسانی می‌شود (CSV + RSS).
- برای خودکارشدن: Task Scheduler را در ویندوز باز کن → Create Basic Task →
  Trigger: Daily یا Hourly (مثلاً هر 60 دقیقه)، Action: Start a Program →
  Program: مسیر کامل به فایل .venv\Scripts\python.exe
  Arguments: etl_to_sqlite.py
  Start in: مسیر پوشه پروژه

[۳] اجرای داشبورد
- نسخه دمو: run_dashboard_demo.bat
- نسخه پرو (لوکال): run_dashboard_pro.bat

[۴] پست خودکار به لینکدین (با Zapier)
- یک Zap با Trigger: "Catch Hook" و Action: "Create LinkedIn Post" بساز و URL Webhook را کپی کن.
- فایل scripts/windows/post_linkedin.bat را باز کن و خط زیر را با URL خودت تنظیم کن:
  set ZAPIER_HOOK_URL=...
- برای خودکارسازی پست روزانه: در Task Scheduler یک تسک جدید بساز و همین bat را روزی یک‌بار اجرا کن.

[۵] نکات
- app/config.yaml → تنظیم وزن و آستانه‌ها.
- اگر GOLD کمتر خبر داشت، RSS جدید به etl_to_sqlite.py اضافه کن.
