class ServiceError(Exception):
    pass


class ResourceNotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InvalidVerificationError(ServiceError):
    pass


class AuthTechnicalError(ServiceError):
    pass


class RateLimitExceeded(ServiceError):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many requests")
        self.retry_after = retry_after
