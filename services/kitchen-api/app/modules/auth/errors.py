from app.core.errors import ServiceError


class InvalidVerificationError(ServiceError):
    pass


class AuthTechnicalError(ServiceError):
    pass
