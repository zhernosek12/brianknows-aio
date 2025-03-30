import asyncio

from loguru import logger


def solve_captcha_retry(async_func):
    async def wrapper(idx, *args, **kwargs):
        last_exc = None
        for _ in range(1):
            try:
                return await async_func(idx, *args, **kwargs)
            except Exception as e:
                last_exc = e
        if last_exc is not None:
            raise last_exc

    return wrapper

def network_error_handler_decorator(max_retry=5):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for retry in range(max_retry):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Ошибка сети {e}, повторим {retry}/{max_retry}.")
                    await asyncio.sleep(10)

        return wrapper

    return decorator