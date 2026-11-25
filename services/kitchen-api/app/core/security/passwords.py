import asyncio
from collections.abc import Callable
from typing import TypeVar

from anyio import to_thread
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 128

_PASSWORD_OPERATION_LIMIT = 4
_ResultT = TypeVar("_ResultT")

_password_hasher = PasswordHasher(
    memory_cost=19456,
    time_cost=2,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_password_operation_slots = asyncio.Semaphore(_PASSWORD_OPERATION_LIMIT)
_running_password_operations: set[asyncio.Task] = set()


def _operation_finished(operation: asyncio.Task) -> None:
    _running_password_operations.discard(operation)
    if not operation.cancelled():
        operation.exception()


async def _run_in_worker(
    operation: Callable[..., _ResultT],
    *args: object,
) -> _ResultT:
    await _password_operation_slots.acquire()
    slot_transferred = False
    try:
        worker_task = asyncio.create_task(
            _run_admitted_operation(operation, *args)
        )
        slot_transferred = True
    finally:
        if not slot_transferred:
            _password_operation_slots.release()
    _running_password_operations.add(worker_task)
    worker_task.add_done_callback(_operation_finished)
    return await asyncio.shield(worker_task)


async def _run_admitted_operation(
    operation: Callable[..., _ResultT],
    *args: object,
) -> _ResultT:
    try:
        return await to_thread.run_sync(
            operation,
            *args,
            abandon_on_cancel=False,
        )
    finally:
        _password_operation_slots.release()


async def hash_password(password: str) -> str:
    return await _run_in_worker(
        _password_hasher.hash,
        password,
    )


async def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password.

    InvalidHashError and non-mismatch VerificationError exceptions from
    argon2-cffi are propagated to the caller, as are unexpected failures.
    """
    try:
        return await _run_in_worker(
            _password_hasher.verify,
            password_hash,
            password,
        )
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check hash parameters without validating the hash itself.

    InvalidHashError is propagated when the parameters cannot be parsed.
    """
    return _password_hasher.check_needs_rehash(password_hash)
