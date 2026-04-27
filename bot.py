import os
import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


TOKEN = (
    os.getenv("TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
)


# =========================
# RENDER HEALTH SERVER
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot V9 BTC running")


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Bot V9 BTC HYBRID Ready 🔥\n"
        "Alefaso screenshot BTC chart.\n\n"
        "Bot dia haka prix réel BTC/USDT + hanao analyse image."
    )


# =========================
# BINANCE API BTC
# =========================
def fetch_binance_klines(symbol="BTCUSDT", interval="15m", limit=120):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"

    with urllib.request.urlopen(url, timeout=15) as response:
        data = json.loads(response.read().decode())

    candles = []
    for k in data:
        candles.append({
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        })

    return candles


def ema(values, period):
    if len(values) < period:
        return values[-1]

    multiplier = 2 / (period + 1)
    ema_value = sum(values[:period]) / period

    for price in values[period:]:
        ema_value = (price - ema_value) * multiplier + ema_value

    return ema_value


def rsi(values, period=14):
    if len(values) <= period:
        return 50

    gains = []
    losses = []

    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def atr(candles, period=14):
    if len(candles) <= period:
        return 0

    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)

    return round(sum(trs[-period:]) / period, 2)


def market_data_btc():
    candles = fetch_binance_klines("BTCUSDT", "15m", 120)

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    price = closes[-1]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    atr14 = atr(candles, 14)

    recent_high = max(highs[-30:])
    recent_low = min(lows[-30:])

    if price > ema20 > ema50:
        api_trend = "BULLISH"
    elif price < ema20 < ema50:
        api_trend = "BEARISH"
    else:
        api_trend = "NEUTRAL"

    if rsi14 > 65:
        rsi_state = "OVERBOUGHT"
    elif rsi14 < 35:
        rsi_state = "OVERSOLD"
    elif rsi14 > 50:
        rsi_state = "BULLISH"
    else:
        rsi_state = "BEARISH"

    return {
        "price": price,
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "rsi": rsi14,
        "atr": atr14,
        "recent_high": round(recent_high, 2),
        "recent_low": round(recent_low, 2),
        "api_trend": api_trend,
        "rsi_state": rsi_state,
    }


# =========================
# IMAGE ANALYSIS
# =========================
def analyze_image_chart(image_path):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    x1 = int(w * 0.05)
    y1 = int(h * 0.12)
    x2 = int(w * 0.90)
    y2 = int(h * 0.68)

    chart = img.crop((x1, y1, x2, y2))
    cw, ch = chart.size

    def is_chart_pixel(r, g, b):
        return r < 220 or g < 220 or b < 220

    def points(part):
        pts = []
        for y in range(part.size[1]):
            for x in range(part.size[0]):
                r, g, b = part.getpixel((x, y))
                if is_chart_pixel(r, g, b):
                    pts.append((x, y, r, g, b))
        return pts

    def avg_y(part):
        pts = points(part)
        if not pts:
            return part.size[1] / 2
        return sum(p[1] for p in pts) / len(pts)

    def pressure(part):
        pts = points(part)
        bull = 0
        bear = 0

        for x, y, r, g, b in pts:
            if g > r + 20 or b > r + 20:
                bull += 1
            elif r > g + 20 or r > b + 20:
                bear += 1

        if bull > bear * 1.25:
            return "BULLISH"
        elif bear > bull * 1.25:
            return "BEARISH"
        return "NEUTRAL"

    left = chart.crop((0, 0, int(cw * 0.30), ch))
    mid = chart.crop((int(cw * 0.35), 0, int(cw * 0.65), ch))
    right = chart.crop((int(cw * 0.70), 0, cw, ch))
    last = chart.crop((int(cw * 0.85), 0, cw, ch))

    left_y = avg_y(left)
    mid_y = avg_y(mid)
    right_y = avg_y(right)

    if right_y < left_y - 12:
        visual_trend = "BULLISH"
    elif right_y > left_y + 12:
        visual_trend = "BEARISH"
    else:
        visual_trend = "RANGE"

    if right_y < mid_y - 8:
        momentum = "BULLISH"
    elif right_y > mid_y + 8:
        momentum = "BEARISH"
    else:
        momentum = "NEUTRAL"

    recent_pressure = pressure(last)

    pts_all = points(chart)
    ys = [p[1] for p in pts_all]

    if ys:
        liquidity_high_y = min(ys)
        liquidity_low_y = max(ys)
    else:
        liquidity_high_y = int(ch * 0.25)
        liquidity_low_y = int(ch * 0.75)

    price_y = right_y

    if price_y <= liquidity_high_y + 30:
        visual_zone = "PROCHE RESISTANCE"
    elif price_y >= liquidity_low_y - 30:
        visual_zone = "PROCHE SUPPORT"
    else:
        visual_zone = "MILIEU"

    if visual_trend == "BULLISH" and momentum == "BULLISH":
        structure = "BOS haussier possible"
    elif visual_trend == "BEARISH" and momentum == "BEARISH":
        structure = "BOS baissier possible"
    elif visual_trend == "BULLISH" and momentum == "BEARISH":
        structure = "CHoCH baissier possible"
    elif visual_trend == "BEARISH" and momentum == "BULLISH":
        structure = "CHoCH haussier possible"
    else:
        structure = "Structure neutre / range"

    return {
        "img": img,
        "x1": x1,
        "x2": x2,
        "y1": y1,
        "y2": y2,
        "visual_trend": visual_trend,
        "momentum": momentum,
        "pressure": recent_pressure,
        "visual_zone": visual_zone,
        "structure": structure,
        "liquidity_high_y": y1 + liquidity_high_y,
        "liquidity_low_y": y1 + liquidity_low_y,
    }


# =========================
# DECISION ENGINE
# =========================
def build_trade_plan(image_result, market):
    visual_trend = image_result["visual_trend"]
    momentum = image_result["momentum"]
    pressure = image_result["pressure"]
    visual_zone = image_result["visual_zone"]

    price = market["price"]
    atr_value = market["atr"]
    api_trend = market["api_trend"]
    rsi_state = market["rsi_state"]
    rsi_value = market["rsi"]
    recent_high = market["recent_high"]
    recent_low = market["recent_low"]

    confidence = 50
    reasons = []

    # Confluence API + image
    if api_trend == "BULLISH" and visual_trend == "BULLISH":
        confidence += 20
        reasons.append("API trend + image trend bullish")
    elif api_trend == "BEARISH" and visual_trend == "BEARISH":
        confidence += 20
        reasons.append("API trend + image trend bearish")
    else:
        confidence -= 5
        reasons.append("API et image pas totalement alignés")

    if momentum == "BULLISH":
        confidence += 8
        reasons.append("Momentum image bullish")
    elif momentum == "BEARISH":
        confidence += 8
        reasons.append("Momentum image bearish")

    if pressure == "BULLISH" and api_trend == "BULLISH":
        confidence += 8
        reasons.append("Pression récente acheteuse")
    elif pressure == "BEARISH" and api_trend == "BEARISH":
        confidence += 8
        reasons.append("Pression récente vendeuse")

    if rsi_state in ["OVERBOUGHT", "OVERSOLD"]:
        confidence -= 8
        reasons.append(f"RSI en zone extrême: {rsi_state}")

    confidence = max(40, min(88, confidence))

    # Décision signal
    if api_trend == "BULLISH" and visual_trend == "BULLISH" and rsi_value < 70 and visual_zone != "PROCHE RESISTANCE":
        signal = "BUY"
        entry = round(price, 2)
        sl = round(price - (atr_value * 1.5), 2)
        tp1 = round(price + (atr_value * 1.5), 2)
        tp2 = round(price + (atr_value * 3.0), 2)
        scenario = "Continuation haussière probable si BTC garde EMA20/EMA50 et confirme le pullback."
        invalidation = "Signal invalidé si cassure forte sous EMA20 ou sous support récent."
        conseil = "Attendre un petit pullback ou bougie de confirmation avant BUY."

    elif api_trend == "BEARISH" and visual_trend == "BEARISH" and rsi_value > 30 and visual_zone != "PROCHE SUPPORT":
        signal = "SELL"
        entry = round(price, 2)
        sl = round(price + (atr_value * 1.5), 2)
        tp1 = round(price - (atr_value * 1.5), 2)
        tp2 = round(price - (atr_value * 3.0), 2)
        scenario = "Continuation baissière probable si BTC rejette la résistance ou EMA20."
        invalidation = "Signal invalidé si cassure forte au-dessus EMA50 ou résistance récente."
        conseil = "Attendre pullback + rejet avant SELL."

    elif visual_zone == "PROCHE SUPPORT" and pressure == "BULLISH":
        signal = "BUY ATTENTE"
        entry = round(price, 2)
        sl = round(recent_low - (atr_value * 0.5), 2)
        tp1 = round(price + atr_value, 2)
        tp2 = round(recent_high, 2)
        scenario = "Rebond possible sur support après prise de liquidité basse."
        invalidation = "Cassure nette sous le support récent."
        conseil = "Entrée agressive seulement si bougie verte de confirmation."

    elif visual_zone == "PROCHE RESISTANCE" and pressure == "BEARISH":
        signal = "SELL ATTENTE"
        entry = round(price, 2)
        sl = round(recent_high + (atr_value * 0.5), 2)
        tp1 = round(price - atr_value, 2)
        tp2 = round(recent_low, 2)
        scenario = "Rejet possible sur résistance après prise de liquidité haute."
        invalidation = "Cassure nette au-dessus de la résistance récente."
        conseil = "Entrée agressive seulement si rejet confirmé."

    else:
        signal = "WAIT"
        entry = "Non validée"
        sl = "Non défini"
        tp1 = "Non défini"
        tp2 = "Non défini"
        scenario = "Confluence insuffisante entre image et data marché."
        invalidation = "Aucun setup propre pour le moment."
        conseil = "Attendre BOS/CHoCH clair, pullback ou rejet confirmé."

    return {
        "signal": signal,
        "confidence": confidence,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "scenario": scenario,
        "invalidation": invalidation,
        "conseil": conseil,
        "reasons": reasons,
    }


# =========================
# ANNOTATION IMAGE
# =========================
def annotate_image(image_result, plan, output_path):
    img = image_result["img"].copy()
    draw = ImageDraw.Draw(img)

    x1 = image_result["x1"]
    x2 = image_result["x2"]
    high_y = image_result["liquidity_high_y"]
    low_y = image_result["liquidity_low_y"]

    draw.line((x1, high_y, x2, high_y), fill="red", width=4)
    draw.text((x1 + 10, max(0, high_y - 25)), "LIQUIDITY HIGH / RESISTANCE", fill="red")

    draw.line((x1, low_y, x2, low_y), fill="green", width=4)
    draw.text((x1 + 10, low_y + 8), "LIQUIDITY LOW / SUPPORT", fill="green")

    w, h = img.size
    signal = plan["signal"]

    if "BUY" in signal:
        color = "green"
        draw.rectangle((x1, int(h * 0.55), x2, int(h * 0.68)), outline=color, width=4)
        draw.text((x1 + 10, int(h * 0.56)), "BUY / PULLBACK ZONE", fill=color)
        draw.polygon(
            [(w * 0.80, h * 0.52), (w * 0.74, h * 0.64), (w * 0.86, h * 0.64)],
            fill=color
        )
    elif "SELL" in signal:
        color = "red"
        draw.rectangle((x1, int(h * 0.25), x2, int(h * 0.38)), outline=color, width=4)
        draw.text((x1 + 10, int(h * 0.26)), "SELL / PULLBACK ZONE", fill=color)
        draw.polygon(
            [(w * 0.80, h * 0.66), (w * 0.74, h * 0.54), (w * 0.86, h * 0.54)],
            fill=color
        )
    else:
        draw.text((w * 0.68, h * 0.65), "WAIT / NO CLEAN ENTRY", fill="yellow")

    img.save(output_path)


# =========================
# TELEGRAM HANDLER
# =========================
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document:
        file = await update.message.document.get_file()
    else:
        return

    input_path = "btc_chart_input.jpg"
    output_path = "btc_v9_annotated.jpg"

    await file.download_to_drive(input_path)
    await update.message.reply_text("📥 Analyse V9 BTC Hybrid en cours...")

    try:
        image_result = analyze_image_chart(input_path)
        market = market_data_btc()
        plan = build_trade_plan(image_result, market)

        annotate_image(image_result, plan, output_path)

        reasons_text = "\n".join([f"- {r}" for r in plan["reasons"]])

        msg = f"""
🔥 ANALYSE PRO V9 BTC HYBRID

📊 ACTIF:
BTC/USDT

💰 DATA MARCHÉ RÉELLE:
Prix actuel: {market['price']}
EMA20: {market['ema20']}
EMA50: {market['ema50']}
RSI 14: {market['rsi']} ({market['rsi_state']})
ATR 14: {market['atr']}
High récent: {market['recent_high']}
Low récent: {market['recent_low']}

🧭 BIAS:
API Trend: {market['api_trend']}
Image Trend: {image_result['visual_trend']}
Momentum image: {image_result['momentum']}
Pression récente: {image_result['pressure']}

🏗️ STRUCTURE:
{image_result['structure']}

📍 ZONE:
{image_result['visual_zone']}

🎯 SIGNAL:
{plan['signal']}
Confidence: {plan['confidence']}%

🚀 ENTRY:
{plan['entry']}

🛑 SL:
{plan['sl']}

✅ TP:
TP1: {plan['tp1']}
TP2: {plan['tp2']}

📌 RAISONS:
{reasons_text}

📈 SCÉNARIO PRINCIPAL:
{plan['scenario']}

❌ INVALIDATION:
{plan['invalidation']}

🧠 CONSEIL TRADER:
{plan['conseil']}

⚠️ Analyse éducative/indicative. Pas de garantie.
"""

        await update.message.reply_photo(photo=open(output_path, "rb"))
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur V9 BTC: {e}")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("TOKEN tsy hita. Ampidiro ao Render Environment Variables.")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    print("Bot V9 BTC Hybrid lancé 🔥")
    app.run_polling()
