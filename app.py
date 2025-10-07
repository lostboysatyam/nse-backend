from flask import Flask, jsonify
from flask_cors import CORS
from nse import NSE
from pathlib import Path
import requests
import os
import traceback
import threading
import time
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

# Initialize NSE
nse = NSE(download_folder=Path("."), server=True)

# Cache
cache = {"data": None, "last_update": None}
IST = pytz.timezone("Asia/Kolkata")
REFRESH_INTERVAL = 10  # seconds
MARKET_START = (9, 15)
MARKET_END = (15, 20)


def is_market_open():
    now = datetime.now(IST)
    print("Checking market open, now:", now)
    if now.weekday() > 4:
        print("Market closed: weekend")
        return False
    start = now.replace(hour=MARKET_START[0], minute=MARKET_START[1], second=0, microsecond=0)
    end = now.replace(hour=MARKET_END[0], minute=MARKET_END[1], second=0, microsecond=0)
    print(f"Market start: {start}, end: {end}")
    return start <= now <= end



def fetch_top_stocks(n=28):
    try:
        # Fetch NSE data
        raw_data = nse.listEquityStocksByIndex(index='NIFTY TOTAL MARKET')
        if not raw_data or "data" not in raw_data:
            raise ValueError("Invalid or empty data returned from NSE API")

        summary = raw_data.get("advance", {})
        stocks_raw = raw_data.get("data", [])

        # Extract relevant fields
        stocks = []
        for stock in stocks_raw:
            if stock.get("priority", 0) == 0:
                try:
                    pChange = float(stock.get("pChange", 0) or 0)
                    totalTradedValue = float(stock.get("totalTradedValue", 0) or 0)
                except (ValueError, TypeError):
                    pChange = 0.0
                    totalTradedValue = 0.0

                stocks.append({
                    "symbol": stock.get("symbol", "N/A"),
                    "pChange": pChange,
                    "totalTradedValue": totalTradedValue
                })

        # Sort by % change
        top_stocks = sorted(stocks, key=lambda x: x["pChange"], reverse=True)[:n]

        return {
            "summary": summary,
            "stocks": top_stocks
        }

    except Exception as e:
        # Catch *any* error and return safely
        print("❌ Error in fetch_top_stocks:", str(e))
        traceback.print_exc()

        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "summary": {},
            "stocks": []
        }


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
        print("⚡ First fetch triggered (cache empty)")
        cache['data'] = fetch_top_stocks()
        cache['last_update'] = datetime.now(IST)

    return jsonify(cache['data']), 200


if __name__ == "__main__":
    print("Starting refresh thread...")
    threading.Thread(target=refresh_cache_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
