import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3, os
from pathlib import Path

st.set_page_config(page_title="AI Market Sentiment (Demo/Pro)", page_icon="📊", layout="wide")
st.title("📊 AI Market Sentiment — Demo / Pro")

# --- Demo/Pro switch ---
APP_MODE = os.getenv("APP_MODE", "demo").lower()  # "demo" or "pro"
DEMO_ASSETS = {"BTC"}
DEMO_DAYS = 3
HIDE_ALERTS_IN_DEMO = True

# --- Pro gate (with form) ---
PRO_KEY = os.getenv("PRO_KEY", "").strip()
if APP_MODE == "pro":
    st.info("Pro Mode: لطفاً کلید دسترسی را وارد کنید.")
    if "authed" not in st.session_state:
        st.session_state.authed = False

    with st.form("pro_login", clear_on_submit=False):
        user_key = st.text_input("Access key", type="password")
        submitted = st.form_submit_button("Unlock")

    if not PRO_KEY:
        st.error("کلید Pro روی سیستم ست نشده است. داخل run_dashboard_pro.bat مقدار PRO_KEY را تنظیم کن.")
        st.stop()

    if submitted:
        if user_key.strip() == PRO_KEY:
            st.session_state.authed = True
            st.success("Unlocked ✅")
        else:
            st.session_state.authed = False
            st.error("کلید اشتباه است. دوباره امتحان کن.")

    if not st.session_state.authed:
        st.stop()

BASE = Path(__file__).resolve().parent.parent
DB_DEFAULT = (BASE / "data" / "sentiment.db")
db_path = st.text_input("SQLite DB path", value=str(DB_DEFAULT))
st.caption(f"DB path: {db_path} | Mode: {APP_MODE.upper()}")

def load_daily(db_path: str) -> pd.DataFrame:
    p = Path(db_path)
    if not p.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    conn = sqlite3.connect(p)
    df = pd.read_sql_query(
        "SELECT day, asset, avg_sentiment, count_used FROM sentiments_daily ORDER BY day, asset", conn
    )
    conn.close()
    df["day"] = pd.to_datetime(df["day"])
    return df

try:
    df = load_daily(db_path)

    # Demo limits
    if APP_MODE == "demo" and not df.empty:
        df = df[df["asset"].isin(list(DEMO_ASSETS))].copy()
        last_day = df["day"].max()
        if pd.notnull(last_day):
            df = df[df["day"] >= (last_day - pd.Timedelta(days=DEMO_DAYS-1))]

    with st.sidebar:
        st.header("Filters")
        all_assets = sorted(df["asset"].unique().tolist()) if not df.empty else []
        selected_assets = st.multiselect("Assets", all_assets, default=all_assets)
        if not df.empty:
            min_day = df["day"].min().date()
            max_day = df["day"].max().date()
            dr = st.date_input("Date range", value=(min_day, max_day), min_value=min_day, max_value=max_day)
        else:
            dr = None

    if dr and isinstance(dr, tuple) and len(dr) == 2:
        start, end = pd.to_datetime(dr[0]), pd.to_datetime(dr[1])
    else:
        start, end = (df["day"].min(), df["day"].max()) if not df.empty else (None, None)

    if start is not None and not df.empty:
        f = (df["day"] >= start) & (df["day"] <= end)
        if selected_assets:
            f &= df["asset"].isin(selected_assets)
        dff = df.loc[f].copy()
    else:
        dff = df.copy()

    st.subheader("📈 Daily Sentiment by Asset")
    if dff.empty:
        st.warning("No data to display yet. Run ETL first.")
    else:
        fig = plt.figure(figsize=(9, 3.2))
        for a in (selected_assets or []):
            sub = dff[dff["asset"] == a]
            if not sub.empty:
                plt.plot(sub["day"], sub["avg_sentiment"], marker="o", label=f"{a} (n≈{int(sub['count_used'].sum())})")
        plt.axhline(0, linestyle="--", linewidth=1, alpha=0.5)
        plt.xlabel("Date")
        plt.ylabel("Avg Sentiment (-1..1)")
        plt.title("Daily Market Sentiment")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)

    st.subheader("🔔 Alerts")
    alerts_path = BASE / "data" / "alerts.log"
    if APP_MODE == "demo" and HIDE_ALERTS_IN_DEMO:
        st.caption("Demo Mode: Alerts are hidden. Upgrade to Pro for full alerts/history.")
    else:
        if alerts_path.exists():
            st.code(alerts_path.read_text(encoding="utf-8")[-2000:])
        else:
            st.caption("No alerts yet — run ETL with fresh data (RSS/CSV).")

    if APP_MODE == "demo":
        st.success("این نسخه Demo است: فقط BTC و 3 روز اخیر نمایش داده می‌شود. برای نسخه Pro (همه دارایی‌ها، Alerts و تاریخچه کامل) پیام بدهید.")

except Exception as e:
    st.error(f"Error: {e}")
