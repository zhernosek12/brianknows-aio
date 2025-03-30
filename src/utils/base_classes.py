from decimal import Decimal

from pydantic import BaseModel

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class SwapToken(BaseModel):
    address: str
    name: str

    @property
    def is_eth(self):
        return self.name.strip().lower() == "eth"

    def make_zero_address(self):
        self.address = ZERO_ADDRESS


class Unit(BaseModel):
    wei: int
    value: Decimal