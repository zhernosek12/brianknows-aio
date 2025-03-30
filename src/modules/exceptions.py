
class NotTimeForActivityError(Exception):
    pass


class NotEnoughtBalanceToSend(Exception):
    pass


class InsufficientFunds(Exception):
    pass


class EmptyBalance(Exception):
    pass


class OkxApiException(Exception):
    pass


class OkxTemporaryUnavailableException(Exception):
    pass