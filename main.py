from fastapi import FastAPI, Request
from datetime import datetime, timezone

app = FastAPI(title="Trading AI Copilot")


@app.get("/")
async def home():
    return {
        "status": "online",
        "service": "Trading AI Copilot",
        "time": datetime.now(timezone.utc).isoformat()
    }


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {"raw": await request.body()}

    print("TradingView ALERT:")
    print(data)

    return {
        "received": True,
        "message": "Webhook received successfully"
    }
