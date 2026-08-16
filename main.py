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

def detect_advanced_structure(candles, swing_window=2, liquidity_tolerance=0.0015):
    """
    Advanced structure engine.

    Detects:
    - Swing highs/lows
    - Equal highs/lows (liquidity pools)
    - Liquidity sweeps
    - Basic displacement
    - Validated BOS / CHoCH

    candles must be oldest -> newest.
    """

    if len(candles) < (swing_window * 2 + 10):
        return {
            "error": "Not enough candles",
            "required_minimum": swing_window * 2 + 10,
        }

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

    if len(data) < (swing_window * 2 + 10):
        return {
            "error": "Insufficient valid candle data"
        }

    # ---------------------------------------------------------
    # 1. Swing detection
    # ---------------------------------------------------------

    swing_highs = []
    swing_lows = []

    w = swing_window

    for i in range(w, len(data) - w):

        high = data[i]["high"]
        low = data[i]["low"]

        left_highs = [
            data[j]["high"]
            for j in range(i - w, i)
        ]

        right_highs = [
            data[j]["high"]
            for j in range(i + 1, i + w + 1)
        ]

        left_lows = [
            data[j]["low"]
            for j in range(i - w, i)
        ]

        right_lows = [
            data[j]["low"]
            for j in range(i + 1, i + w + 1)
        ]

        if high > max(left_highs) and high >= max(right_highs):
            swing_highs.append({
                "index": i,
                "datetime": data[i]["datetime"],
                "price": high,
            })

        if low < min(left_lows) and low <= min(right_lows):
            swing_lows.append({
                "index": i,
                "datetime": data[i]["datetime"],
                "price": low,
            })

    # ---------------------------------------------------------
    # 2. Equal highs / equal lows = potential liquidity
    # ---------------------------------------------------------

    equal_highs = []
    equal_lows = []

    for i in range(len(swing_highs)):
        for j in range(i + 1, len(swing_highs)):

            p1 = swing_highs[i]["price"]
            p2 = swing_highs[j]["price"]

            avg_price = (p1 + p2) / 2

            if avg_price > 0 and abs(p1 - p2) / avg_price <= liquidity_tolerance:

                equal_highs.append({
                    "first": swing_highs[i],
                    "second": swing_highs[j],
                    "liquidity_price": avg_price,
                })

    for i in range(len(swing_lows)):
        for j in range(i + 1, len(swing_lows)):

            p1 = swing_lows[i]["price"]
            p2 = swing_lows[j]["price"]

            avg_price = (p1 + p2) / 2

            if avg_price > 0 and abs(p1 - p2) / avg_price <= liquidity_tolerance:

                equal_lows.append({
                    "first": swing_lows[i],
                    "second": swing_lows[j],
                    "liquidity_price": avg_price,
                })

    # ---------------------------------------------------------
    # 3. Candle body / ATR-style displacement proxy
    # ---------------------------------------------------------

    true_ranges = []

    for i in range(1, len(data)):

        previous_close = data[i - 1]["close"]

        tr = max(
            data[i]["high"] - data[i]["low"],
            abs(data[i]["high"] - previous_close),
            abs(data[i]["low"] - previous_close),
        )

        true_ranges.append(tr)

    recent_tr = true_ranges[-20:]

    average_range = (
        sum(recent_tr) / len(recent_tr)
        if recent_tr
        else 0
    )

    displacement_threshold = average_range * 1.25

    def is_bullish_displacement(index):
        if index <= 0:
            return False

        candle = data[index]

        body = abs(candle["close"] - candle["open"])

        return (
            candle["close"] > candle["open"]
            and body >= displacement_threshold
        )

    def is_bearish_displacement(index):
        if index <= 0:
            return False

        candle = data[index]

        body = abs(candle["close"] - candle["open"])

        return (
            candle["close"] < candle["open"]
            and body >= displacement_threshold
        )

    # ---------------------------------------------------------
    # 4. Liquidity sweeps
    # ---------------------------------------------------------

    sweeps = []

    for i in range(1, len(data)):

        candle = data[i]

        # Buy-side liquidity sweep:
        # price trades above a prior swing/equal high,
        # then closes back below it.
        candidate_highs = [
            h for h in swing_highs
            if h["index"] < i
        ]

        if candidate_highs:

            recent_high = candidate_highs[-1]

            if (
                candle["high"] > recent_high["price"]
                and candle["close"] < recent_high["price"]
            ):
                sweeps.append({
                    "datetime": candle["datetime"],
                    "type": "BUY_SIDE_SWEEP",
                    "swept_level": recent_high["price"],
                    "price": candle["close"],
                    "index": i,
                })

        # Sell-side liquidity sweep:
        # price trades below a prior swing low,
        # then closes back above it.
        candidate_lows = [
            low for low in swing_lows
            if low["index"] < i
        ]

        if candidate_lows:

            recent_low = candidate_lows[-1]

            if (
                candle["low"] < recent_low["price"]
                and candle["close"] > recent_low["price"]
            ):
                sweeps.append({
                    "datetime": candle["datetime"],
                    "type": "SELL_SIDE_SWEEP",
                    "swept_level": recent_low["price"],
                    "price": candle["close"],
                    "index": i,
                })

    # ---------------------------------------------------------
    # 5. Validated BOS / CHoCH
    # ---------------------------------------------------------

    events = []

    trend = "NEUTRAL"

    broken_high_indices = set()
    broken_low_indices = set()

    for i in range(len(data)):

        close = data[i]["close"]

        prior_highs = [
            h for h in swing_highs
            if h["index"] < i
        ]

        prior_lows = [
            low for low in swing_lows
            if low["index"] < i
        ]

        if prior_highs:

            high = prior_highs[-1]

            if (
                close > high["price"]
                and high["index"] not in broken_high_indices
            ):

                displacement = is_bullish_displacement(i)

                previous_trend = trend

                if previous_trend == "BEARISH":
                    event_type = "CHoCH"
                else:
                    event_type = "BOS"

                events.append({
                    "datetime": data[i]["datetime"],
                    "type": event_type,
                    "direction": "BULLISH",
                    "break_price": close,
                    "broken_level": high["price"],
                    "displacement": displacement,
                    "index": i,
                })

                trend = "BULLISH"
                broken_high_indices.add(high["index"])

        if prior_lows:

            low = prior_lows[-1]

            if (
                close < low["price"]
                and low["index"] not in broken_low_indices
            ):

                displacement = is_bearish_displacement(i)

                previous_trend = trend

                if previous_trend == "BULLISH":
                    event_type = "CHoCH"
                else:
                    event_type = "BOS"

                events.append({
                    "datetime": data[i]["datetime"],
                    "type": event_type,
                    "direction": "BEARISH",
                    "break_price": close,
                    "broken_level": low["price"],
                    "displacement": displacement,
                    "index": i,
                })

                trend = "BEARISH"
                broken_low_indices.add(low["index"])

    # ---------------------------------------------------------
    # 6. Confirmed events
    # ---------------------------------------------------------

    confirmed_events = [
        event
        for event in events
        if event["displacement"] is True
    ]

    return {
        "trend": trend,
        "candle_count": len(data),

        "swing_highs": swing_highs[-20:],
        "swing_lows": swing_lows[-20:],

        "equal_highs": equal_highs[-10:],
        "equal_lows": equal_lows[-10:],

        "liquidity_sweeps": sweeps[-20:],

        "all_structure_events": events[-20:],

        "confirmed_structure_events": confirmed_events[-20:],

        "latest_swing_high": (
            swing_highs[-1]
            if swing_highs
            else None
        ),

        "latest_swing_low": (
            swing_lows[-1]
            if swing_lows
            else None
        ),
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

    candles = list(reversed(result["values"]))

    structure_result = detect_advanced_structure(candles)

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "structure": structure_result,
    }
TIMEFRAME_WEIGHTS = {
    "1month": 20,
    "1week": 18,
    "1day": 16,
    "4h": 14,
    "1h": 12,
    "30min": 8,
    "15min": 7,
    "5min": 5,
}


def calculate_bias_from_structure(structure):
    trend = structure.get("trend", "NEUTRAL")

    if trend == "BULLISH":
        return 1

    if trend == "BEARISH":
        return -1

    return 0


def calculate_multi_timeframe_bias(all_structures):
    """
    Weighted multi-timeframe directional bias.

    Returns:
    - score from -100 to +100
    - BULLISH / BEARISH / NEUTRAL
    """

    total_weight = 0
    weighted_score = 0

    timeframe_details = {}

    for timeframe, weight in TIMEFRAME_WEIGHTS.items():

        structure = all_structures.get(timeframe)

        if not structure:
            continue

        trend_score = calculate_bias_from_structure(structure)

        weighted_score += trend_score * weight
        total_weight += weight

        timeframe_details[timeframe] = {
            "trend": structure.get("trend", "NEUTRAL"),
            "weight": weight,
            "score": trend_score * weight,
        }

    if total_weight == 0:
        return {
            "bias": "NEUTRAL",
            "score": 0,
            "timeframes": timeframe_details,
        }

    normalized_score = (weighted_score / total_weight) * 100

    if normalized_score >= 35:
        bias = "BULLISH"

    elif normalized_score <= -35:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "score": round(normalized_score, 2),
        "timeframes": timeframe_details,
    }
    @app.get("/bias/{symbol}")
async def multi_timeframe_bias(symbol: str):

    url = "https://api.twelvedata.com/time_series"

    structures = {}

    async with httpx.AsyncClient(timeout=30) as client:

        for timeframe in TIMEFRAME_WEIGHTS:

            params = {
                "symbol": symbol.upper(),
                "interval": timeframe,
                "outputsize": 100,
                "apikey": TWELVE_DATA_API_KEY,
            }

            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                result = response.json()

                if "values" not in result:
                    structures[timeframe] = {
                        "trend": "NEUTRAL",
                        "error": result,
                    }
                    continue

                candles = list(reversed(result["values"]))

                structures[timeframe] = detect_advanced_structure(
                    candles
                )

            except Exception as e:

                structures[timeframe] = {
                    "trend": "NEUTRAL",
                    "error": str(e),
                }

    bias_result = calculate_multi_timeframe_bias(structures)

    return {
        "symbol": symbol.upper(),
        "multi_timeframe_bias": bias_result,
    }
TIMEFRAME_WEIGHTS = {
    "1month": 20,
    "1week": 18,
    "1day": 16,
    "4h": 14,
    "1h": 12,
    "30min": 8,
    "15min": 7,
    "5min": 5,
}


def calculate_bias_from_structure(structure):
    trend = structure.get("trend", "NEUTRAL")

    if trend == "BULLISH":
        return 1

    if trend == "BEARISH":
        return -1

    return 0


def calculate_multi_timeframe_bias(all_structures):

    total_weight = 0
    weighted_score = 0

    timeframe_details = {}

    for timeframe, weight in TIMEFRAME_WEIGHTS.items():

        structure = all_structures.get(timeframe)

        if not structure:
            continue

        trend_score = calculate_bias_from_structure(structure)

        weighted_score += trend_score * weight
        total_weight += weight

        timeframe_details[timeframe] = {
            "trend": structure.get("trend", "NEUTRAL"),
            "weight": weight,
            "score": trend_score * weight,
        }

    if total_weight == 0:
        return {
            "bias": "NEUTRAL",
            "score": 0,
            "timeframes": timeframe_details,
        }

    normalized_score = (weighted_score / total_weight) * 100

    if normalized_score >= 35:
        bias = "BULLISH"

    elif normalized_score <= -35:
        bias = "BEARISH"

    else:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "score": round(normalized_score, 2),
        "timeframes": timeframe_details,
    }


@app.get("/bias/{symbol}")
async def multi_timeframe_bias(symbol: str):

    url = "https://api.twelvedata.com/time_series"

    structures = {}

    async with httpx.AsyncClient(timeout=30) as client:

        for timeframe in TIMEFRAME_WEIGHTS:

            params = {
                "symbol": symbol.upper(),
                "interval": timeframe,
                "outputsize": 100,
                "apikey": TWELVE_DATA_API_KEY,
            }

            try:
                response = await client.get(url, params=params)
                response.raise_for_status()

                result = response.json()

                if "values" not in result:
                    structures[timeframe] = {
                        "trend": "NEUTRAL",
                        "error": result,
                    }
                    continue

                candles = list(reversed(result["values"]))

                structures[timeframe] = detect_advanced_structure(
                    candles
                )

            except Exception as e:

                structures[timeframe] = {
                    "trend": "NEUTRAL",
                    "error": str(e),
                }

    bias_result = calculate_multi_timeframe_bias(structures)

    return {
        "symbol": symbol.upper(),
        "multi_timeframe_bias": bias_result,
    }
