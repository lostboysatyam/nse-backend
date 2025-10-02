from flask import Flask, jsonify
from nse import NSE
from pathlib import Path
import os

app = Flask(__name__)

# Initialize NSE
nse = NSE(download_folder=Path("."), server=False)

def fetch_top_stocks(n=28):
    # Fetch NIFTY TOTAL MARKET data
    raw_data = nse.listEquityStocksByIndex(index='NIFTY TOTAL MARKET')

    # Extract summary (advance/decline info)
    summary = raw_data.get("advance", {})

    # Extract stocks
    stocks_raw = raw_data.get("data", [])

    # Keep only relevant fields and filter out summary rows
    stocks = [
        {
            "symbol": stock["symbol"],
            "pChange": stock.get("pChange", 0),
            "totalTradedValue": stock.get("totalTradedValue", 0)
        }
        for stock in stocks_raw if stock.get("priority", 0) == 0
    ]

    # Sort by pChange descending and take top n
    top_stocks = sorted(stocks, key=lambda x: x["pChange"], reverse=True)[:n]

    # Return combined dict
    return {
        "summary": summary,
        "stocks": top_stocks
    }

@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    data = fetch_top_stocks(28)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
