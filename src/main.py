import os

from pathlib import Path
from loguru import logger

from src.config import Config
from src.modules.data_file_iterator import DataFileIterator
from src.modules.step_executor import StepExecutor
from src.utils.hydra import load_hydra_config
from src.utils.logger import setup_logging
from src.utils.proxy import check_proxy


async def run_account(
        main_config: Config
) -> None:
    logger.info(f"Начинаю работу по файлам ключей...")

    keys_file_iterator = DataFileIterator(
        path=main_config.keys_file_path, shuffle=main_config.shuffle_keys
    )

    step_executor = StepExecutor(
        main_config.step_executor,
        main_config.base_web3_transaction_executor,
    )

    for idx, (private_key, *other_data) in enumerate(keys_file_iterator):
        logger.info(f"Начальный шаг с номером #{idx + 1}/{len(keys_file_iterator)}")

        if main_config.proxy_mode == "use_proxy":
            proxy = None
            is_proxy_valid = False

            if len(other_data) > 0:
                proxy = other_data[0]
                logger.info(f"Пробуем прокси {proxy}, прикрепленный к ключу")

                is_proxy_valid = await check_proxy(proxy)

            if not is_proxy_valid:
                logger.error(f"Прикрепленный прокси: {proxy} не рабочий!")
                continue

            logger.info(f"Используем прокси {proxy}")

            step_executor.setup_w3(proxy)
        else:
            step_executor.setup_w3()

        try:
            await step_executor.run_step(str(private_key))
        # except NotTimeForActivityError as e:
        #    logger.warning("Кошелек отработан, пропускаем его и приступаем к следующему...")
        #    continue
        except Exception as e:
            logger.exception(e)
            continue

        step_executor.cleanup_w3()


async def main(config_name: str = "config") -> None:
    config_dir = Path.cwd().resolve()
    config_hydra = load_hydra_config(
        config_dir=str(config_dir),
        config_name=config_name,
        return_hydra_section=False,
        config_overrides=os.getenv("CONFIG_OVERRIDES", None),
    )
    config = Config(**config_hydra)
    await setup_logging(config.logs)

    logger.info(f"Начинаем работу...")

    await run_account(config)
