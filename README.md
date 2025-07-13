# reminder-bot

# author : khos_019

# About My project
This project is a Telegram bot built with Python. The bot is integrated with LLaMA.

If you send the bot a message saying that you want to do something at a certain time and ask it to remind you, it will send you a reminder about that task.

It is recommended to use the bot primarily in English. Additionally, when adding a reminder, including the exact time will help the bot work more accurately.

# Use
This bot has two main commands. The /add command only requires you to enter the time. However, even if you don’t use the /add command, the bot can still understand what you need from natural language.

For example: “Remind me at 10 a.m. tomorrow”.

The /list command displays the list of reminders you’ve added to the bot, and you can delete the ones you no longer need from there.

# Install
``` bash
git clone https://github.com/khos019/project.git
cd project
pip install -r requirements.txt
python main.py
