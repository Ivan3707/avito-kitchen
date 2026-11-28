from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    ConflictError,
    RateLimitExceeded,
    ResourceNotFoundError,
)
from app.core.lifespan import lifespan
from app.infrastructure.database import models  # noqa: F401
from app.modules.auth.errors import (
    AuthTechnicalError,
    InvalidVerificationError,
)
from app.modules.auth.router import router as auth_router
from app.modules.cart.router import router as cart_router
from app.modules.catalog.router import router as catalog_router
from app.modules.catalog.sync.router import router as sync_router
from app.modules.checkout.router import router as checkout_router
from app.modules.orders.router import router as orders_router

app = FastAPI(
    title="Avito Kitchen",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(catalog_router)
app.include_router(sync_router)
app.include_router(orders_router)
app.include_router(cart_router)
app.include_router(checkout_router)
app.include_router(auth_router)

_AUTH_REQUEST_FIELDS = {"email", "password", "token"}


@app.exception_handler(RequestValidationError)
async def handle_request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if not request.url.path.startswith("/api/v1/auth/"):
        return await request_validation_exception_handler(request, exc)
    safe_errors = []
    seen_fields = set()
    for error in exc.errors():
        field = next(
            (
                item
                for item in reversed(error.get("loc", ()))
                if item in _AUTH_REQUEST_FIELDS
            ),
            "request",
        )
        if field in seen_fields:
            continue
        seen_fields.add(field)
        safe_errors.append(
            {
                "loc": ["body", field],
                "msg": "Invalid value",
                "type": "value_error",
            }
        )
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.exception_handler(ResourceNotFoundError)
async def handle_not_found(
    request: Request, exc: ResourceNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def handle_conflict(
    request: Request, exc: ConflictError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidVerificationError)
async def handle_invalid_verification(
    request: Request, exc: InvalidVerificationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"message": str(exc)})


@app.exception_handler(AuthTechnicalError)
async def handle_auth_technical_error(
    request: Request, exc: AuthTechnicalError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.exception_handler(RateLimitExceeded)
async def handle_rate_limit(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={"Retry-After": str(exc.retry_after)},
    )
