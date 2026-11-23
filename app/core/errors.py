"""Domain exceptions, mapped to the unified error body by api/errors.py."""

from __future__ import annotations


class DomainError(Exception):
    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, details: list[dict] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class Unauthorized(DomainError):
    status_code = 401
    code = "unauthorized"


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class InvalidInput(DomainError):
    status_code = 422
    code = "invalid_input"


class UpstreamUnavailable(DomainError):
    status_code = 503
    code = "upstream_unavailable"
