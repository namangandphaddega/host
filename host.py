import telebot
import os
import subprocess
import signal
import json
import re
from datetime import datetime, timedelta

API_TOKEN = '7574721300:AAGURzPCChSO0I4vmvjQCrw7R_4zLni8LLk'  # Replace with your bot token
bot = telebot.TeleBot(API_TOKEN)

UPLOAD_DIR = 'user_bots'
AUTH_FILE = 'authorized_users.json'

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

if not os.path.exists(AUTH_FILE):
    with open(AUTH_FILE, 'w') as f:
        json.dump({"admins": ["6353114118"], "users": {}}, f)  # Replace with your Telegram user ID

user_processes = {}  # {user_id: pid}


# ==== AUTH SYSTEM ====

def load_auth_data():
    with open(AUTH_FILE, 'r') as f:
        return json.load(f)


def save_auth_data(data):
    with open(AUTH_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def is_admin(user_id):
    auth = load_auth_data()
    return str(user_id) in auth['admins']


def is_authorized(user_id):
    auth = load_auth_data()
    uid = str(user_id)
    if uid in auth['admins']:
        return True
    if uid in auth['users']:
        expiry = datetime.strptime(auth['users'][uid], '%Y-%m-%d')
        return datetime.now() <= expiry
    return False


# ==== UTILITY: Dependency Scanner ====

def scan_dependencies(code):
    imports = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', code, re.M)
    unique_imports = sorted(set(imports))
    return unique_imports


# ==== COMMAND HANDLERS ====

@bot.message_handler(commands=['start'])
def handle_start(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized to use this bot.")
    bot.reply_to(message, (
        "👋 Welcome to the Python Bot Hosting Service!\n\n"
        "Commands:\n"
        "📤 Upload your `.py` file\n"
        "/startbot - Start your bot\n"
        "/stopbot - Stop your bot\n"
        "/deletebot - Delete bot file\n"
        "/status - Bot running status\n"
        "/install <package> - Install dependency\n"
    ))


@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized to use this bot.")
    if not message.document.file_name.endswith('.py'):
        return bot.reply_to(message, "❌ Upload a valid `.py` file.")

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    user_id = str(message.from_user.id)
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_dir, exist_ok=True)

    file_path = os.path.join(user_dir, 'bot.py')
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    with open(file_path, 'r') as f:
        code = f.read()
    deps = scan_dependencies(code)

    bot.reply_to(message, f"✅ Bot uploaded!\n📦 Detected packages:\n" + "\n".join(f"• `{d}`" for d in deps), parse_mode='Markdown')


@bot.message_handler(commands=['startbot'])
def start_user_bot(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized.")
    user_id = str(message.from_user.id)
    if user_id in user_processes:
        return bot.reply_to(message, "⚠️ Bot already running.")

    bot_path = os.path.join(UPLOAD_DIR, user_id, 'bot.py')
    if not os.path.exists(bot_path):
        return bot.reply_to(message, "❌ Upload your bot first.")

    try:
        process = subprocess.Popen(['python3', bot_path])
        user_processes[user_id] = process.pid
        bot.reply_to(message, f"🚀 Bot started with PID {process.pid}.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error starting bot:\n{str(e)}")


@bot.message_handler(commands=['stopbot'])
def stop_user_bot(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized.")
    user_id = str(message.from_user.id)
    pid = user_processes.get(user_id)
    if not pid:
        return bot.reply_to(message, "⚠️ No bot running.")
    try:
        os.kill(pid, signal.SIGTERM)
        del user_processes[user_id]
        bot.reply_to(message, f"🛑 Bot stopped (PID {pid}).")
    except Exception as e:
        bot.reply_to(message, f"❌ Error stopping bot:\n{str(e)}")


@bot.message_handler(commands=['deletebot'])
def delete_user_bot(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized.")
    user_id = str(message.from_user.id)
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    pid = user_processes.get(user_id)

    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            del user_processes[user_id]
        except Exception:
            pass

    if os.path.exists(user_dir):
        for file in os.listdir(user_dir):
            os.remove(os.path.join(user_dir, file))
        os.rmdir(user_dir)

    bot.reply_to(message, "🗑️ Bot deleted successfully.")


@bot.message_handler(commands=['status'])
def bot_status(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized.")
    user_id = str(message.from_user.id)
    if user_id in user_processes:
        bot.reply_to(message, "✅ Your bot is running.")
    else:
        bot.reply_to(message, "⛔ Your bot is not running.")


@bot.message_handler(commands=['install'])
def install_package(message):
    if not is_authorized(message.from_user.id):
        return bot.reply_to(message, "🚫 You are not authorized.")
    cmd_parts = message.text.split(' ', 1)

    if len(cmd_parts) < 2:
        return bot.reply_to(message, "📦 Usage: /install <package_name>")

    package = cmd_parts[1].strip()
    bot.reply_to(message, f"⏳ Installing `{package}`...")

    try:
        result = subprocess.run(['pip3', 'install', package], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            bot.reply_to(message, f"✅ `{package}` installed.", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Install failed:\n```{result.stderr}```", parse_mode='Markdown')
    except subprocess.TimeoutExpired:
        bot.reply_to(message, "⚠️ Install timed out.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# ==== ADMIN COMMANDS ====

@bot.message_handler(commands=['add'])
def add_user(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ You are not an admin.")
    parts = message.text.split()
    if len(parts) != 3:
        return bot.reply_to(message, "📥 Usage: /add <user_id> <days>")
    user_id, days = parts[1], parts[2]
    try:
        days = int(days)
        expiry = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        auth = load_auth_data()
        auth['users'][user_id] = expiry
        save_auth_data(auth)
        bot.reply_to(message, f"✅ User {user_id} authorized until {expiry}")
    except ValueError:
        bot.reply_to(message, "❌ Invalid input. Days must be a number.")


@bot.message_handler(commands=['remove'])
def remove_user(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ You are not an admin.")
    parts = message.text.split()
    if len(parts) != 2:
        return bot.reply_to(message, "🗑 Usage: /remove <user_id>")
    user_id = parts[1]
    auth = load_auth_data()
    if user_id in auth['users']:
        del auth['users'][user_id]
        save_auth_data(auth)
        bot.reply_to(message, f"✅ User {user_id} removed.")
    else:
        bot.reply_to(message, f"⚠️ User {user_id} not found.")

@bot.message_handler(commands=['log'])
def send_all_py_files(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "❌ You are not an admin.")
    
    count = 0
    for user_folder in os.listdir(UPLOAD_DIR):
        user_path = os.path.join(UPLOAD_DIR, user_folder)
        if os.path.isdir(user_path):
            for file in os.listdir(user_path):
                if file.endswith('.py'):
                    filepath = os.path.join(user_path, file)
                    try:
                        with open(filepath, 'rb') as f:
                            bot.send_document(message.chat.id, f, caption=f"📦 From user `{user_folder}`", parse_mode='Markdown')
                            count += 1
                    except Exception as e:
                        bot.send_message(message.chat.id, f"❌ Failed to send `{file}` from user `{user_folder}`: {e}")
    
    if count == 0:
        bot.reply_to(message, "📭 No .py files found.")


# Start polling
bot.polling()
