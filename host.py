import telebot
import os
import subprocess
import signal

API_TOKEN = '7480431180:AAHFoJlLsmWh_he6s4f8rv5bm4r1QBncd6I'  # Replace with your hosting bot's token
bot = telebot.TeleBot(API_TOKEN)

UPLOAD_DIR = 'user_bots'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

user_processes = {}  # Track running bots: {user_id: pid}


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message, (
        "👋 Welcome to the Python Bot Hosting Service!\n\n"
        "Commands:\n"
        "📤 Send your .py file to upload\n"
        "/startbot - Start your uploaded bot\n"
        "/stopbot - Stop your running bot\n"
        "/deletebot - Delete your uploaded bot\n"
        "/status - Check bot status\n"
        "/install <package> - Install Python package\n"
    ))


@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    if not message.document.file_name.endswith('.py'):
        return bot.reply_to(message, "❌ Please upload a valid Python `.py` file.")

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    user_id = str(message.from_user.id)
    user_dir = os.path.join(UPLOAD_DIR, user_id)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    file_path = os.path.join(user_dir, 'bot.py')
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    bot.reply_to(message, "✅ Bot file uploaded successfully! Use /startbot to launch it.")


@bot.message_handler(commands=['startbot'])
def start_user_bot(message):
    user_id = str(message.from_user.id)
    if user_id in user_processes:
        return bot.reply_to(message, "⚠️ Your bot is already running!")

    bot_path = os.path.join(UPLOAD_DIR, user_id, 'bot.py')
    if not os.path.exists(bot_path):
        return bot.reply_to(message, "❌ No bot uploaded yet. Please upload a .py file first.")

    try:
        process = subprocess.Popen(['python3', bot_path])
        user_processes[user_id] = process.pid
        bot.reply_to(message, f"🚀 Bot started with PID {process.pid}.")
    except Exception as e:
        bot.reply_to(message, f"❌ Failed to start bot:\n{str(e)}")


@bot.message_handler(commands=['stopbot'])
def stop_user_bot(message):
    user_id = str(message.from_user.id)
    pid = user_processes.get(user_id)
    if not pid:
        return bot.reply_to(message, "⚠️ Your bot is not currently running.")

    try:
        os.kill(pid, signal.SIGTERM)
        del user_processes[user_id]
        bot.reply_to(message, f"🛑 Bot stopped (PID {pid}).")
    except Exception as e:
        bot.reply_to(message, f"❌ Error stopping bot:\n{str(e)}")


@bot.message_handler(commands=['deletebot'])
def delete_user_bot(message):
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
    user_id = str(message.from_user.id)
    if user_id in user_processes:
        bot.reply_to(message, "✅ Your bot is currently running.")
    else:
        bot.reply_to(message, "⛔ Your bot is not running.")


@bot.message_handler(commands=['install'])
def install_package(message):
    user_id = str(message.from_user.id)
    cmd_parts = message.text.split(' ', 1)

    if len(cmd_parts) < 2 or not cmd_parts[1].strip():
        return bot.reply_to(message, "📦 Usage: /install <package_name>\nExample: /install requests")

    package = cmd_parts[1].strip()
    bot.reply_to(message, f"⏳ Installing `{package}`...")

    try:
        result = subprocess.run(
            ['pip3', 'install', package],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            bot.reply_to(message, f"✅ Package `{package}` installed successfully!")
        else:
            bot.reply_to(message, f"❌ Failed to install `{package}`:\n```{result.stderr}```", parse_mode='Markdown')
    except subprocess.TimeoutExpired:
        bot.reply_to(message, "⚠️ Installation timed out.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# Start polling
bot.polling()
