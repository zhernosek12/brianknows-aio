import aiohttp
from loguru import logger


async def check_proxy(proxy: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.brianknows.org/app", proxy=proxy) as response:
                if response.status == 200:
                    logger.info(f"Прокси работает: {proxy}")
                    return True
                else:
                    logger.info(response.status)
                    logger.info(await response.text())
    except Exception as e:  # noqa
        logger.info(e)

    logger.info(f"Нерабочий прокси: {proxy}")
    return False