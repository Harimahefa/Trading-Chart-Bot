import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


TOKEN = os.getenv("8225959243:AAFPByF33ZXIH69oekdqmcKudU8EDft5gJc")


# =========================
# RENDER HEALTH SERVER
# =========================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot V6 running")


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Chart Vision Bot V6 SMC Ready 🔥\nAlefaso screenshot chart."
    )


# =========================
# IMAGE ANALYSIS
# =========================
def analyze_smc(image_path):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Crop zone chart principale
    x1, y1, x2, y2 = int(w * 0.05), int(h * 0.12), int(w * 0.90), int(h * 0.68)
    chart = img.crop((x1, y1, x2, y2))
    cw, ch = chart.size

    def dark_points(part):
        pts = []
        for y in range(part.size[1]):
            for x in range(part.size[0]):
                r, g, b = part.getpixel((x, y))
                if r < 210 or g < 210 or b < 210:
                    pts.append((x, y, r, g, b))
        return pts

    def avg_y_zone(x_start, x_end):
        part = chart.crop((x_start, 0, x_end, ch))
        pts = dark_points(part)
        if not pts:
            return ch / 2
        return sum(p[1] for p in pts) / len(pts)

    left_y = avg_y_zone(0, int(cw * 0.30))
    mid_y = avg_y_zone(int(cw * 0.35), int(cw * 0.65))
    right_y = avg_y_zone(int(cw * 0.70), cw)
    last_y = avg_y_zone(int(cw * 0.85), cw)

    all_pts = dark_points(chart)
    ys = [p[1] for p in all_pts]

    if ys:
        liquidity_high_y = min(ys)
        liquidity_low_y = max(ys)
    else:
        liquidity_high_y = int(ch * 0.25)
        liquidity_low_y = int(ch * 0.75)

    # Trend
    if right_y < left_y - 10:
        trend = "UP"
    elif right_y > left_y + 10:
        trend = "DOWN"
    else:
        trend = "RANGE"

    # Momentum
    if right_y < mid_y - 6:
        momentum = "BULLISH"
    elif right_y > mid_y + 6:
        momentum = "BEARISH"
    else:
        momentum = "NEUTRAL"

    # BOS / CHoCH approximatif
    if trend == "UP" and right_y < mid_y:
        structure = "BOS haussier possible"
    elif trend == "DOWN" and right_y > mid_y:
        structure = "BOS baissier possible"
    elif trend == "UP" and momentum == "BEARISH":
        structure = "CHoCH baissier possible"
    elif trend == "DOWN" and momentum == "BULLISH":
        structure = "CHoCH haussier possible"
    else:
        structure = "Structure neutre"

    # Order Block zone approximative
    if trend == "UP":
        ob_top = int(ch * 0.60)
        ob_bottom = int(ch * 0.75)
        signal = "BUY"
        entry = "Buy sur retour dans Order Block / pullback"
        sl = "Sous liquidity low"
        tp = "Vers liquidity high"
        confidence = 78 if momentum == "BULLISH" else 65
    elif trend == "DOWN":
        ob_top = int(ch * 0.25)
        ob_bottom = int(ch * 0.40)
        signal = "SELL"
        entry = "Sell sur retour dans Order Block / pullback"
        sl = "Au-dessus liquidity high"
        tp = "Vers liquidity low"
        confidence = 78 if momentum == "BEARISH" else 65
    else:
        ob_top = int(ch * 0.45)
        ob_bottom = int(ch * 0.58)
        signal = "WAIT"
        entry = "Attendre BOS ou CHoCH clair"
        sl = "Non défini"
        tp = "Non défini"
        confidence = 55

    return {
        "img": img,
        "crop": (x1, y1, x2, y2),
        "trend": trend,
        "momentum": momentum,
        "structure": structure,
        "signal": signal,
        "confidence": confidence,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "liquidity_high_y": y1 + liquidity_high_y,
        "liquidity_low_y": y1 + liquidity_low_y,
        "ob_top": y1 + ob_top,
        "ob_bottom": y1 + ob_bottom,
        "chart_x1": x1,
        "chart_x2": x2,
    }


# =========================
# ANNOTATION
# =========================
def annotate_chart(result, output_path):
    img = result["img"].copy()
    draw = ImageDraw.Draw(img)

    x1 = result["chart_x1"]
    x2 = result["chart_x2"]
    high_y = result["liquidity_high_y"]
    low_y = result["liquidity_low_y"]
    ob_top = result["ob_top"]
    ob_bottom = result["ob_bottom"]

    signal = result["signal"]

    # Liquidity lines
    draw.line((x1, high_y, x2, high_y), fill="red", width=4)
    draw.text((x1 + 10, high_y - 25), "Liquidity High / Resistance", fill="red")

    draw.line((x1, low_y, x2, low_y), fill="green", width=4)
    draw.text((x1 + 10, low_y + 5), "Liquidity Low / Support", fill="green")

    # Order Block rectangle
    ob_color = "green" if signal == "BUY" else "red" if signal == "SELL" else "yellow"
    draw.rectangle((x1, ob_top, x2, ob_bottom), outline=ob_color, width=4)
    draw.text((x1 + 10, ob_top + 5), "Order Block zone", fill=ob_color)

    # Signal arrow
    w, h = img.size
    if signal == "BUY":
        draw.polygon(
            [(w * 0.78, h * 0.55), (w * 0.72, h * 0.65), (w * 0.84, h * 0.65)],
            fill="green",
        )
        draw.text((w * 0.70, h * 0.68), "BUY ZONE", fill="green")
    elif signal == "SELL":
        draw.polygon(
            [(w * 0.78, h * 0.65), (w * 0.72, h * 0.55), (w * 0.84, h * 0.55)],
            fill="red",
        )
        draw.text((w * 0.70, h * 0.68), "SELL ZONE", fill="red")
    else:
        draw.text((w * 0.70, h * 0.68), "WAIT", fill="yellow")

    img.save(output_path)


# =========================
# HANDLER
# =========================
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document:
        file = await update.message.document.get_file()
    else:
        return

    input_path = "chart_input.jpg"
    output_path = "chart_v6_annotated.jpg"

    await file.download_to_drive(input_path)
    await update.message.reply_text("📥 Analyse V6 Smart Money en cours...")

    try:
        r = analyze_smc(input_path)
        annotate_chart(r, output_path)

        msg = f"""
📊 RESULTAT V6 SMART MONEY:

Bias / Trend: {r['trend']}
Momentum: {r['momentum']}
Structure: {r['structure']}

Signal: {r['signal']}
Confidence: {r['confidence']}%

Entry:
{r['entry']}

SL:
{r['sl']}

TP:
{r['tp']}

Zones détectées:
- Liquidity High
- Liquidity Low
- Order Block approximatif

Scénario:
- Entrer seulement après confirmation bougie.
- Éviter entrée si le prix est déjà trop proche du TP.
- Attendre retest si breakout fort.

⚠️ Analyse image approximative, pas garantie.
"""
        await update.message.reply_photo(photo=open(output_path, "rb"))
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur V6: {e}")


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

    print("Bot V6 Smart Money lancé 🔥")
    app.run_polling()        bull = 0
        bear = 0

        for x, y, r, g, b in pts:
            if b > r + 20:
                bull += 1
            elif r > b + 20:
                bear += 1

        if bull > bear * 1.2:
            return "BULLISH"
        elif bear > bull * 1.2:
            return "BEARISH"
        return "NEUTRAL"

    left_y = avg_y(left)
    mid_y = avg_y(mid)
    right_y = avg_y(right)

    if right_y < left_y - 10:
        trend = "UP"
    elif right_y > left_y + 10:
        trend = "DOWN"
    else:
        trend = "RANGE"

    if right_y < mid_y - 6:
        momentum = "BULLISH"
    elif right_y > mid_y + 6:
        momentum = "BEARISH"
    else:
        momentum = "NEUTRAL"

    pressure = color_force(last)

    pts_all = dark_points(chart)
    ys = [p[1] for p in pts_all]

    if ys:
        resistance_y = min(ys)
        support_y = max(ys)
    else:
        resistance_y = ch * 0.25
        support_y = ch * 0.75

    price_y = right_y

    price_pos = round((1 - price_y / ch) * 100, 1)
    support_pos = round((1 - support_y / ch) * 100, 1)
    resistance_pos = round((1 - resistance_y / ch) * 100, 1)

    if price_y <= resistance_y + 28:
        zone = "PROCHE RESISTANCE"
    elif price_y >= support_y - 28:
        zone = "PROCHE SUPPORT"
    else:
        zone = "MILIEU"

    breakout = "NO"
    fakeout = "NO"

    if trend == "UP" and price_y <= resistance_y + 20 and pressure == "BULLISH":
        breakout = "BREAKOUT HAUSSIER POSSIBLE"
    elif trend == "DOWN" and price_y >= support_y - 20 and pressure == "BEARISH":
        breakout = "BREAKOUT BAISSIER POSSIBLE"

    if zone == "PROCHE RESISTANCE" and pressure == "BEARISH":
        fakeout = "REJET RESISTANCE POSSIBLE"
    elif zone == "PROCHE SUPPORT" and pressure == "BULLISH":
        fakeout = "REJET SUPPORT POSSIBLE"

    if trend == "UP" and momentum == "BULLISH" and pressure == "BULLISH" and zone != "PROCHE RESISTANCE":
        signal = "BUY"
        confidence = 82
        entry = "Zone BUY actuelle ou après petit pullback"
        sl = "Sous dernier creux / support visuel"
        tp = "Résistance récente"
        comment = "Trend UP + momentum bullish + pression acheteuse."

    elif trend == "DOWN" and momentum == "BEARISH" and pressure == "BEARISH" and zone != "PROCHE SUPPORT":
        signal = "SELL"
        confidence = 82
        entry = "Zone SELL actuelle ou après pullback"
        sl = "Au-dessus dernier sommet / résistance"
        tp = "Support récent"
        comment = "Trend DOWN + momentum bearish + pression vendeuse."

    elif fakeout == "REJET SUPPORT POSSIBLE":
        signal = "BUY"
        confidence = 74
        entry = "BUY si confirmation bougie verte"
        sl = "Sous support"
        tp = "Milieu du range puis résistance"
        comment = "Prix proche support avec rejet possible."

    elif fakeout == "REJET RESISTANCE POSSIBLE":
        signal = "SELL"
        confidence = 74
        entry = "SELL si confirmation bougie rouge"
        sl = "Au-dessus résistance"
        tp = "Milieu du range puis support"
        comment = "Prix proche résistance avec rejet possible."

    elif breakout != "NO":
        signal = "WAIT"
        confidence = 68
        entry = "Attendre clôture claire du breakout"
        sl = "Selon retest"
        tp = "Prochaine zone"
        comment = breakout

    else:
        signal = "WAIT"
        confidence = 58
        entry = "Attendre confirmation"
        sl = "Non défini"
        tp = "Non défini"
        comment = "Pas assez de confluence."

    return {
        "trend": trend,
        "momentum": momentum,
        "pressure": pressure,
        "zone": zone,
        "breakout": breakout,
        "fakeout": fakeout,
        "signal": signal,
        "confidence": confidence,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "price_pos": price_pos,
        "support_pos": support_pos,
        "resistance_pos": resistance_pos,
        "comment": comment,
    }


# =========================
# HANDLE IMAGE
# =========================
async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
    elif update.message.document:
        file = await update.message.document.get_file()
    else:
        return

    path = "chart.png"
    await file.download_to_drive(path)

    await update.message.reply_text("📥 Analyse V4 PRO en cours...")

    try:
        r = analyze_chart_v4(path)

        msg = f"""
📊 RESULTAT V4 PRO:

Trend: {r['trend']}
Momentum: {r['momentum']}
Pression récente: {r['pressure']}
Zone: {r['zone']}

Breakout: {r['breakout']}
Fakeout/Rejet: {r['fakeout']}

Signal: {r['signal']}
Confidence: {r['confidence']}%

Entry: {r['entry']}
SL: {r['sl']}
TP: {r['tp']}

Position prix: {r['price_pos']}%
Support visuel: {r['support_pos']}%
Résistance visuelle: {r['resistance_pos']}%

Commentaire:
{r['comment']}

⚠️ Signal indicatif, pas garantie.
"""
        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur analyse V4: {e}")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("TOKEN tsy hita. Ampidiro ao Render Environment Variables.")

    threading.Thread(target=run_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_all))

    print("Bot V4 PRO lancé 🔥")
    app.run_polling()
