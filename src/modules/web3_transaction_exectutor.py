import math
import time
from decimal import Decimal
from typing import Optional, Tuple

from eth_utils import to_hex
from loguru import logger
from pydantic import BaseModel
from web3 import Web3
from web3.exceptions import ContractLogicError

from src.utils.base_classes import ZERO_ADDRESS
from src.utils.base_types import Account
from src.utils.progress_bar import wait
from src.modules.exceptions import NotEnoughtBalanceToSend, InsufficientFunds


class Web3TransactionExecutorConfig(BaseModel):
    gas_price_multiplier: float
    balance_check_interval: int
    transaction_wait_attempts: int
    transaction_wait_retry_interval: int
    max_gas_price_eth_gwei_bridge_action: Optional[Decimal] = None
    max_gas_price_eth_gwei_usual_actions: Optional[Decimal] = None


def rpc_error_handler_decorator():
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for _ in range(10):
                try:
                    return await func(*args, **kwargs)
                except ContractLogicError as e:
                    raise e
                except Exception as e:
                    error = str(e)

                    if "insufficient funds for gas" in error:
                        logger.error("Баланса недостаточно для оплаты газа")
                        raise InsufficientFunds()
                    else:
                        logger.error(f"Ошибка RPC {e}, повторяем")
                        await wait(10)

        return wrapper

    return decorator


class Web3TransactionExecutor:
    def __init__(
            self,
            w3: Web3,
            account: Account,
            config: Web3TransactionExecutorConfig,
            eth_w3_trans_executor: Optional["Web3TransactionExecutor"] = None,
    ) -> None:
        self.config = config
        self.w3 = w3
        self.account = account
        self.eth_w3_trans_executor: Optional["Web3TransactionExecutor"] = eth_w3_trans_executor

    async def wait_for_gas_price(
            self, max_gas_price: int, timeout: int = 30, log_success=True
    ) -> None:
        while True:
            current_gas_price = await self.get_gas_price()

            if current_gas_price <= max_gas_price:
                if log_success:
                    logger.info(
                        f"Текущий газ {float(self.w3.from_wei(current_gas_price, 'gwei'))} gwei ниже, чем "
                        f"ожидалось {self.w3.from_wei(max_gas_price, 'gwei')}, продолжаем"
                    )
                break

            logger.info(
                f"Текущий газ {float(self.w3.from_wei(current_gas_price, 'gwei'))} gwei выше, чем  "
                f"ожидалось {self.w3.from_wei(max_gas_price, 'gwei')}, ждем {timeout} сек"
            )
            await wait(timeout)

    async def wait_for_bridge_gas_price(self, log_success=False):
        if self.eth_w3_trans_executor:
            await self.eth_w3_trans_executor.wait_for_bridge_gas_price(log_success)
            return

        if self.config.max_gas_price_eth_gwei_bridge_action is None:
            raise Exception("max_gas_price_eth_gwei_bridge_action is not set")

        await self.wait_for_gas_price(
            self.w3.to_wei(self.config.max_gas_price_eth_gwei_bridge_action, "gwei"),
            log_success=log_success,
        )

    async def wait_for_usual_actions_gas_price(self, log_success=False):

        if self.config.max_gas_price_eth_gwei_usual_actions is None:
            raise Exception(f"max_gas_price_eth_gwei_usual_actions is not set")

        await self.wait_for_gas_price(
            self.w3.to_wei(self.config.max_gas_price_eth_gwei_usual_actions, "gwei"),
            log_success=log_success,
        )

    @rpc_error_handler_decorator()
    async def get_gas_price(self) -> int:
        return int(await self.w3.eth.gas_price)

    @rpc_error_handler_decorator()
    async def get_balance(self, address: Optional[str] = None) -> int:
        if address is None:
            address = self.account.address
        return await self.w3.eth.get_balance(address)

    @rpc_error_handler_decorator()
    async def get_transaction_count(self, address: str) -> int:
        return await self.w3.eth.get_transaction_count(address)

    @rpc_error_handler_decorator()
    async def get_chain_id(self) -> int:
        return await self.w3.eth.chain_id

    @rpc_error_handler_decorator()
    async def estimate_gas(self, tx: dict) -> int:
        nonce = await self.get_transaction_count(tx["from"])
        tx = {**tx, "nonce": nonce}

        return await self.w3.eth.estimate_gas(tx)

    @rpc_error_handler_decorator()
    async def send_transaction(self, tx: dict) -> str:
        nonce = await self.get_transaction_count(tx["from"])
        tx = {**tx, "nonce": nonce}
        sign = self.account.sign_transaction(tx)

        return await self.w3.eth.send_raw_transaction(sign.rawTransaction)

    async def get_scaled_gas_price(self) -> int:
        return int(await self.get_gas_price() * self.config.gas_price_multiplier)

    async def wait_for_tx(self, tx_hash: str, retry_n=0) -> None:
        # logger.info(f"Ожидание выполнения транзакции {to_hex(tx_hash)}... попытка {retry_n}")

        try:
            trx_receipt = await self.w3.eth.get_transaction_receipt(tx_hash)
        except Exception as e:
            # logger.info(f"Информация о транзакции: {e}")
            if (
                    self.config.transaction_wait_attempts != -1
                    and retry_n >= self.config.transaction_wait_attempts
            ):
                raise Exception(f"Транзакция {to_hex(tx_hash)} не найдена")

            await wait(self.config.transaction_wait_retry_interval)
            await self.wait_for_tx(tx_hash, retry_n + 1)
            return

        status = trx_receipt["status"]

        if status == 0:
            raise Exception(f"Транзакция {to_hex(tx_hash)} была отменена EVM")
        else:
            logger.info(f"Транзакция успешно выполнена: https://basescan.org/tx/{to_hex(tx_hash)}")

        return status

    async def send_ether(
            self,
            to_addr: str,
            amount_eth: Decimal,
            gas_price: Optional[int] = None,
            gas: Optional[int] = None,
            scale_gas: float = 1.1,
    ) -> Tuple[str, Decimal]:
        if gas_price is None:
            await self.wait_for_usual_actions_gas_price()

        address = self.account.address
        tx = {
            "from": address,
            "to": Web3.to_checksum_address(to_addr),
            "value": Web3.to_wei(amount_eth, "ether"),
            "chainId": await self.get_chain_id(),
        }

        logger.info(
            f'Отправляем {amount_eth} eth из {address} на {to_addr} в chain id {tx["chainId"]}'
        )

        if gas_price is None:
            gas_price = await self.get_scaled_gas_price()

        # tx["gas"] = self.config.transaction_gas
        if gas is None:
            gas = int(await self.estimate_gas(tx) * scale_gas)

        tx["type"] = "0x2"
        tx["gas"] = gas
        tx["maxPriorityFeePerGas"] = gas_price
        tx["maxFeePerGas"] = gas_price

        logger.info(f'Итоговые расходы: {self.w3.from_wei(gas_price * gas, "ether")} eth')

        tx_hash = await self.send_transaction(tx)
        await self.wait_for_tx(tx_hash)

        return tx_hash, Web3.to_wei(amount_eth, "ether")

    async def send_contract_transaction(
            self, tx_data: str, to_addr: str, amount_eth: Decimal, scale_gas: float = 1.1, tx_type : int = 2
    ):
        await self.wait_for_usual_actions_gas_price()

        tx = {
            "from": self.account.address,
            "to": to_addr,
            "value": Web3.to_wei(amount_eth, "ether"),
            "data": tx_data,
            "chainId": await self.get_chain_id(),
        }

        gas_price = await self.get_scaled_gas_price()

        gas = int(await self.estimate_gas(tx) * scale_gas)

        if tx_type == 2:
            tx["type"] = "0x2"
            tx["gas"] = gas
            tx["maxPriorityFeePerGas"] = gas_price
            tx["maxFeePerGas"] = gas_price
        else:
            tx["gas"] = gas
            tx["gasPrice"] = gas_price

        hash_ = await self.send_transaction(tx)
        status = await self.wait_for_tx(hash_)

        return status

    async def get_transfer_price_wei(self, scale_gas: float = 1.1):
        address = self.account.address

        gas_price = await self.get_gas_price()

        mock_tx = {
            "from": ZERO_ADDRESS,
            "to": address,
            "value": Web3.to_wei(0.000001, "ether"),
            "chainId": await self.get_chain_id(),
        }

        gas = int(await self.estimate_gas(mock_tx) * scale_gas)

        return gas_price * gas, gas, gas_price

    async def send_full_balance(
            self, to_addr: str, max_amount_eth_to_abort: Decimal = Decimal(0), scale_gas: float = 1.1
    ) -> Tuple[str, Decimal]:
        address = self.account.address

        await self.wait_for_usual_actions_gas_price()

        balance = await self.get_balance(address)
        gas_price = await self.get_gas_price()

        mock_tx = {
            "from": address,
            "to": Web3.to_checksum_address(to_addr),
            "value": Web3.to_wei(0.000001, "ether"),
            "chainId": await self.get_chain_id(),
        }

        gas = int(await self.estimate_gas(mock_tx) * scale_gas)

        amount_wei = balance - gas_price * gas

        if amount_wei < Web3.to_wei(max_amount_eth_to_abort, "ether"):
            expected_eth_to_get = int(math.copysign(1, amount_wei)) * self.w3.from_wei(
                abs(amount_wei), "ether"
            )
            raise NotEnoughtBalanceToSend(
                f"Баланс {self.w3.from_wei(balance, 'ether')} eth слишком низкий, "
                f"Ожидаемая сумма для получения {expected_eth_to_get} eth"
            )

        return await self.send_ether(to_addr, self.w3.from_wei(amount_wei, "ether"), gas_price, gas)

    async def wait_for_balance(
            self, address, amount_eth: Decimal, timeout_sec: int = 0, wait_obj_msg: Optional[str] = None
    ) -> int:
        timeout_sec_str = f"от {timeout_sec} сек" if timeout_sec != 0 else "indefinitely"
        if wait_obj_msg is None:
            wait_obj_msg = f"{amount_eth} eth"
        logger.info(
            f"Ожидание {wait_obj_msg} по адресу {address} по chain id {await self.get_chain_id()} {timeout_sec_str}"
        )

        start_time = time.time()
        while True:
            logger.info(
                f"Ожидание {wait_obj_msg} на {address}, время потрачено {int(time.time() - start_time)} сек."
            )
            balance = await self.get_balance(address)

            if balance >= Web3.to_wei(amount_eth, "ether"):
                return balance

            if timeout_sec != 0 and time.time() - start_time > timeout_sec:
                raise Exception(f"Тайм-аут ожидания {wait_obj_msg} на {address}")

            await wait(self.config.balance_check_interval)