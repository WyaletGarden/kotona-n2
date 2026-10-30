class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def conflict(code: str, message: str):
    raise DomainError(409, code, message)
