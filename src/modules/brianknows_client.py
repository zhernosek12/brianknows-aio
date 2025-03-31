import random
import json

from loguru import logger
from eth_account import Account
from eth_account.messages import encode_defunct
from datetime import datetime
from decimal import Decimal
from web3 import Web3
from eth_utils import to_hex

from src.utils.progress_bar import wait
from src.modules.exceptions import InsufficientFunds


class BrianknowsClient:
    def __init__(self, browser_client, transaction_executors, address, proxy):
        self.browser_client = browser_client
        self.transaction_executors = transaction_executors
        self.address = address
        self.proxy = proxy
        self.useragent = browser_client.user_agent

        self.headers = {
            'User-Agent': self.useragent,
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, zstd',
            'Origin': 'https://www.brianknows.org',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0'
        }

        self.wait_before_send_transaction = [3, 11]
        self.max_retry = 3

    async def get_nonce(self):
        response_data = await self.browser_client.request(
            url="https://www.brianknows.org/api/auth/nonce",
            method="GET",
            headers=self.headers,
            proxy=self.proxy
        )
        if response_data['response'].status == 200:
            return response_data['data']

    def get_iso8601_utc(self):
        date_ = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
        return date_

    def signature_hex(self, nonce, issued_at):
        message = f"www.brianknows.org wants you to sign in with your Ethereum account:\n{self.address}\n\nBy signing this message, you confirm you have read and accepted the following Terms and Conditions: https://brianknows.org/terms-and-conditions\n\nURI: https://www.brianknows.org\nVersion: 1\nChain ID: 1\nNonce: {nonce}\nIssued At: {issued_at}"
        prefixed_message = '0x' + message.encode('utf-8').hex()

        message = bytes.fromhex(prefixed_message[2:])
        message_encoded = encode_defunct(message)

        signature = Account.sign_message(message_encoded,
                                         private_key=self.transaction_executors['base'].account.key.hex())
        signature_hex = signature.signature.hex()

        if signature_hex[:2] != "0x":
            signature_hex = "0x" + signature_hex

        return signature_hex

    async def login(self):
        issued_at = self.get_iso8601_utc()
        nonce = await self.get_nonce()

        if nonce is None:
            logger.error("Не удалось получить nonce...")
            return

        signature = self.signature_hex(nonce, issued_at)

        payload = {
            "message": {
                "address": self.address,
                "domain": "www.brianknows.org",
                "issuedAt": issued_at,
                "nonce": nonce,
                "statement": "By signing this message, you confirm you have read and accepted the following Terms and Conditions: https://brianknows.org/terms-and-conditions",
                "uri": "https://www.brianknows.org",
                "chainId": "1",
                "version": "1"
            },
            "signature": signature
        }

        headers = self.headers
        headers['Content-Type'] = 'application/json'

        response_data = await self.browser_client.request(
            url="https://www.brianknows.org/api/auth/verify",
            method="POST",
            headers=self.headers,
            proxy=self.proxy,
            json=payload,
        )

        if response_data['response'].status == 200:
            if response_data['data']['ok']:
                return True
            else:
                logger.error("Ошибка при верификации...")
                return False

    async def authorized(self):
        try:
            if await self.me() is None:
                return False
            return True
        except Exception as e:
            if "Unauthorized" in str(e):
                return False
            logger.error(f"Authorized error: {e}")

    async def me(self):
        headers = self.headers
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'

        response_data = await self.browser_client.request(
            url="https://www.brianknows.org/api/auth/me",
            method="GET",
            headers=headers,
            proxy=self.proxy,
        )

        if response_data['response'].status == 200:
            data = response_data['data']
            if isinstance(data, str):
                data = json.loads(data)
            return data

    async def send_points(self, tx_hash, action, chain_id):
        headers = self.headers
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'

        payload = {
            "txHash": tx_hash,
            "action": action,
            "chainId": chain_id
        }

        response_data = await self.browser_client.request(
            url="https://www.brianknows.org/api/points",
            method="POST",
            headers=headers,
            proxy=self.proxy,
            json=payload,
        )

        if response_data['response'].status == 200:
            return True

    async def build_and_run_promt(self, chain, query):

        transaction_executor = self.transaction_executors[chain]
        chain_id = await transaction_executor.get_chain_id()

        headers = self.headers
        headers['Content-Type'] = 'application/json'

        payload = {
            "chain": chain_id,
            "query": query
        }

        results = []

        for retry in range(self.max_retry):
            try:
                response_data = await self.browser_client.request(
                    url="https://www.brianknows.org/api/builds",
                    method="POST",
                    headers=headers,
                    proxy=self.proxy,
                    json=payload
                )

                if response_data['response'].status == 200:
                    results = response_data['data']['result']
                    break

                if response_data['response'].status == 500:
                    message = response_data['data']
                    if "error" in response_data['data']:
                        message = response_data['data']['error']
                    logger.warning(f"Данное действие невозможно выполнить: {message}")
                    return False

            except Exception as e:
                logger.error("Ошибка" + str(e))

            await wait(10)

        if len(results) == 0:
            logger.error("Ошибка при сборке запроса...")
            return

        await wait(random.randint(*self.wait_before_send_transaction))

        for result in results:
            action = result['action']
            data = result['data']
            data_description = data['description']
            data_steps = data['steps']
            success = False
            tx_hash = None

            for step in data_steps:
                logger.info("Описания действия от Brianknows: " + data_description)

                for retry in range(self.max_retry):
                    logger.info(f"Выполняем действие: {action} по {self.address}... ({retry}/{self.max_retry})")

                    try:
                        if step["value"][:2] == "0x":
                            amount_eth = Web3.from_wei(int(step["value"], 16), "ether")
                        else:
                            amount_eth = Web3.from_wei(int(step["value"]), "ether")

                        status, tx_hash = await transaction_executor.send_contract_transaction(
                            tx_data=step["data"],
                            to_addr=Web3.to_checksum_address(step["to"]),
                            amount_eth=Decimal(amount_eth),
                        )
                        success = True
                        break
                    except InsufficientFunds:
                        logger.warning("Недостаточно баланса для выполнения данного действия...")
                    except Exception as e:
                        logger.error("Ошибка при выполнении действия...")
                        logger.exception(e)

                    await wait(5)

                await wait(random.randint(6, 23))

            if success and await self.send_points(to_hex(tx_hash), action, chain_id):
                logger.info("Транзакция на поинты успешно отправлена!")

            return success
