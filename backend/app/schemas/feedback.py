from datetime import datetime
from pydantic import BaseModel

from app.schemas.task import ImageOut


class FeedbackTaskSummary(BaseModel):
    task_id: str
    model: str = ""
    mode: str = "generate"
    source: str = "web"
    prompt: str = ""
    status: str = ""
    created_at: datetime | None = None
    images: list[ImageOut] = []


class FeedbackListItem(BaseModel):
    feedback_id: str
    user_id: str
    username: str = ""
    task_id: str
    status: str
    content: str
    process_note: str = ""
    result_note: str = ""
    handler_id: str | None = None
    handler_name: str = ""
    handled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    task: FeedbackTaskSummary


class FeedbackDetail(FeedbackListItem):
    task_user_id: str = ""


class FeedbackListResponse(BaseModel):
    total: int
    items: list[FeedbackListItem]


class FeedbackCreateRequest(BaseModel):
    task_id: str
    content: str


class FeedbackUpdateRequest(BaseModel):
    status: str | None = None
    process_note: str | None = None
    result_note: str | None = None
