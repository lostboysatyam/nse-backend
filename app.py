from flask import Flask, jsonify
from flask_cors import CORS
from nse import NSE
from pathlib import Path
import requests
import os
import traceback

app = Flask(__name__)
CORS(app)

# Initialize NSE
nse = NSE(download_folder=Path("."), server=False)

# Remote endpoint to post symbols
POST_ENDPOINT = "https://sat98-yfinchartdata.hf.space/update_symbols"


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

        # ✅ Concatenate ".NS" to all symbols
        symbols = [s["symbol"] + ".NS" for s in top_stocks if s.get("symbol")]

        # ✅ Post the symbols to external endpoint with error handling
        try:
            resp = requests.post(
                POST_ENDPOINT,
                json={"symbols": symbols},
                timeout=10
            )
            if resp.status_code != 200:
                print(f"⚠️ POST failed: {resp.status_code} - {resp.text}")
            else:
                print(f"✅ Symbols posted successfully ({len(symbols)} symbols).")
        except requests.exceptions.RequestException as e:
            print("❌ Error posting symbols:", str(e))

        # Normal response
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


@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    data = fetch_top_stocks(28)
    if "error" in data:
        # return 500 if there was an error
        return jsonify(data), 500
    return jsonify(data), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
