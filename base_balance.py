import asyncio
import aiohttp
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from eth_account import Account
from loguru import logger
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Конфигурация сети Base
BASE_RPC = "https://mainnet.base.org"
BASE_CHAIN_ID = 8453

# Настройка формата логгера
logger.remove()  # Удаляем стандартный обработчик
logger.add(lambda msg: print(msg), format="{message}")  # Добавляем простой формат без временных меток

class BaseBalanceChecker:
    def __init__(self, keys_file: str):
        self.w3 = Web3(Web3.HTTPProvider(BASE_RPC))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.keys_file = Path(keys_file)
        self.eth_price = Decimal('0')
        
    async def get_eth_price(self) -> Decimal:
        """Получить текущий курс ETH/USDT"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT') as response:
                    if response.status == 200:
                        data = await response.json()
                        return Decimal(data['price'])
                    else:
                        logger.error(f"Ошибка получения курса ETH/USDT: {response.status}")
                        return Decimal('0')
        except Exception as e:
            logger.error(f"Ошибка при получении курса ETH/USDT: {e}")
            return Decimal('0')

    async def get_balance(self, private_key: str) -> Tuple[str, Decimal]:
        """Получить адрес и баланс кошелька"""
        try:
            account = Account.from_key(private_key)
            balance_wei = self.w3.eth.get_balance(account.address)
            balance_eth = Decimal(str(self.w3.from_wei(balance_wei, 'ether')))
            return account.address, balance_eth
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            return "", Decimal('0')

    async def process_keys(self) -> List[Tuple[str, str, Decimal]]:
        """Обработать файл с ключами"""
        results = []
        
        if not self.keys_file.exists():
            logger.error(f"Файл {self.keys_file} не найден")
            return results

        # Получаем курс ETH/USDT
        self.eth_price = await self.get_eth_price()
        if self.eth_price == 0:
            logger.warning("Не удалось получить курс ETH/USDT")

        with open(self.keys_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Разделяем строку на приватный ключ и прокси (если есть)
                parts = line.split(';')
                private_key = parts[0].strip()
                
                address, balance = await self.get_balance(private_key)
                if address:
                    results.append((private_key, address, balance))
                    
        return results

    def print_results(self, results: List[Tuple[str, str, Decimal]]):
        """Вывести результаты в консоль"""
        if not results:
            logger.warning("Нет результатов для отображения")
            return

        logger.info("\n=== Балансы кошельков в сети Base ===")
        if self.eth_price > 0:
            logger.info(f"Текущий курс ETH/USDT: {self.eth_price:.2f}")
        logger.info("-" * 100)
        logger.info(f"{'Приватный ключ':<30} {'Адрес':<42} {'Баланс (ETH)':<10} {'Стоимость (USDT)':<15}")
        logger.info("-" * 100)

        total_balance = Decimal('0')
        total_usdt = Decimal('0')
        for private_key, address, balance in results:
            usdt_value = balance * self.eth_price if self.eth_price > 0 else Decimal('0')
            # Показываем только последние 4 символа приватного ключа
            masked_key = f"...{private_key[-4:]}"
            logger.info(f"{masked_key:<30} {address:<42} {balance:<10.4f} {usdt_value:<15.2f}")
            total_balance += balance
            total_usdt += usdt_value

        logger.info("-" * 100)
        logger.info(f"Общий баланс: {total_balance:.4f} ETH")
        if self.eth_price > 0:
            logger.info(f"Общая стоимость: {total_usdt:.2f} USDT")
        logger.info(f"Всего кошельков: {len(results)}")
        
        # Добавляем статистику
        if results:
            balances = [b for _, _, b in results]
            max_balance = max(balances)
            min_balance = min(balances)
            avg_balance = sum(balances) / len(balances)
            
            logger.info("\nСтатистика:")
            logger.info(f"Максимальный баланс: {max_balance:.4f} ETH")
            logger.info(f"Минимальный баланс: {min_balance:.4f} ETH")
            logger.info(f"Средний баланс: {avg_balance:.4f} ETH")
            if self.eth_price > 0:
                logger.info(f"Максимальная стоимость: {(max_balance * self.eth_price):.2f} USDT")
                logger.info(f"Минимальная стоимость: {(min_balance * self.eth_price):.2f} USDT")
                logger.info(f"Средняя стоимость: {(avg_balance * self.eth_price):.2f} USDT")
        
        # Добавляем метку времени
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"\nОбновлено: {current_time}")

async def main():
    checker = BaseBalanceChecker("keys.txt")
    results = await checker.process_keys()
    checker.print_results(results)

if __name__ == "__main__":
    asyncio.run(main()) 
