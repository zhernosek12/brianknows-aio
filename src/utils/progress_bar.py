import asyncio
import sys

from tqdm import tqdm


async def wait(delay: int):
    for _ in tqdm(
        range(delay),
        ncols=100,
        ascii=" ▖▘▝▗▚▞█",
        bar_format="{l_bar}{bar}|",
        file=sys.stdout,
        colour="GREEN",
        desc=f"Ждем {delay} сек",
    ):
        await asyncio.sleep(1)