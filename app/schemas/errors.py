from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    code: str
    message: str
    metadata: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorDetail
