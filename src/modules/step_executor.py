import random

from typing import List
from typing import Optional

from loguru import logger
from pydantic import BaseModel
from web3 import Web3
from web3.eth import AsyncEth

from src.modules.web3_transaction_exectutor import (
    Web3TransactionExecutor,
    Web3TransactionExecutorConfig,
)

from src.modules.brianknows_client import BrianknowsClient
from src.modules.browser_client import BrowserClient

from src.utils.helper import write_file
from src.utils.progress_bar import wait


class StepExecutorConfig(BaseModel):
    rpc_base: str

    actions_repeat: tuple[int, int]
    prompts: List
    chains: List

    swap_eth_amount: tuple[float, float]
    swap_eth_percent: tuple[int, int]
    bridge_eth_percent: tuple[int, int]
    wrap_eth_percent: tuple[int, int]

    wait_before_after_authorization_sec: tuple[int, int]
    wait_before_action_sec: tuple[int, int]
    timeout_between_wallets_src: tuple[int, int]


class StepExecutor:
    def __init__(
            self,
            config: StepExecutorConfig,
            base_web3_transaction_executor_config: Web3TransactionExecutorConfig,
    ) -> None:
        self.config = config

        self.base_web3_transaction_executor_config = base_web3_transaction_executor_config

        self.w3_base: Optional[Web3] = None
        self.proxy: Optional[str] = None

    def setup_w3(self, proxy: Optional[str] = None):
        request_kwargs = {"proxy": proxy}

        self.w3_base = Web3(
            Web3.AsyncHTTPProvider(self.config.rpc_base, request_kwargs=request_kwargs),
            modules={"eth": (AsyncEth,)},
            middlewares=[],
        )

        self.proxy = proxy

    def cleanup_w3(self):
        self.w3_base = None
        self.proxy = None

    async def _wait_before_action(self, min_sec: int, max_sec: int, action_name: str) -> None:
        wait_sec = random.randint(min_sec, max_sec)
        logger.info(f"Ждем {wait_sec} сек перед {action_name}")
        await wait(wait_sec)

    async def run_step(self, private_key: str) -> None:
        account = self.w3_base.eth.account.from_key(private_key)
        address = account.address

        logger.info(f"Запускаем аккаунт {address}...")

        base_transaction_executor = Web3TransactionExecutor(
            w3=self.w3_base, config=self.base_web3_transaction_executor_config, account=account
        )

        browser_client = BrowserClient(
            username=address,
            proxy=self.proxy
        )

        transaction_executors = {
            "base": base_transaction_executor
        }

        brianknows_client = BrianknowsClient(
            browser_client=browser_client,
            transaction_executors=transaction_executors,
            address=address,
            proxy=self.proxy
        )

        chain = random.choice(self.config.chains)

        if chain not in list(transaction_executors.keys()):
            logger.error("Сеть chain в данный момент не поддерживается софтом...")
            return

        if not await brianknows_client.authorized():
            logger.info("Начинаем авторизацию...")

            if await brianknows_client.login():
                logger.info("Успешно авторизовались, получаем информацию о профиле...")

                profile_data = await brianknows_client.me()

                account_id = profile_data['account']['id']

                browser_client.set_param('account_id', account_id)
                browser_client.save()

                await self._wait_before_action(
                    min_sec=self.config.wait_before_after_authorization_sec[0],
                    max_sec=self.config.wait_before_after_authorization_sec[1],
                    action_name="выполненияем действий",
                )

        logger.info(f"Формируем действия, сеть: {chain}")

        actions = []

        for _ in range(random.randint(*self.config.actions_repeat)):
            action = random.choice(self.config.prompts)

            swap_eth_amount = round(random.uniform(*self.config.swap_eth_amount), 6)
            swap_eth_percent = random.randint(*self.config.swap_eth_percent)
            bridge_eth_percent = random.randint(*self.config.bridge_eth_percent)
            wrap_eth_percent = random.randint(*self.config.wrap_eth_percent)

            action = action.replace("{swap_eth_amount}", str(swap_eth_amount))
            action = action.replace("{swap_eth_percent}", str(swap_eth_percent))
            action = action.replace("{bridge_eth_percent}", str(bridge_eth_percent))
            action = action.replace("{wrap_eth_percent}", str(wrap_eth_percent))

            actions.append(action)

        random.shuffle(actions)

        for action in actions:
            logger.info(f"Запускаем действие '{action}'...")
            if await brianknows_client.build_and_run_promt(chain, action):
                logger.info(f"Успешно выполнено {action}!")
                status = 1
            else:
                status = 0

            write_file(address, chain, action, status)

            await self._wait_before_action(
                min_sec=self.config.wait_before_action_sec[0],
                max_sec=self.config.wait_before_action_sec[1],
                action_name="выполнением следующего действия"
            )

        logger.success(f"Аккаунт {address} отработан...")
        await wait(random.randint(*self.config.timeout_between_wallets_src))
