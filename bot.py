# -*- coding: utf-8 -*-
"""Telegram bot for friends betting — 10000 rubles each, track bets, rates and sums."""
import os
import re
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# Load .env if python-dotenv is present (optional)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import storage


def get_token():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN in .env or environment (get token from @BotFather)")
    return token


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    u = storage.get_user(chat_id, user.id, user.username or "")
    balance = u["balance"]
    await update.message.reply_text(
        "Здорова, лудик. Сейчас попробуем сохранить твои бабки, но оставить интерес. Погнали...\n\n"
        f"Привет, {user.first_name or 'друг'}!\n\n"
        f"У тебя на счёте {balance:,} ₽. Можно делать ставки.\n\n"
        "Команды:\n"
        "/balance — баланс\n"
        "/bet описание | коэффициент | сумма — сделать ставку\n"
        "/bets — мои ставки (кнопки «Сыграло» / «Не сыграло»)\n"
        "/active — все нерассчитанные ставки в чате\n"
        "/top — таблица по балансам\n"
        "/results — подвести итоги и сбросить балансы до 10 000 ₽\n"
        "/help — полное руководство по боту"
    )


HELP_TEXT = """📖 Руководство по боту «Ставки с друзьями»

У каждого участника на счёте 10 000 ₽. Делайте ставки, указывайте коэффициент и сумму — всё сохраняется в боте.

━━━━━━━━━━━━━━━━━━━━
📌 КОМАНДЫ
━━━━━━━━━━━━━━━━━━━━

/start — регистрация и стартовый баланс 10 000 ₽

/balance — показать текущий баланс

/bet описание | коэффициент | сумма — сделать ставку
Пример: /bet Победа Спартака | 2.0 | 500

/bets — список своих ставок. У активных ставок есть кнопки «✅ Сыграло» и «❌ Не сыграло» — нажмите, чтобы закрыть ставку.

/active — показать все нерассчитанные ставки в чате (кто поставил, на что, коэффициент и сумма)

/top — таблица участников по балансу

/results — подвести итоги раунда (показать результаты), затем по запросу обнулить балансы — у всех снова по 10 000 ₽. Сначала появится вопрос «Обнулить балансы?» с кнопками Да/Нет.

/help — это руководство

━━━━━━━━━━━━━━━━━━━━
📌 КАК СДЕЛАТЬ СТАВКУ
━━━━━━━━━━━━━━━━━━━━

• Описание — на что ставите (например: «Победа команды А»).
• Коэффициент — число больше 1 (например 2.0: при выигрыше получите сумму × 2).
• Сумма — сколько рублей ставите (списывается с баланса).

После исхода события отметьте результат: нажмите «✅ Сыграло» или «❌ Не сыграло» в списке /bets.

Если баланс закончился — новые ставки недоступны, пока не выиграете по одной из активных или не будет выполнен /results (новый раунд)."""


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    balance = storage.get_balance(chat_id, user_id)
    await update.message.reply_text(f"Твой баланс: {balance:,} ₽")


async def cmd_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    # /bet description | rate | sum
    parts = re.split(r"\s*\|\s*", text.replace("/bet", "").strip(), maxsplit=2)
    if len(parts) != 3:
        await update.message.reply_text(
            "Формат: /bet описание | коэффициент | сумма\n"
            "Пример: /bet Победа Спартака | 2.0 | 500"
        )
        return
    desc, rate_str, sum_str = (p.strip() for p in parts)
    if not desc:
        await update.message.reply_text("Укажи описание ставки.")
        return
    try:
        rate = float(rate_str.replace(",", "."))
        if rate < 1.01:
            await update.message.reply_text("Коэффициент должен быть больше 1 (например 2.0).")
            return
    except ValueError:
        await update.message.reply_text("Коэффициент — число (например 2.0 или 1.5).")
        return
    try:
        sum_rub = int(sum_str.replace(" ", ""))
        if sum_rub < 1:
            await update.message.reply_text("Сумма должна быть больше 0.")
            return
    except ValueError:
        await update.message.reply_text("Сумма — целое число рублей.")
        return

    bet = storage.create_bet(chat_id, user_id, desc, rate, sum_rub)
    if bet is None:
        balance = storage.get_balance(chat_id, user_id)
        await update.message.reply_text(
            f"Недостаточно средств. Твой баланс: {balance:,} ₽"
        )
        return
    potential = int(bet["sum"] * bet["rate"])
    await update.message.reply_text(
        f"Ставка принята.\n"
        f"Описание: {bet['description']}\n"
        f"Коэффициент: {bet['rate']}\n"
        f"Сумма: {bet['sum']:,} ₽\n"
        f"Потенциальный выигрыш: {potential:,} ₽\n"
        f"Баланс после ставки: {storage.get_balance(chat_id, user_id):,} ₽"
    )


def _format_bets_message(chat_id: int, user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    """Формирует текст списка ставок и клавиатуру для активных (до 15 шт.)."""
    bets = storage.get_user_bets(chat_id, user_id)[:20]
    lines = []
    keyboard_rows = []
    for b in bets:
        status_emoji = {"active": "⏳", "won": "✅", "lost": "❌"}.get(b.get("status"), "?")
        potential = int(b["sum"] * b["rate"])
        lines.append(
            f"{status_emoji} #{b['id']} {b['description']} | кф. {b['rate']} | {b['sum']:,} ₽ (выигрыш {potential:,} ₽)"
        )
        if b.get("status") == "active" and len(keyboard_rows) < 15:
            keyboard_rows.append([
                InlineKeyboardButton("✅ Сыграло", callback_data=f"settle_{b['id']}_win"),
                InlineKeyboardButton("❌ Не сыграло", callback_data=f"settle_{b['id']}_lost"),
            ])
    text = "Твои ставки:\n\n" + "\n".join(lines)
    keyboard = InlineKeyboardMarkup(keyboard_rows) if keyboard_rows else None
    return text, keyboard


async def cmd_bets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    bets = storage.get_user_bets(chat_id, user_id)
    if not bets:
        await update.message.reply_text("У тебя пока нет ставок.")
        return
    text, keyboard = _format_bets_message(chat_id, user_id)
    await update.message.reply_text(text, reply_markup=keyboard)


async def cmd_active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать все нерассчитанные (активные) ставки в чате."""
    chat_id = update.effective_chat.id
    active_bets = storage.get_all_active_bets(chat_id)
    if not active_bets:
        await update.message.reply_text("Нет нерассчитанных ставок. Все ставки закрыты.")
        return
    lines = ["⏳ Нерассчитанные ставки:\n"]
    for b in active_bets[:30]:  # Ограничение до 30 ставок
        author = f"@{b['username']}" if b.get("username") else f"ID{b['user_id']}"
        potential = int(b["sum"] * b["rate"])
        lines.append(
            f"#{b['id']} | {author}\n"
            f"   {b['description']}\n"
            f"   Коэффициент: {b['rate']} | Сумма: {b['sum']:,} ₽ | Выигрыш: {potential:,} ₽\n"
        )
    await update.message.reply_text("\n".join(lines))


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    users = storage.get_all_users_balances(chat_id)
    if not users:
        await update.message.reply_text("Пока никого нет.")
        return
    users.sort(key=lambda x: x["balance"], reverse=True)
    lines = []
    for i, u in enumerate(users[:15], 1):
        name = f"@{u['username']}" if u["username"] else f"ID{u['user_id']}"
        lines.append(f"{i}. {name} — {u['balance']:,} ₽")
    await update.message.reply_text("Балансы:\n\n" + "\n".join(lines))


async def cmd_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подвести итоги и спросить подтверждение перед обнулением балансов."""
    chat_id = update.effective_chat.id
    users = storage.get_all_users_balances(chat_id)
    if not users:
        await update.message.reply_text("Нет участников. Итоги подводить нечего.")
        return
    users.sort(key=lambda x: x["balance"], reverse=True)
    lines = ["📊 Итоги раунда:\n"]
    for i, u in enumerate(users, 1):
        name = f"@{u['username']}" if u["username"] else f"ID{u['user_id']}"
        lines.append(f"{i}. {name} — {u['balance']:,} ₽")
    lines.append("\nОбнулить балансы?")
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Да", callback_data=f"results_yes_{chat_id}"),
            InlineKeyboardButton("Нет", callback_data=f"results_no_{chat_id}"),
        ]
    ])
    await update.message.reply_text("\n".join(lines), reply_markup=keyboard)


async def results_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка нажатия кнопки подтверждения обнуления балансов."""
    query = update.callback_query
    await query.answer()
    # callback_data: results_yes_<chat_id> или results_no_<chat_id>
    parts = query.data.split("_")
    if len(parts) < 3:
        await query.answer("Ошибка данных.", show_alert=True)
        return
    chat_id = int(parts[2])
    if query.data.startswith("results_no"):
        await query.edit_message_text(
            query.message.text + "\n\n❌ Отменено."
        )
        return
    if query.data.startswith("results_yes"):
        count = storage.reset_all_balances_to_initial(chat_id)
        await query.edit_message_text(
            query.message.text + f"\n\n✅ Балансы сброшены. У всех {count} участников снова по 10 000 ₽. Новый раунд!"
        )


async def settle_bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Быстро закрыть ставку: Сыграло / Не сыграло из списка /bets."""
    query = update.callback_query
    user_id = query.from_user.id if query.from_user else 0
    chat_id = query.message.chat.id if query.message else 0
    # callback_data: settle_<bet_id>_win или settle_<bet_id>_lost
    parts = query.data.split("_")
    if len(parts) != 3:
        await query.answer("Ошибка данных.", show_alert=True)
        return
    try:
        bet_id = int(parts[1])
    except ValueError:
        await query.answer("Неверный номер ставки.", show_alert=True)
        return
    won = parts[2] == "win"
    bet = storage.get_bet(chat_id, bet_id)
    if not bet:
        await query.answer("Ставка не найдена.", show_alert=True)
        return
    if bet["user_id"] != user_id:
        await query.answer("Можно закрывать только свои ставки.", show_alert=True)
        return
    if bet.get("status") != "active":
        await query.answer("Эта ставка уже закрыта.", show_alert=True)
        return
    username = (query.from_user.username or "") if query.from_user else ""
    storage.settle_bet(chat_id, bet_id, won, settled_by_user_id=user_id, settled_by_username=username)
    payout = int(bet["sum"] * bet["rate"]) if won else 0
    new_balance = storage.get_balance(chat_id, user_id)
    if won:
        await query.answer(f"Ставка #{bet_id} сыграла! +{payout:,} ₽. Баланс: {new_balance:,} ₽")
    else:
        await query.answer(f"Ставка #{bet_id} не сыграла. Баланс: {new_balance:,} ₽")
    text, keyboard = _format_bets_message(chat_id, user_id)
    await query.edit_message_text(text, reply_markup=keyboard)


def main() -> None:
    token = get_token()
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("bet", cmd_bet))
    app.add_handler(CommandHandler("bets", cmd_bets))
    app.add_handler(CommandHandler("active", cmd_active))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("results", cmd_results))
    app.add_handler(CallbackQueryHandler(results_confirm_callback, pattern="^results_(yes|no)_-?\\d+$"))
    app.add_handler(CallbackQueryHandler(settle_bet_callback, pattern="^settle_\\d+_(win|lost)$"))
    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
