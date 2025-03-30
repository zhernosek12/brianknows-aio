from typing import Literal, Union

from eth_typing import Address, ChecksumAddress
from web3.types import ENS

Account = Union[Address, ChecksumAddress, ENS]

BlockchainName = Literal["eth", "base"]