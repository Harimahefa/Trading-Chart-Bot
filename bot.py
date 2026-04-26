from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image

TOKEN = "8225959243:AAFPByF33ZXIH69oekdqmcKudU8EDft5gJc"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Chart Vision Bot V4 PRO Ready 🔥\nAlefaso screenshot chart!")

def analyze_chart_v4(image_path):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    chart = img.crop((int(w*0.05), int(h*0.13), int(w*0.90), int(h*0.68)))
    cw, ch = chart.size

    left = chart.crop((0, 0, int(cw*0.30), ch))
    mid = chart.crop((int(cw*0.35), 0, int(cw*0.65), ch))
    right = chart.crop((int(cw*0.70), 0, cw, ch))
    last = chart.crop((int(cw*0.85), 0, cw, ch))

    def dark_points(part):
        pts = []
        for y in range(part.size[1]):
            for x in range(part.size[0]):
                r, g, b = part.getpixel((x, y))
                if r < 210 or g < 210 or b < 210:
                    pts.append((x, y, r, g, b))
        return pts

    def avg_y(part):
        pts = dark_points(part)
        if not pts:
            return part.size[1] / 2
        return sum(p[1] for p in pts) / len(pts)

    def color_force(part):
        pts = dark_points(part)
        bull = 0
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
        "comment": comment
    }

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

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_all))

    print("Bot V4 PRO lancé 🔥")
    app.run_polling()
