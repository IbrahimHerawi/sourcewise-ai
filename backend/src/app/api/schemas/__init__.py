"""API request and response schemas."""

from app.api.schemas.auth import (
    AuthUserResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.api.schemas.documents import (
    DocumentDetailsResponse,
    DocumentSummaryResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaginatedDocumentListResponse,
)
from app.api.schemas.questions import (
    PaginatedQuestionHistoryResponse,
    QuestionAnswerRequest,
    QuestionAnswerResponse,
    QuestionAskRequest,
    QuestionAskResponse,
    QuestionHistoryItemResponse,
    QuestionSourceResponse,
)

__all__ = [
    "AuthUserResponse",
    "DocumentDetailsResponse",
    "DocumentSummaryResponse",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "PaginatedDocumentListResponse",
    "PaginatedQuestionHistoryResponse",
    "QuestionAnswerRequest",
    "QuestionAnswerResponse",
    "QuestionAskRequest",
    "QuestionAskResponse",
    "QuestionHistoryItemResponse",
    "QuestionSourceResponse",
    "RegisterRequest",
    "RegisterResponse",
    "UserResponse",
]
