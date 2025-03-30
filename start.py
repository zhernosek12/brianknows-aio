import sys
import asyncio

from src.main import main
from src.utils.force_ipv4 import force_ipv4

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    force_ipv4()
    asyncio.run(main("config"))