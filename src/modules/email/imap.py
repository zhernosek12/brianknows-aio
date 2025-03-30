import email
import ssl
import certifi
from email.header import decode_header
from email.message import Message
from typing import Optional, Tuple
from loguru import logger
from aioimaplib import aioimaplib

from .base import BaseClient


class IMAPClient(BaseClient):

    def __init__(self, email_username: str, email_password: str):
        super().__init__('IMAP')
        self.email_username = email_username
        self.email_password = email_password
        self.imap: aioimaplib.IMAP4_SSL | None = None
        self.imap_servers = {
            'outlook.com': 'imap-mail.outlook.com',
            'hotmail.com': 'imap-mail.outlook.com',
            'rambler.ru': 'imap.rambler.ru',
            'mail.ru': 'imap.mail.ru',
            'gmail.com': 'imap.gmail.com',
        }
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())


    async def close(self):
        if self.imap:
            try:
                await self.imap.close()
            except Exception as e:
                logger.warning(f'Failed to close IMAP client: {str(e)}')

    def username(self) -> str:
        return self.email_username

    async def _login(self):
        email_domain = self.email_username.split('@')[1]
        imap_server = self.imap_servers[email_domain]
        self.imap = aioimaplib.IMAP4_SSL(imap_server, ssl_context=self.ssl_context)  #
        await self.imap.wait_hello_from_server()
        res = await self.imap.login(self.email_username, self.email_password)
        #print("RESULT", res.result, res.lines)
        await self.imap.select()

    async def _find_email(self, folder: str, subject_condition_func) -> Tuple[Optional[str], Optional[str]]:
        _, messages = await self.imap.select(folder)
        msg_cnt = 0
        for message in messages:
            if message.endswith(b'EXISTS'):
                msg_cnt = int(message.split()[0])
                break
        for i in range(msg_cnt, 0, -1):
            res, msg = await self.imap.fetch(str(i), '(RFC822)')
            if res != 'OK':
                continue
            raw_email = msg[1]
            msg = email.message_from_bytes(raw_email)
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else 'utf-8')
            if subject_condition_func(subject):
                return subject, self.get_email_body(msg)
        return None, None

    def get_email_body(self, msg: Message):
        if msg.is_multipart():
            return self.get_email_body(msg.get_payload(0))
        return msg.get_payload(decode=True).decode()
