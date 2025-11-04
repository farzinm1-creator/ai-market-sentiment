import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime
import feedparser
import yaml

from app.sentiment_backend import ensemble_scores

CFG_PATH = Path("app/config.yaml")
CFG = yaml.safe_load(open(CFG_PATH, "r", encoding="utf-8")) if CFG_PATH.exists() else {}
MIN_ABS_FOR_DAILY = float(CFG.get("min_abs_final_for_daily", 0.12))
DELTA_THRESHOLD = 0.30
USE_RSS = True

CSV_PATH = Path("data/news_sample_multiasset.csv")
DB_PATH = Path("data/sentiment.db")
ALERTS_LOG = Path("data/alerts.log")

# منابع خبری متنوع و پایدار
RSS_SOURCES = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/marketsNews",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.kitco.com/rss/",
    "https://www.investing.com/rss/news_25.rss",   # gold
    "https://oilprice.com/rss/main",
    "https://www.fxstreet.com/rss"
]

# نگاشت کلیدواژه‌ها به دارایی‌ها (حروف کوچک بررسی می‌شود)
ASSET_KEYWORDS = {
    "BTC":    ["bitcoin", "btc", "crypto"],
    "ETH":    ["ethereum", "eth"],
    "GOLD":   ["gold", "xau", "bullion", "precious metal", "safe haven"],
    "OIL":    ["oil", "brent", "wti", "crude"],
    "SP500":  ["s&p 500", "s&p500", "sp500", "gspc", "s&p index", "us stocks"],
    "USD":    ["us dollar", "dollar index", "dxy", "greenback", "usd"],
    "EURUSD": ["eurusd", "eur/usd", "euro-dollar", "euro vs dollar"]
}

def ensure_tables(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS news_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        source TEXT,
        asset TEXT,
        title TEXT,
        text TEXT,
        sentiment REAL,
        confidence REAL,
        low_confidence INTEGER
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS sentiments_daily (
        day TEXT,
        asset TEXT,
        avg_sentiment REAL,
        count_used INTEGER,
        PRIMARY KEY (day, asset)
    )
    """)
    conn.commit()

def write_alert(msg: str):
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

def infer_asset(title: str, summary: str) -> str | None:
    text = f"{title} {summary}".lower()
    for asset, kws in ASSET_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return asset
    return None

def fetch_rss_rows() -> list[dict]:
    rows = []
    today = datetime.utcnow().strftime("%Y-%m-%d")
    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = getattr(e, "title", "") or ""
                summary = getattr(e, "summary", "") or ""
                asset = infer_asset(title, summary)
                if not asset:
                    continue
                source = feed.feed.title if hasattr(feed, "feed") and hasattr(feed.feed, "title") else "RSS"
                rows.append({
                    "date": today,
                    "source": source,
                    "asset": asset,
                    "title": title.strip(),
                    "text": summary.strip()
                })
        except Exception:
            continue
    return rows

def load_csv_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    needed = {"date","source","asset","title","text"}
    if not needed.issubset(df.columns):
        raise ValueError(f"CSV must include columns: {needed}")
    return df.to_dict(orient="records")

def upsert_news(conn, rows: list[dict]):
    if not rows:
        return pd.DataFrame(columns=["date","source","asset","title","text","sentiment","confidence","low_confidence"])
    df = pd.DataFrame(rows)
    texts = (df["title"].fillna("") + " " + df["text"].fillna("")).tolist()
    final, confs, low_flags = ensemble_scores(texts)
    df["sentiment"] = final
    df["confidence"] = confs
    df["low_confidence"] = [1 if lf else 0 for lf in low_flags]
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["date"])
    df["key"] = df["date"].astype(str) + "|" + df["asset"].astype(str) + "|" + df["title"].astype(str)
    existing = pd.read_sql_query("SELECT date, asset, title FROM news_raw", conn)
    if not existing.empty:
        existing["key"] = existing["date"].astype(str) + "|" + existing["asset"].astype(str) + "|" + existing["title"].astype(str)
        df = df[~df["key"].isin(existing["key"])]
    if not df.empty:
        df[["date","source","asset","title","text","sentiment","confidence","low_confidence"]].to_sql(
            "news_raw", conn, if_exists="append", index=False
        )
    return df

def recompute_daily(conn):
    raw = pd.read_sql_query("SELECT date, asset, sentiment, low_confidence FROM news_raw", conn)
    if raw.empty:
        return pd.DataFrame(columns=["day","asset","avg_sentiment","count_used"])
    raw["date"] = pd.to_datetime(raw["date"])
    use = (raw["low_confidence"] == 0) & (raw["sentiment"].abs() >= MIN_ABS_FOR_DAILY)
    raw_use = raw.loc[use].copy()
    if raw_use.empty:
        daily = pd.DataFrame(columns=["day","asset","avg_sentiment","count_used"])
    else:
        daily = raw_use.groupby([raw_use["date"].dt.strftime("%Y-%m-%d"), "asset"]).agg(
            avg_sentiment=("sentiment","mean"),
            count_used=("sentiment","size")
        ).reset_index().rename(columns={"date":"day"})
    prev = pd.read_sql_query("SELECT * FROM sentiments_daily", conn)
    for _, r in daily.iterrows():
        conn.execute(
            "INSERT OR REPLACE INTO sentiments_daily (day, asset, avg_sentiment, count_used) VALUES (?, ?, ?, ?)",
            (r["day"], r["asset"], float(r["avg_sentiment"]), int(r["count_used"]))
        )
    conn.commit()
    if not prev.empty and not daily.empty:
        merged = daily.merge(prev, on=["day","asset"], how="left", suffixes=("", "_prev"))
        merged["delta"] = (merged["avg_sentiment"] - merged["avg_sentiment_prev"]).abs()
        spikes = merged[(~merged["avg_sentiment_prev"].isna()) & (merged["delta"] > 0.30)]
        for _, s in spikes.iterrows():
            if int(s.get("count_used", 1)) >= 2:
                write_alert(f"ALERT: {s['asset']} on {s['day']} change {s['delta']:.2f} "
                            f"(from {s['avg_sentiment_prev']:.2f} to {s['avg_sentiment']:.2f}, n={int(s.get('count_used',0))})")
    return daily

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_tables(conn)
    csv_rows = load_csv_rows(); upsert_news(conn, csv_rows)
    rss_rows = fetch_rss_rows() if USE_RSS else []
    upsert_news(conn, rss_rows)
    recompute_daily(conn)
    conn.close()
    print(f"ETL complete. CSV rows: {len(csv_rows)} | RSS rows: {len(rss_rows)} | DB: {DB_PATH}")

if __name__ == "__main__":
    main()
