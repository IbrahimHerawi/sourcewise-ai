"""API request and response schemas."""

from app.api.schemas.auth import (
    AuthUserResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
)
from app.api.schemas.collections import (
    CollectionCreateRequest,
    CollectionResponse,
    CollectionUpdateRequest,
    PaginatedCollectionListResponse,
)
from app.api.schemas.documents import (
    DocumentDetailsResponse,
    DocumentSummaryResponse,
    DocumentUploadItemResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaginatedDocumentListResponse,
)
from app.api.schemas.questions import (
    CitationResponse,
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
    "CitationResponse",
    "CollectionCreateRequest",
    "CollectionResponse",
    "CollectionUpdateRequest",
    "DocumentDetailsResponse",
    "DocumentSummaryResponse",
    "DocumentUploadItemResponse",
    "DocumentUploadRequest",
    "DocumentUploadResponse",
    "LoginRequest",
    "LoginResponse",
    "PaginatedCollectionListResponse",
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
