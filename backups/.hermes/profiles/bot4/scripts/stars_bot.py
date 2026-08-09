"""
Telegram Stars bot — sells digital goods worth real TON to customers.

Reference: https://core.telegram.org/api/stars + https://core.telegram.org/bots/payments
One-time setup (Jack, ~2 minutes):
  1. Telegram → DM @BotFather → /newbot → name: "Kachang Sia Tools" (or any)
  2. Copy the token (format: 1234567890:AA...) and paste it as STARS_BOT_TOKEN
  3. Provide TON wallet address as STARS_PAYOUT_WALLET (Fragment withdrawal target)
  4. Run this script: `python3 stars_bot.py &`

What this bot sells:
  - Prompt packs at 50 Stars (~$0.50)  → Gumroad product `50-viral-tiktok-hooks`
  - Full launchpad at 250 Stars (~$2.50) → Gumroad product `ai-solopreneur-launchpad`
  - One-on-one consult at 1000 Stars (~$10) → Discord/email follow-up

How it works:
  - Customer hits /start → main menu shows products
  - Customer taps "Buy 50 Stars pack" → bot calls sendInvoice(currency="XTR")
  - Customer pays via Telegram (Stars → real money via Apple/Google IAP or Fragment)
  - Bot receives pre_checkout_query → answers OK
  - Bot receives successful_payment → delivers the Gumroad link (or triggers fulfillment)
  - Bot owner withdraws via Fragment → TON → list on exchanges → USD

Payout flow:
  - Call `getStarsRevenueWithdrawalUrl` → Fragment URL → Jack clicks → TON to wallet
  - Or programmatically: `getStarsBalance` shows accumulated Stars
  - TON/USD rate: ~$1.395 (live per Aug 2026 research)

Revenue potential:
  - 1 unit/day = $0.50–$10/day = $15–$300/mo (small audience)
  - 10 units/day = $150–$3000/mo (modest audience with channel cross-promotion)
  - 100% headless after the 1-time BotFather step
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

import requests
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("stars_bot")

BOT_TOKEN = os.environ.get("STARS_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise SystemExit(
        "STARS_BOT_TOKEN not set. See top-of-file comment for the 1-time BotFather setup."
    )

# 1 Star ≈ $0.015 (Aug 2026 — Telegram sets rate; can be read via getMyStarBalance usd_rate)
PRODUCTS = {
    "hook_pack_50": {
        "title": "50 Viral TikTok Hooks — AI Prompt Pack",
        "description": (
            "50 tested-and-iterated TikTok hook templates that get scrollers to stop. "
            "Plug-and-play for faceless AI video. Delivered as a downloadable PDF."
        ),
        "stars": 50,  # ~$0.50–$0.75
        "delivery_url": "https://jackalope86.gumroad.com/l/50-viral-tiktok-hooks",
    },
    "launchpad_250": {
        "title": "AI Solopreneur Launchpad — 50+ Prompts",
        "description": (
            "The full prompt library used by Singapore AI studios to ship products solo. "
            "Pricing, copy, code, growth. Delivered as a downloadable ZIP."
        ),
        "stars": 250,  # ~$2.50–$3.75
        "delivery_url": "https://jackalope86.gumroad.com/l/ai-solopreneur-launchpad",
    },
    "consult_1000": {
        "title": "1-on-1 AI Automation Consult (30 min)",
        "description": (
            "30 minutes with Jack Loh — Singapore AI automation studio, running x402 / Base / "
            "Telegram agent infrastructure. Bring your hardest automation problem. Delivered via "
            "Google Meet at the time you book."
        ),
        "stars": 1000,  # ~$15
        "delivery_url": "https://cal.com/kachangsia/30min",  # replace with real booking link
    },
}


WELCOME_TEXT = (
    "👋 Welcome to Kachang Sia Tools.\n\n"
    "I sell AI automation products and services. Pay with Telegram Stars (real money — "
    "Apple/Google IAP or @PremiumBot) and get instant delivery.\n\n"
    "Pick a product:"
)


def build_main_menu():
    keyboard = [
        [InlineKeyboardButton(
            f"{p['title']} — {p['stars']}⭐",
            callback_data=f"buy:{key}",
        )]
        for key, p in PRODUCTS.items()
    ]
    return InlineKeyboardMarkup(keyboard)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, reply_markup=build_main_menu())


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show seller accumulated Stars (admin-only)."""
    user_id = update.effective_user.id
    # Replace with actual admin user IDs from .env
    admin_ids = [int(x) for x in os.environ.get("STARS_ADMIN_IDS", "").split(",") if x]
    if user_id not in admin_ids:
        await update.message.reply_text("Not authorized.")
        return
    info = await context.bot.get_my_star_balance()
    usd = info.amount * 0.015  # Aug 2026 estimate
    await update.message.reply_text(
        f"⭐ Balance: {info.amount} Stars (≈ ${usd:.2f} USD)\n"
        f"Withdraw via Fragment when ≥ 1000 Stars."
    )


async def on_buy_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Customer taps a product button → send invoice in XTR."""
    query = update.callback_query
    await query.answer()
    product_key = query.data.split(":", 1)[1]
    product = PRODUCTS.get(product_key)
    if not product:
        await query.edit_message_text("Product not found.")
        return

    # Critical: currency="XTR" (Telegram Stars), provider_token="" (empty for Stars)
    # Per https://core.telegram.org/bots/payments — sendInvoice for Stars
    prices = [LabeledPrice(label=product["title"], amount=product["stars"])]
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=product["title"],
        description=product["description"],
        payload=product_key,  # echoed back in successful_payment
        provider_token="",  # empty for Stars
        currency="XTR",
        prices=prices,
    )


async def on_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve checkout before customer is charged."""
    query = update.pre_checkout_query
    if query.invoice_payload not in PRODUCTS:
        await query.answer(ok=False, error_message="Unknown product.")
        return
    await query.answer(ok=True)


async def on_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Customer paid. Deliver the product."""
    sp = update.message.successful_payment
    product = PRODUCTS.get(sp.invoice_payload)
    if not product:
        logger.error("Successful payment for unknown payload: %s", sp.invoice_payload)
        return
    logger.info(
        "PAYMENT: %s paid %s Stars for %s (txn: %s)",
        update.effective_user.id,
        sp.total_amount,
        product["title"],
        sp.telegram_payment_charge_id,
    )

    # TODO: log to accounting file for Jack's records
    # Path("stars_ledger.jsonl").open("a").write(json.dumps({...}) + "\n")

    delivery_text = (
        f"✅ Payment received ({sp.total_amount}⭐). Thanks!\n\n"
        f"Your product: *{product['title']}*\n\n"
        f"📦 Delivery link: {product['delivery_url']}\n\n"
        f"Questions? Reply here or email sales@kachangsia.com."
    )
    await update.message.reply_text(delivery_text, parse_mode="Markdown")


def main():
    if not BOT_TOKEN:
        raise SystemExit("Set STARS_BOT_TOKEN env var first.")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CallbackQueryHandler(on_buy_click, pattern=r"^buy:"))
    app.add_handler(PreCheckoutQueryHandler(on_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, on_successful_payment))
    logger.info("Stars bot online. Products: %s", list(PRODUCTS.keys()))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    from telegram.ext import MessageHandler, filters
    main()
