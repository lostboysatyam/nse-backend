from flask import Flask, jsonify
from nse import NSE
from pathlib import Path
import pandas as pd
import os

app = Flask(__name__)

# Initialize NSE
nse = NSE(download_folder=Path("."), server=False)

def fetch_top_stocks(n=28):
    # Fetch NIFTY TOTAL MARKET stocks
    data = nse.listEquityStocksByIndex(index='NIFTY TOTAL MARKET')
    stock_list = data.get("data", [])

    # Convert to DataFrame
    df = pd.DataFrame(stock_list)

    # Keep only relevant columns
    df = df[['symbol', 'pChange', 'totalTradedValue']]

    # Sort by pChange descending
    df_sorted = df.sort_values(by='pChange', ascending=False)

    # Take top n
    top_stocks = df_sorted.head(n)

    # Convert to list of dicts
    return top_stocks.to_dict(orient='records')

@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    data = fetch_top_stocks(28)
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
