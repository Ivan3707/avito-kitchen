from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.cart import router as cart_router
from app.api.catalog import router as catalog_router
from app.api.integration import router as integration_router
from app.services.errors import (
    AuthTechnicalError,
    ConflictError,
    InvalidVerificationError,
    RateLimitExceeded,
    ResourceNotFoundError,
)

app = FastAPI(
    title="Avito Kitchen",
    version="1.0.0",
)

app.include_router(catalog_router)
app.include_router(integration_router)
app.include_router(cart_router)
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
