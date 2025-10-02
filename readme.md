# NSE Backend API

## Overview
This Flask app provides the top 28 NIFTY TOTAL MARKET stocks in JSON format.

## API Endpoint
- `GET /top-stocks` → returns JSON:
```json
[
  {"symbol": "SUNTV", "pChange": 12.36, "totalTradedValue": 7163530492.5},
  ...
]
