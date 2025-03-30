import asyncio
import re
import sys
from asyncio import Queue, create_task
from pathlib import Path

from loguru import logger
from telegram import Bot
from telegram.request import HTTPXRequest

from src.config import LogsConfig

tasks = set()


class TelegramLoggerHandler:
    ERROR_MSG = "Не могу отправить лог в телеграм"

    def __init__(self, token: str, chat_id: int):
        self.token = token
        self.chat_id = int(chat_id)

        self.bot = Bot(token, request=HTTPXRequest(connection_pool_size=10**10))

        self.queue = Queue()

        self.log_types_emoji = {"INFO": "🟢", "ERROR": "🔴", "WARNING": "🟠"}

    async def send_message(self, message):
        await self.bot.send_message(chat_id=self.chat_id, text=message)

    async def sender_task(self):
        while True:
            try:
                message = await self.queue.get()
                await self.send_message(message)
            except Exception as e:
                logger.debug(f"{self.ERROR_MSG}: {e}")
            await asyncio.sleep(3)

    def write(self, message):
        if self.ERROR_MSG not in message:
            message = self.prepare_message(message)
            self.queue.put_nowait(message)

    def prepare_message(self, message):
        message = self.add_emojies(message)
        message = self.remove_colors_from_message(message)
        message = self.split_to_lines(message)
        return message

    @staticmethod
    def remove_colors_from_message(message: str) -> str:
        return re.sub(r"\x1b\[\d+m", "", message)

    @staticmethod
    def split_to_lines(message: str) -> str:
        return message.replace(" | ", "\n")

    def add_emojies(self, message) -> str:
        level_name = message.record["level"].name
        emoji = self.log_types_emoji.get(level_name)
        if emoji:
            message = emoji + " " + message

        return message


async def setup_logging(config: LogsConfig):
    file_path = Path(config.file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
        "| <level>{level: <8}</level> "
        "| <level>{message}</level>"
    )
    logger.add(sys.stdout, level=config.level, format=formatter)
    logger.add(file_path, level=config.level, format=formatter)
    logger.remove(0)

    if config.telegram.enabled:
        telegram_logger_handler = TelegramLoggerHandler(
            config.telegram.token, config.telegram.chat_id
        )
        logger.add(telegram_logger_handler)
        task = create_task(telegram_logger_handler.sender_task())
        tasks.add(task)