from flask import Flask, jsonify
from flask_cors import CORS
import requests, pandas as pd, traceback, os, threading, time
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

POST_ENDPOINT = "https://sat98-yfinchartdata.hf.space/update_symbols"
HEADERS = {"User-Agent": "Mozilla/5.0"}
INDEX_URL = "https://api.stockedge.com/Api/SecurityDashboardApi/GetComposedIndexParts/100792?page=1&pageSize=1000&lang=en"

# Cache
cache = {"data": None, "last_update": None}
IST = pytz.timezone("Asia/Kolkata")
REFRESH_INTERVAL = 150  # seconds
MARKET_START = (9, 15)
MARKET_END   = (15, 20)


def is_market_open():
    now = datetime.now(IST)
    # Weekday: Monday=0, ..., Friday=4
    if now.weekday() > 4:  
        return False

    start = now.replace(hour=MARKET_START[0], minute=MARKET_START[1], second=0, microsecond=0)
    end   = now.replace(hour=MARKET_END[0],   minute=MARKET_END[1],   second=0, microsecond=0)
    return start <= now <= end



def fetch_top_stocks(n=28):
    """Your existing StockEdge fetch logic"""
    try:
        resp = requests.get(INDEX_URL, headers=HEADERS, timeout=10)
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected StockEdge data format")

        df = pd.DataFrame(data)
        df_clean = df[['Nm', 'CZG', 'SecurityID']].copy()
        df_clean['CZG'] = pd.to_numeric(df_clean['CZG'], errors='coerce').fillna(0.0)

        gainers = int((df_clean['CZG'] > 0.015).sum())
        losers  = int((df_clean['CZG'] < -0.015).sum())
        neutral = int(((df_clean['CZG'] >= -0.015) & (df_clean['CZG'] <= 0.015)).sum())

        top_df = df_clean.sort_values(by='CZG', ascending=False).head(n)

        def fetch_security_info(security_id):
            try:
                url = f"https://api.stockedge.com/Api/SecurityDashboardApi/GetLatestSecurityInfo/{security_id}?lang=en"
                res = requests.get(url, headers=HEADERS, timeout=5)
                info = res.json()
                listing = next((l for l in info.get('Listings', []) if l['ExchangeName'] == "NSE"), None)
                if not listing and info.get('Listings'):
                    listing = info['Listings'][0]

                if listing:
                    symbol = listing.get('ListingSymbol', info.get('Name'))
                    c = listing.get('C', 0.0)
                    tq = listing.get('TQ', 0.0)
                    return symbol, float(c * tq)
                return info.get('Name'), 0.0
            except:
                return "N/A", 0.0

        stocks_list = []
        for _, row in top_df.iterrows():
            symbol, turnover = fetch_security_info(row['SecurityID'])
            stocks_list.append({"symbol": symbol, "pChange": float(row['CZG']), "totalTradedValue": turnover})

        stocks_list = sorted(stocks_list, key=lambda x: x['pChange'], reverse=True)

        # Post externally
        symbols = [s["symbol"] for s in stocks_list if s.get("symbol") not in ("N/A", None)]
        try:
            resp = requests.post(POST_ENDPOINT, json={"symbols": symbols}, timeout=10)
            if resp.status_code == 200:
                print(f"✅ Symbols posted ({len(symbols)})")
        except:
            pass

        return {"gainers": gainers, "losers": losers, "neutral": neutral, "stocks": stocks_list}

    except Exception as e:
        print("❌ Error in fetch_top_stocks:", e)
        traceback.print_exc()
        return {"error": str(e), "gainers": 0, "losers": 0, "neutral": 0, "stocks": []}


def refresh_cache_loop():
    while True:
        if is_market_open():
            print("⏱ Refreshing cache...")
            cache['data'] = fetch_top_stocks()
            cache['last_update'] = datetime.now(IST)
        time.sleep(REFRESH_INTERVAL)


@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    if cache['data'] is None:
        # Trigger fetch on first call even if market closed
        print("⚡ First fetch triggered (cache empty)")
        cache['data'] = fetch_top_stocks()
        cache['last_update'] = datetime.now(IST)

    return jsonify(cache['data']), 200


if __name__ == "__main__":
    threading.Thread(target=refresh_cache_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
