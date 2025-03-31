import aiohttp


async def make_async_request(url: str, method: str = "GET", **kwargs) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.request(method=method, url=url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()