class CatalogMutationError(Exception):
    pass


class CatalogNotFoundError(CatalogMutationError):
    pass


class CatalogConflictError(CatalogMutationError):
    pass


class CatalogInvariantError(CatalogMutationError):
    pass
