"""Typed application errors. Routes raise these; one handler turns them into JSON."""


class NudgeError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthError(NudgeError):
    status_code = 401
    code = "unauthorized"


class NotFoundError(NudgeError):
    status_code = 404
    code = "not_found"


class InvalidInputError(NudgeError):
    status_code = 400
    code = "invalid_input"


class ExternalServiceError(NudgeError):
    status_code = 502
    code = "external_service_error"
