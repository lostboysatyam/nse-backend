from flask import Flask, jsonify
from flask_cors import CORS
from nse import NSE
from pathlib import Path
import traceback
import time

app = Flask(__name__)
CORS(app)


@app.route("/reinitialize-nse", methods=['GET'])
def refresh_nse():
    global nse  # ensure we're updating global vars
    
    try:
        print("🔄 Refreshing NSE session...")
        nse.exit()
        time.sleep(2)  # give time for file unlock + avoid NSE rate limit
    except Exception as e:
        print(f"⚠️ NSE exit failed: {e}")

    try:
        nse = NSE(download_folder=Path("."), server=True)
        logging.info("✅ NSE session refreshed successfully")
    except Exception as e:
        print(f"❌ NSE refresh failed: {e}")

# Initialize NSE
nse = NSE(download_folder=Path("."), server=True)

# Cache
cache = {"data": None}


def fetch_top_stocks(n=28):
    """Fetch top N NSE stocks by % change."""
    try:
        raw_data = nse.listEquityStocksByIndex(index='NIFTY TOTAL MARKET')
        if not raw_data or "data" not in raw_data:
            raise ValueError("Invalid or empty data returned from NSE API")

        summary = raw_data.get("advance", {})
        stocks_raw = raw_data.get("data", [])

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

        top_stocks = sorted(stocks, key=lambda x: x["pChange"], reverse=True)[:n]

        return {"summary": summary, "stocks": top_stocks}

    except Exception as e:
        print("❌ Error in fetch_top_stocks:", str(e))
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc(), "summary": {}, "stocks": []}


@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    """Return cached top stocks, fetch if cache is empty."""
    if cache['data'] is None:
        print("⚡ Cache empty, fetching data for the first time...")
        cache['data'] = fetch_top_stocks()
    return jsonify(cache['data']), 200


@app.route("/refresh-cache", methods=['GET'])
def refresh_cache():
    """Refresh the cache on demand (to be called by external cron)."""
    print("⏱ Refreshing cache via endpoint...")
    cache['data'] = fetch_top_stocks()
    return "Cache refreshed", 200


if __name__ == "__main__":
    port = 5000
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
