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
    text = text.strip()
    text = convert_khmer_numbers(text)
    today = datetime.now()

    # ✅ ថ្ងៃនេះ
    if "ថ្ងៃនេះ" in text:
        return today

    # ✅ ស្អែក
    if "ស្អែក" in text:
        return today + timedelta(days=1)

    # ✅ ម្សិលមិញ
    if "ម្សិលមិញ" in text:
        return today - timedelta(days=1)

    # ✅ សប្ដាហ៍ក្រោយ
    if "សប្ដាហ៍ក្រោយ" in text or "សប្តាហ៍ក្រោយ" in text:
        return today + timedelta(days=7)

    # ✅ ខែក្រោយ
    if "ខែក្រោយ" in text:
        month = today.month + 1
        year = today.year
        if month > 12:
            month = 1
            year += 1
        return datetime(year, month, today.day)

    # ✅ X ថ្ងៃក្រោយ (ឧ: 3 ថ្ងៃក្រោយ)
    match_days = re.search(r"(\d+)\s*ថ្ងៃក្រោយ", text)
    if match_days:
        days = int(match_days.group(1))
        return today + timedelta(days=days)

    # ✅ X សប្ដាហ៍ក្រោយ
    match_weeks = re.search(r"(\d+)\s*សប្ដាហ៍ក្រោយ", text)
    if match_weeks:
        weeks = int(match_weeks.group(1))
        return today + timedelta(weeks=weeks)

    # ✅ Format: 15 ខែសីហា 2026
    pattern = r"(\d{1,2})\s*ខែ\s*([^\s]+)\s*(\d{4})"
    match = re.search(pattern, text)

    if match:
        day = int(match.group(1))
        month_name = match.group(2).replace("ខែ", "").strip()
        year = int(match.group(3))

        month = KHMER_MONTHS.get(month_name)

        if month:
            return datetime(year, month, day)

    return None
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
            
            event_str = format_khmer_date(event_date)
            reminder_str = format_khmer_date(reminder_date)
            
            bot.send_message(update.message.chat_id,
                             f""" បានកត់ត្រាជោគជ័យ!
                             📅 ថ្ងៃព្រឹត្តិការណ៍: {event_str}
                             🔔 ថ្ងៃរំលឹក: {reminder_str}
                             """)
        else:
            bot.send_message(update.message.chat_id,
                             "❌ សូមសរសេរថ្ងៃជាទម្រង់: 15 ខែ សីហា 2026")

    return "OK"

@app.route("/")
def home():
    return "Bot is running ✅"

if __name__ == "__main__":
    app.run()