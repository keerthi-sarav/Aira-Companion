from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.auth import Unauthorized


class CompanionError(Exception):
    status_code: int = 400
    code: str = "companion_error"
    default_message: str = "Companion error."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class CompanionNotFound(CompanionError):
    status_code = 404
    code = "companion_not_found"
    default_message = "Companion not found."


class CompanionPaused(CompanionError):
    status_code = 409
    code = "companion_paused"
    default_message = "This companion is paused."


class CompanionBusy(CompanionError):
    status_code = 503
    code = "companion_busy"
    default_message = "The companion is busy right now. Please try again."


class CompanionMisconfigured(CompanionError):
    status_code = 422
    code = "companion_misconfigured"
    default_message = "Set your AI model in Settings."


class TurnExpired(CompanionError):
    status_code = 404
    code = "turn_expired"
    default_message = "This tool request has expired. Please start the message again."


class DuplicateName(CompanionError):
    status_code = 409
    code = "duplicate_name"
    default_message = "A companion with this name already exists."


async def _error_response(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,  # type: ignore[attr-defined]
        content={"error": exc.code, "message": exc.message},  # type: ignore[attr-defined]
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CompanionError, _error_response)
    app.add_exception_handler(Unauthorized, _error_response)
