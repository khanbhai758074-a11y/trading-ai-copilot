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

TIMEFRAMES = [
    "1month",
    "1week",
    "1day",
    "4h",
    "1h",
    "30min",
    "15min",
    "5min",
]


@app.get("/multi-timeframe/{symbol}")
async def multi_timeframe(symbol: str):

    url = "https://api.twelvedata.com/time_series"

    results = {}

    async with httpx.AsyncClient(timeout=20) as client:

        for timeframe in TIMEFRAMES:

            params = {
                "symbol": symbol.upper(),
                "interval": timeframe,
                "outputsize": 100,
                "apikey": TWELVE_DATA_API_KEY,
            }

            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                results[timeframe] = data

            except Exception as e:
                results[timeframe] = {
                    "error": str(e)
                }

    return {
        "symbol": symbol.upper(),
        "timeframes": results,
    }

def detect_structure(candles, swing_window=2):
    """
    Detect swing highs/lows and basic BOS/CHoCH structure.

    candles are expected in chronological order:
    oldest -> newest
    """

    if not candles or len(candles) < (swing_window * 2 + 5):
        return {
            "error": "Not enough candle data",
            "required_minimum": swing_window * 2 + 5,
        }

    # Convert strings to floats and keep chronological order
    data = []

    for candle in candles:
        try:
            data.append({
                "datetime": candle["datetime"],
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle.get("volume", 0)),
            })
        except (KeyError, TypeError, ValueError):
            continue

    if len(data) < (swing_window * 2 + 5):
        return {
            "error": "Insufficient valid candle data"
        }

    swing_highs = []
    swing_lows = []

    w = swing_window

    # Swing detection
    for i in range(w, len(data) - w):

        current_high = data[i]["high"]
        current_low = data[i]["low"]

        left_highs = [
            data[j]["high"] for j in range(i - w, i)
        ]

        right_highs = [
            data[j]["high"] for j in range(i + 1, i + w + 1)
        ]

        left_lows = [
            data[j]["low"] for j in range(i - w, i)
        ]

        right_lows = [
            data[j]["low"] for j in range(i + 1, i + w + 1)
        ]

        if current_high > max(left_highs) and current_high >= max(right_highs):
            swing_highs.append({
                "index": i,
                "datetime": data[i]["datetime"],
                "price": current_high,
            })

        if current_low < min(left_lows) and current_low <= min(right_lows):
            swing_lows.append({
                "index": i,
                "datetime": data[i]["datetime"],
                "price": current_low,
            })

    # Default state
    trend = "NEUTRAL"
    events = []

    last_broken_high = None
    last_broken_low = None

    # Evaluate structure using candle closes
    for i in range(len(data)):

        close = data[i]["close"]

        previous_highs = [
            s for s in swing_highs
            if s["index"] < i
        ]

        previous_lows = [
            s for s in swing_lows
            if s["index"] < i
        ]

        latest_high = previous_highs[-1] if previous_highs else None
        latest_low = previous_lows[-1] if previous_lows else None

        # Bullish structure break
        if latest_high:
            level = latest_high["price"]

            if close > level and last_broken_high != latest_high["index"]:

                previous_trend = trend
                trend = "BULLISH"

                event_type = "BOS" if previous_trend in ["BULLISH", "NEUTRAL"] else "CHoCH"

                events.append({
                    "datetime": data[i]["datetime"],
                    "type": event_type,
                    "direction": "BULLISH",
                    "break_price": close,
                    "broken_level": level,
                    "reference": latest_high["datetime"],
                })

                last_broken_high = latest_high["index"]

        # Bearish structure break
        if latest_low:
            level = latest_low["price"]

            if close < level and last_broken_low != latest_low["index"]:

                previous_trend = trend
                trend = "BEARISH"

                event_type = "BOS" if previous_trend in ["BEARISH", "NEUTRAL"] else "CHoCH"

                events.append({
                    "datetime": data[i]["datetime"],
                    "type": event_type,
                    "direction": "BEARISH",
                    "break_price": close,
                    "broken_level": level,
                    "reference": latest_low["datetime"],
                })

                last_broken_low = latest_low["index"]

    # Keep recent events only
    recent_events = events[-20:]

    return {
        "trend": trend,
        "candle_count": len(data),
        "swing_highs": swing_highs[-20:],
        "swing_lows": swing_lows[-20:],
        "events": recent_events,
        "latest_swing_high": swing_highs[-1] if swing_highs else None,
        "latest_swing_low": swing_lows[-1] if swing_lows else None,
    }


@app.get("/structure/{symbol}/{interval}")
async def structure(symbol: str, interval: str):

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

        result = response.json()

    if "values" not in result:
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "error": result,
        }

    # Twelve Data normally returns newest -> oldest.
    # Structure engine needs oldest -> newest.
    candles = list(reversed(result["values"]))

    structure_result = detect_structure(candles)

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "structure": structure_result,
    }
