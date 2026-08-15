import os
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException

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

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()

        if data.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=data,
            )

        return {
            "symbol": symbol.upper(),
            "data": data,
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Market data request failed: {exc}",
        )


@app.get("/candles/{symbol}/{interval}")
async def candles(symbol: str, interval: str, outputsize: int = 100):
    allowed_intervals = {
        "1min",
        "5min",
        "15min",
        "30min",
        "1h",
        "4h",
        "1day",
        "1week",
        "1month",
    }

    if interval not in allowed_intervals:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Unsupported interval",
                "allowed_intervals": sorted(allowed_intervals),
            },
        )

    if outputsize < 1 or outputsize > 5000:
        raise HTTPException(
            status_code=400,
            detail="outputsize must be between 1 and 5000",
        )

    url = "https://api.twelvedata.com/time_series"

    params = {
        "symbol": symbol.upper(),
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()

        if data.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=data,
            )

        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "candles": data,
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Candle data request failed: {exc}",
        )
