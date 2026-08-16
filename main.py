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


@app.get("/candles/{symbol}/{interval}")
async def candles(symbol: str, interval: str):

    allowed_intervals = {
        "1month",
        "1week",
        "1day",
        "4h",
        "1h",
        "30min",
        "15min",
        "5min",
    }

    if interval not in allowed_intervals:
        return {
            "error": "Invalid interval",
            "allowed_intervals": list(allowed_intervals),
        }

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "outputsize": 100,
        "apikey": TWELVE_DATA_API_KEY,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "data": data,
    }
