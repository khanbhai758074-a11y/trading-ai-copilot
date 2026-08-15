import os
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI

app = FastAPI(title="Trading AI Copilot")

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

if not TWELVE_DATA_API_KEY:
    raise RuntimeError("TWELVE_DATA_API_KEY is not configured")


@app.get("/")
async def home():
    return {
        "status": "online",
        "service": "Trading AI Copilot",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/market/{symbol}")
async def market(symbol: str):
    url = "https://api.twelvedata.com/price"

    params = {
        "symbol": symbol.upper(),
        "apikey": TWELVE_DATA_API_KEY,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "symbol": symbol.upper(),
        "data": data,
    }
