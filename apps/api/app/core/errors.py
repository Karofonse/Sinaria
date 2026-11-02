"""Errores de dominio y su traducción HTTP. Mensajes en español, códigos estables en inglés."""

from fastapi import HTTPException, status


class DomainError(Exception):
    http_status = status.HTTP_400_BAD_REQUEST
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.http_status,
            detail={"code": self.code, "message": self.message},
        )


class InsufficientCredits(DomainError):
    http_status = status.HTTP_402_PAYMENT_REQUIRED
    code = "insufficient_credits"


class BudgetExceeded(DomainError):
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    code = "budget_exceeded"


class ConflictError(DomainError):
    http_status = status.HTTP_409_CONFLICT
    code = "conflict"


class NotFoundError(DomainError):
    http_status = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationProblem(DomainError):
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "invalid_request"


class ProviderUnavailable(DomainError):
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "provider_unavailable"


class LedgerInvariantError(Exception):
    """Un movimiento violaría una invariante. Nunca debe ocurrir si la lógica es correcta."""
