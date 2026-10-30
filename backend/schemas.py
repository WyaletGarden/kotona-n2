import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)
from .constants import (
    KANJI_LENGTH,
    MAX_WORDS,
    MEANING_LENGTH,
    NOTE_LENGTH,
    PASSWORD_MAX,
    PASSWORD_MIN,
    READING_LENGTH,
)

Skill = Literal["reading", "meaning"]
View = Literal["flash", "quiz", "review", "words"]
Mode = Literal["flash", "quiz"]
Scope = Literal["all", "wrong"]
SessionStatus = Literal["in_progress", "paused", "completed", "abandoned", "invalidated"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Credentials(Input):
    model_config = ConfigDict(extra="forbid")  # Password whitespace is intentional.
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class Register(Credentials):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Tên không được để trống.")
        return value.strip()


class WordInput(Input):
    kanji: str = Field(min_length=1, max_length=KANJI_LENGTH)
    reading: str = Field(min_length=1, max_length=READING_LENGTH)
    meaning: str = Field(min_length=1, max_length=MEANING_LENGTH)
    note: str = Field(default="", max_length=NOTE_LENGTH)

    @field_validator("kanji", "reading", "meaning", "note", mode="before")
    @classmethod
    def normalize(cls, value):
        return unicodedata.normalize("NFC", value.strip()) if isinstance(value, str) else value

    @field_validator("reading")
    @classmethod
    def hiragana(cls, value):
        if not all(
            "HIRAGANA" in unicodedata.name(c, "") or c in "ー・" or c.isspace() for c in value
        ):
            raise ValueError("Cách đọc chỉ dùng hiragana.")
        return value


class ImportWords(Input):
    words: list[WordInput] = Field(min_length=1, max_length=MAX_WORDS)


class Review(Input):
    marked_for_review: StrictBool


class StudySettings(Input):
    count: Literal[0, 10, 20] = 10
    quizType: Skill = "reading"

    @field_validator("count", mode="before")
    @classmethod
    def numeric_count(cls, value):
        if isinstance(value, bool):
            raise ValueError("Số từ cần là số nguyên 0, 10 hoặc 20.")
        return value


class Preferences(StudySettings):
    view: View = "flash"


class Start(StudySettings):
    mode: Mode = "flash"
    scope: Scope = "all"
    view: Literal["flash", "quiz", "review"] = "flash"
    restart: StrictBool = False

    @model_validator(mode="after")
    def coherent_view(self):
        if (self.scope == "wrong" and self.view != "review") or (
            self.scope == "all" and self.view != self.mode
        ):
            raise ValueError("Trang học phải khớp chế độ và phạm vi của phiên.")
        return self


class ActionBase(Input):
    session_id: UUID
    index: int = Field(ge=0, le=MAX_WORDS)


class RevealAction(ActionBase):
    action: Literal["reveal"]


class FlashAnswerAction(ActionBase):
    action: Literal["flash_answer"]
    correct: StrictBool


class QuizAnswerAction(ActionBase):
    action: Literal["quiz_answer"]
    choice: str = Field(min_length=1, max_length=MEANING_LENGTH)


class NextAction(ActionBase):
    action: Literal["next"]


StudyAction = Annotated[
    RevealAction | FlashAnswerAction | QuizAnswerAction | NextAction, Field(discriminator="action")
]


class Output(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Limits(Output):
    max_words: int
    page_size: int
    max_page_size: int
    import_bytes: int
    kanji_length: int
    reading_length: int
    meaning_length: int
    note_length: int
    password_min: int
    password_max: int
    mastered_streak: int


class CatalogueInfo(Output):
    count: int
    added: int
    source: str
    commit: str
    license: str
    license_url: str
    credits_url: str
    scope: str
    upstream_attribution: list[str]
    adaptations: list[str]
    limits: Limits


class SkillProgress(Output):
    seen: int = 0
    correct: int = 0
    streak: int = 0
    last_correct: bool | None = None
    next_review_at: datetime | None = None


class WordOut(WordInput):
    id: UUID
    marked_for_review: bool
    seen: int
    correct: int
    known: bool
    needs_review: bool
    progress: dict[Skill, SkillProgress]


class Stats(Output):
    total: int
    known: int
    review: int
    new: int


class SessionOut(Output):
    id: UUID
    mode: Mode
    scope: Scope
    quizType: Skill
    status: SessionStatus
    index: int
    total: int
    correct: int
    answered_count: int
    answered: bool
    current_result: bool | None
    revealed: bool
    choice: str | None
    options: list[str]
    current_word: WordOut | None


class Snapshot(Output):
    revision: int
    view: View
    settings: StudySettings
    stats: Stats
    session: SessionOut | None


class WorkspaceOut(Snapshot):
    version: Literal[2] = 2
    limits: Limits
    catalogue: CatalogueInfo


class MutationOut(Snapshot):
    updated_words: list[WordOut] = Field(default_factory=list)
    deleted_ids: list[UUID] = Field(default_factory=list)
    imported: int = 0
    duplicates: int = 0


class WordPage(Output):
    revision: int
    total: int
    offset: int
    limit: int
    items: list[WordOut]


class ImportPreview(Output):
    added: int
    duplicates: int
    capacity_remaining: int
    samples: list[WordInput]


class UserOut(Output):
    id: UUID
    name: str
    email: EmailStr


class Identity(Output):
    user: UserOut
    csrf: str


class HistoryItem(Output):
    id: UUID
    mode: Mode
    scope: Scope
    quizType: Skill
    status: SessionStatus
    total: int
    correct: int
    answered_count: int
    created_at: datetime
    completed_at: datetime | None


class HistoryPage(Output):
    total: int
    offset: int
    limit: int
    items: list[HistoryItem]


class AnswerOut(Output):
    index: int
    correct: bool
    choice: str | None
    kanji: str
    reading: str
    meaning: str
    answered_at: datetime


class AnswerPage(Output):
    total: int
    offset: int
    limit: int
    items: list[AnswerOut]
