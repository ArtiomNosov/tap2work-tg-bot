from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from datetime import datetime
from collections import defaultdict
from logger import log_action

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, interval_seconds=3, warning_limit=20, block_limit=200, admin_chat_id=None, blacklist=None):
        super().__init__()
        self.interval = interval_seconds
        self.admin_chat_id = admin_chat_id
        self.warning_limit = warning_limit
        self.block_limit = block_limit
        self.user_last_time = {}
        self.user_daily_counts = defaultdict(lambda: {"count": 0, "last_seen": datetime.now()})
        self.blocked_users = set()
        self.blacklist = blacklist or set()

    async def on_pre_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        now = datetime.now()
        log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="on_pre_process_message", message_text=message.text, content_type=str(message.content_type))

        # Блокировка
        if user_id in self.blocked_users:
            log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="User blocked", message_text=message.text, content_type=str(message.content_type))
            raise Exception("User blocked")
        
        if user_id in self.blacklist:
            log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="User is in static blacklist", message_text=message.text, content_type=str(message.content_type))
            raise Exception("User is in static blacklist")

        # Проверка частоты
        last_time = self.user_last_time.get(user_id)
        if last_time and (now - last_time).total_seconds() < self.interval:
            log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="Too frequent", message_text=message.text, content_type=str(message.content_type))
            await message.answer("⛔️ Слишком часто. Попробуй чуть позже.")
            raise Exception("Too frequent")
        self.user_last_time[user_id] = now

        # Подсчёт за сутки
        stats = self.user_daily_counts[user_id]
        if (now - stats["last_seen"]).total_seconds() > 86400:
            stats["count"] = 0

        stats["count"] += 1
        stats["last_seen"] = now

        if stats["count"] == self.warning_limit:
            await message.answer("⚠️ Вы отправили слишком много сообщений за сутки. Возможна блокировка при продолжении.")
            log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="⚠️ Вы отправили слишком много сообщений за сутки. Возможна блокировка при продолжении.", message_text=message.text, content_type=str(message.content_type))
            if self.admin_chat_id:
                await message.bot.send_message(self.admin_chat_id, f"🚨 Пользователь @{message.from_user.username or message.from_user.full_name} достиг лимита {self.warning_limit} сообщений за сутки.")

        elif stats["count"] >= self.block_limit:
            log_action(user_id=user_id, username=message.from_user.username or message.from_user.full_name, action_type="User blocked by limit", message_text=message.text, content_type=str(message.content_type))
            self.blocked_users.add(user_id)
            if self.admin_chat_id:
                await message.bot.send_message(self.admin_chat_id, f"⛔️ Пользователь @{message.from_user.username or message.from_user.full_name} был автоматически заблокирован за спам ({self.block_limit}+ сообщений).")
            raise Exception("User blocked by limit")
