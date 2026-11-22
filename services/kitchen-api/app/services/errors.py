class ServiceError(Exception):
    pass


class ResourceNotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass
