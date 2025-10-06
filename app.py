from flask import Flask, jsonify
from flask_cors import CORS
import requests
import pandas as pd
import traceback
import os

app = Flask(__name__)
CORS(app)

# Remote endpoint to post symbols
POST_ENDPOINT = "https://sat98-yfinchartdata.hf.space/update_symbols"

# StockEdge headers
HEADERS = {"User-Agent": "Mozilla/5.0"}

# StockEdge URL for composed index
INDEX_URL = "https://api.stockedge.com/Api/SecurityDashboardApi/GetComposedIndexParts/100792?page=1&pageSize=1000&lang=en"


def fetch_top_stocks(n=28):
    try:
        # 1️⃣ Fetch StockEdge JSON data
        resp = requests.get(INDEX_URL, headers=HEADERS, timeout=10)
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected StockEdge data format")

        # 2️⃣ Convert to DataFrame
        df = pd.DataFrame(data)
        df_clean = df[['Nm', 'CZG', 'SecurityID']].copy()
        df_clean['CZG'] = pd.to_numeric(df_clean['CZG'], errors='coerce').fillna(0.0)

        # 3️⃣ Count gainers, losers, neutral
        gainers = int((df_clean['CZG'] > 0.03).sum())
        losers = int((df_clean['CZG'] < -0.03).sum())
        neutral = int(((df_clean['CZG'] >= -0.03) & (df_clean['CZG'] <= 0.03)).sum())

        # 4️⃣ Select top N by CZG
        top_df = df_clean.sort_values(by='CZG', ascending=False).head(n)

        # 5️⃣ Fetch latest security info and calculate turnover
        def fetch_security_info(security_id):
            try:
                url = f"https://api.stockedge.com/Api/SecurityDashboardApi/GetLatestSecurityInfo/{security_id}?lang=en"
                res = requests.get(url, headers=HEADERS, timeout=5)
                info = res.json()

                # Prefer NSE listing, else BSE
                listing = next((l for l in info.get('Listings', []) if l['ExchangeName'] == "NSE"), None)
                if not listing and info.get('Listings'):
                    listing = info['Listings'][0]

                if listing:
                    symbol = listing.get('ListingSymbol', info.get('Name'))
                    c = listing.get('C', 0.0)
                    tq = listing.get('TQ', 0.0)
                    turnover = float(c * tq)
                    return symbol, turnover
                else:
                    return info.get('Name'), 0.0
            except Exception:
                return "N/A", 0.0

        # 6️⃣ Build top stocks list
        stocks_list = []
        for _, row in top_df.iterrows():
            symbol, turnover = fetch_security_info(row['SecurityID'])
            stocks_list.append({
                "Symbol": symbol,
                "%Chg": float(row['CZG']),
                "Turnover": turnover
            })

        # Sort by % change descending
        stocks_list = sorted(stocks_list, key=lambda x: x['%Chg'], reverse=True)

        # 7️⃣ Post symbols to external endpoint
        symbols = [s["Symbol"] for s in stocks_list if s.get("Symbol")]
        try:
            resp = requests.post(POST_ENDPOINT, json={"symbols": symbols}, timeout=10)
            if resp.status_code != 200:
                print(f"⚠️ POST failed: {resp.status_code} - {resp.text}")
            else:
                print(f"✅ Symbols posted successfully ({len(symbols)} symbols).")
        except requests.exceptions.RequestException as e:
            print("❌ Error posting symbols:", str(e))

        return {
            "gainers": gainers,
            "losers": losers,
            "neutral": neutral,
            "stocks": stocks_list
        }

    except Exception as e:
        print("❌ Error in fetch_top_stocks:", str(e))
        traceback.print_exc()
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "gainers": 0,
            "losers": 0,
            "neutral": 0,
            "stocks": []
        }


@app.route("/top-stocks", methods=['GET'])
def top_stocks():
    data = fetch_top_stocks(28)
    if "error" in data:
        return jsonify(data), 500
    return jsonify(data), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
