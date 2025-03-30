from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel

from src.modules.step_executor import StepExecutorConfig
from src.modules.web3_transaction_exectutor import Web3TransactionExecutorConfig

class TelegramConfig(BaseModel):
    enabled: bool
    token: str
    chat_id: int


class LogsConfig(BaseModel):
    file_path: str
    level: str
    telegram: TelegramConfig


class Config(BaseModel):
    keys_file_path: str

    shuffle_keys: bool
    proxy_mode: Literal["no_proxy", "use_proxy"]

    base_web3_transaction_executor: Web3TransactionExecutorConfig

    step_executor: StepExecutorConfig

    logs: LogsConfig
