from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, Application
)
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from llama_cpp import Llama
import asyncio
import sqlite3

BOT_TOKEN = "BOT_TOKEN"

# 🔧 Scheduler va baza ulanishi
scheduler = BackgroundScheduler()
scheduler.start()

conn = sqlite3.connect("reminders.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reminder_time TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
)
''')
conn.commit()

llm = Llama(
    model_path="C:/Users/khos/Downloads/mistral.gguf",
    n_ctx=2048,
    n_threads=4
)

# Bu loop ni global saqlaymiz (asosiy asyncio loop)
main_loop = asyncio.get_event_loop()


# Komanda funksiyalari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        # This bot works to send reminders
        "Assalomu alaykum!\nThis bot works to send reminders.\n\n"
        "Commands:\n"
        "/add — add a new reminder\n"
        "/list — reminders list"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏰ Please, enter the time:\n in `YYYY-MM-DD HH:MM` format",
        parse_mode="Markdown"
    )

def nlp(text):
    today = datetime.now()
    rpl = {
        "tomorrow" : (today+timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        "today" : (today).strftime("%Y-%m-%d %H:%M"),
        "ertaga" : (today+timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
        "bugun" : (today).strftime("%Y-%m-%d %H:%M")
    }
    for word, time in rpl.items():
        text.replace(word, time)
    return text

# Reminder yuboruvchi funksiya
async def send_reminder(bot, user_id, message, reminder_id=None):
    await bot.send_message(chat_id=user_id, text=message)
    if reminder_id:
        cursor.execute("UPDATE reminders SET status = 'done' WHERE id = ?", (reminder_id,))
        conn.commit()


# Wrapper: async funksiyani thread-safe usulda chaqirish
def run_async_reminder(bot, user_id, message, reminder_id):
    asyncio.run_coroutine_threadsafe(
        send_reminder(bot, user_id, message, reminder_id),
        main_loop
    )


# Eslatma vaqtini qabul qilish va schedulerga qo‘shish
async def add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id
    text = update.message.text.strip()
    # while True:
    prompt = text
    prompt = nlp(prompt)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    formatted_prompt = f"""### User:
Today's date is {now}. Extract the date time from this following sentence and return it in 'YYYY-MM-DD HH:MM'
Sentence: {prompt} 
output only date and time.don't write excess thing.DO NOT include any extra text, please only date. no need as 'The date time extracted ...' only date.no need anything else
### Assistant:
"""

    output = llm(formatted_prompt, max_tokens=200, stop=["###"])
    # print("🤖 Bot:", output["choices"][0]["text"].strip())
    text = output["choices"][0]["text"].strip()
    if text[0].isdigit() == 0:
        text = text[-17:-1]
    print(text)
    try:
        now = datetime.now()
        rem = datetime.strptime(text, "%Y-%m-%d %H:%M")
        if rem < now:
            await update.message.reply_text("❗ This time already gone!")
            return

        await update.message.reply_text("✅ reminder was saved!")
        cursor.execute("INSERT INTO reminders (user_id, reminder_time) VALUES (?, ?)", (user, text))
        reminder_id = cursor.lastrowid
        conn.commit()

        rem_times = [60, 30, 5, 1]
        for minutes_before in rem_times:
            notify_time = rem - timedelta(minutes=minutes_before)
            if notify_time > now:
                s = f"⏰ {minutes_before} minutes left!"
                scheduler.add_job(
                    run_async_reminder,
                    trigger='date',
                    run_date=notify_time,
                    args=[context.bot, user, s, reminder_id],
                    id=f"job_{reminder_id}_{minutes_before}"
                )

        scheduler.add_job(
            run_async_reminder,
            trigger='date',
            run_date=rem,
            args=[context.bot, user, "⏰ Ring, ring, ring, ring ....", reminder_id],
            id=f"job_{reminder_id}_final"
        )

    except ValueError:
        await update.message.reply_text("❌ Wrong format! please enter in this format `YYYY-MM-DD HH:MM`.")


# Eski eslatmalarni tiklash
def rechedule_all_reminders(scheduler, bot):
    cursor.execute("SELECT id, user_id, reminder_time FROM reminders WHERE status = 'pending'")
    reminders = cursor.fetchall()

    for rem_id, user_id, rem_time in reminders:
        run_time = datetime.strptime(rem_time, "%Y-%m-%d %H:%M")
        now = datetime.now()
        rem_times = [60, 30, 5, 1]

        for minutes_before in rem_times:
            notify_time = run_time - timedelta(minutes=minutes_before)
            if notify_time > now:
                s = f"⏰ {minutes_before} minutes left!"
                scheduler.add_job(
                    run_async_reminder,
                    trigger='date',
                    run_date=notify_time,
                    args=[bot, user_id, s, rem_id],
                    id=f"job_{rem_id}_{minutes_before}"
                )

        if run_time > now:
            scheduler.add_job(
                run_async_reminder,
                trigger='date',
                run_date=run_time,
                args=[bot, user_id, "⏰ Ring, ring, ring, ring ....", rem_id],
                id=f"job_{rem_id}_final"
            )


# Eslatmalar ro‘yxatini ko‘rsatish
async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT id, reminder_time FROM reminders WHERE user_id = ? AND status = 'pending'", (user_id,))
    reminders = cursor.fetchall()

    if not reminders:
        await update.message.reply_text("📭 You have no reminders.")
        return

    for rem_id, rem_time in reminders:
        text = f"🕒 {rem_time} - 📌 Reminder"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{rem_id}")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# Inline tugma orqali eslatmani bekor qilish
async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cancel_"):
        rem_id = int(data.split("_")[1])
        cursor.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
        conn.commit()

        for minutes_before in [60, 30, 5, 1]:
            try:
                scheduler.remove_job(f"job_{rem_id}_{minutes_before}")
            except Exception:
                pass

        try:
            scheduler.remove_job(f"job_{rem_id}_final")
        except Exception:
            pass

        await query.edit_message_text("⛔ Reminder was canceled.")


# 🚀 Botni ishga tushurish
app = ApplicationBuilder().token(BOT_TOKEN).build()

rechedule_all_reminders(scheduler, app.bot)
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("list", list_reminders))
app.add_handler(CallbackQueryHandler(handle_cancel))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_code))

print("✅ Bot is running...")
app.run_polling()
