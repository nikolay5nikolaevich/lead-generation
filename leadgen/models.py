from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_serializer


class Status(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    NO_DATA = "NO_DATA"
    REJECTED = "REJECTED"
    NO_EMAIL = "NO_EMAIL"
    BUDGET_STOP = "BUDGET_STOP"
    DRAFT_UNVERIFIED = "DRAFT_UNVERIFIED"


class FactKind(StrEnum):
    WHAT_THEY_DO = "what_they_do"
    SIZE = "size"
    INDUSTRY = "industry"
    CLIENTS = "clients"
    HOOK = "hook"
    TECH_STACK = "tech_stack"


class Fact(BaseModel):
    kind: FactKind
    value: str
    source_url: HttpUrl
    quote: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)

    # Чекпоинтер сохраняет модель через model_dump(), а объект HttpUrl он записать не умеет.
    # Строка при загрузке снова проверяется и становится HttpUrl.
    @field_serializer("source_url")
    def url_as_str(self, url: HttpUrl) -> str:
        return str(url)


class ScoreCriterion(BaseModel):
    criterion: str
    rating: Literal[0, 1, 2, 3]
    reasoning: str


class Score(BaseModel):
    criteria: list[ScoreCriterion]
    total: int = Field(ge=0, le=100)


class EmailHit(BaseModel):
    address: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    kind: Literal["role", "personal"]
    source: str
    confidence: Literal["high", "low_confidence"]


class Lead(BaseModel):
    domain: str
    name: str = ""
    description: str = ""
    facts: list[Fact] = []
    facts_dropped: int = 0
    score: Score | None = None
    email: EmailHit | None = None
    draft: str = ""
    status: Status = Status.PENDING
