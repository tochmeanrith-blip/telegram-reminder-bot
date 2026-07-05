import os
import json
from datetime import datetime, timedelta
from flask import Flask, request
import telegram
import gspread
from google.oauth2.service_account import Credentials
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import re

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = "ReminderSheet"
TIMEZONE = "Asia/Phnom_Penh"

# ===== TELEGRAM =====
bot = telegram.Bot(token=BOT_TOKEN)

# ===== GOOGLE AUTH =====
creds_dict = json.loads(os.environ["GOOGLE_CREDS_JSON"])

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ===== SCHEDULER =====
scheduler = BackgroundScheduler(timezone=TIMEZONE)
scheduler.start()

def schedule_reminder(chat_id, message, run_date):
    scheduler.add_job(
        lambda: bot.send_message(chat_id, f"🔔 រំលឹក: {message}"),
        trigger='date',
        run_date=run_date
    )

# ===== KHMER DATE PARSER =====
KHMER_MONTHS = {
    "មករា": 1, "កុម្ភៈ": 2, "មីនា": 3, "មេសា": 4,
    "ឧសភា": 5, "មិថុនា": 6, "កក្កដា": 7, "សីហា": 8,
    "កញ្ញា": 9, "តុលា": 10, "វិច្ឆិកា": 11, "ធ្នូ": 12
}
# ===== Convert Khmer numbers to Arabic =====

KHMER_DIGITS = {
    "០": "0", "១": "1", "២": "2", "៣": "3", "៤": "4",
    "៥": "5", "៦": "6", "៧": "7", "៨": "8", "៩": "9"
}

def convert_khmer_numbers(text):
    for kh, ar in KHMER_DIGITS.items():
        text = text.replace(kh, ar)
    return text

def parse_khmer_date(text):
    pattern = r"(\d{1,2})\s*ខែ\s*([^\s]+)\s*(\d{4})"
    match = re.search(pattern, text)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).strip()
        year = int(match.group(3))

        month = KHMER_MONTHS.get(month_name)

        if month:
            return datetime(year, month, day)
    return None

# ===== FLASK APP =====
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    if update.message and update.message.text:
        text = update.message.text
        event_date = parse_khmer_date(text)

        if event_date:
            reminder_date = event_date - timedelta(days=7)

            sheet.append_row([
                text,
                event_date.strftime("%Y-%m-%d"),
                reminder_date.strftime("%Y-%m-%d"),
                update.message.chat_id
            ])

            schedule_reminder(update.message.chat_id, text, reminder_date)

            bot.send_message(update.message.chat_id,
                             "✅ បានកត់ត្រា និងកំណត់រំលឹករួច!")
        else:
            bot.send_message(update.message.chat_id,
                             "❌ សូមសរសេរថ្ងៃជាទម្រង់: 15 ខែ សីហា 2026")

    return "OK"

@app.route("/")
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    app.run()