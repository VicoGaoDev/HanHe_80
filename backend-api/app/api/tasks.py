import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.task import TaskCreate, TaskOut
from app.services.image_delivery_service import (
    get_optional_cos_config,
    sanitize_api_public_message,
    serialize_task,
)
from app.services.business_id_service import user_external_id
from app.services.external_api_config_service import require_scene_config
from app.services.task_service import (
    create_tasks,
)

router = APIRouter(prefix="/api/tasks", tags=["生成任务"])
task_logger = logging.getLogger("app.task")
BASE64_IMAGE_PATTERN = re.compile(
    r"^(?:data:image/(?:png|jpe?g|gif|webp);base64,)?[A-Za-z0-9+/=\s]+$",
    re.I,
)
API_GENERATE_MODELS = frozenset(
    {
        "gptimage2_high",
        "gptimage2_medium",
        "gptimage2_low",
        "banana_pro",
        "banana2",
        "banana",
    }
)
API_EDIT_MODELS = frozenset(
    {
        "gptimage2_high_edit",
        "gptimage2_medium_edit",
        "gptimage2_low_edit",
        "banana_pro_edit",
        "banana2_edit",
        "banana_edit",
    }
)


def _validate_base64_image(value: str, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    if not BASE64_IMAGE_PATTERN.fullmatch(normalized) or len(normalized) <= 100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} 必须是图片 base64 或 data URL")
    return normalized


def _normalize_base64_images(values: list[str] | None) -> list[str]:
    return [_validate_base64_image(value, f"reference_images[{index}]") for index, value in enumerate(values or [])]


def _resolve_api_task_model(model: str, reference_images: list[str]) -> str:
    task_model = (model or "").strip()
    if not task_model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="model 不能为空")
    is_edit = bool(reference_images)
    if task_model in API_EDIT_MODELS and not is_edit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图编辑须传入 reference_images",
        )
    allowed = API_EDIT_MODELS if is_edit else API_GENERATE_MODELS
    if task_model not in allowed:
        kind = "图编辑" if is_edit else "文生图"
        options = "、".join(sorted(allowed))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{kind} model 无效，可选值：{options}",
        )
    return task_model


@router.post("", response_model=list[TaskOut])
def create(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task_logger.info(
        "task create request received",
        extra={
            "event": "task.api.received",
            "user_id": user_external_id(user),
            "mode": body.mode,
            "model": body.model.strip(),
            "task_count": 1,
            "prompt_length": len((body.prompt or "").strip()),
        },
    )
    if (body.mode or "generate").strip().lower() != "generate":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="暂不开放局部重绘 API")
    reference_images = _normalize_base64_images(body.reference_images)
    task_model = _resolve_api_task_model(body.model, reference_images)
    require_scene_config(db, task_model)
    resolved_resolution = "" if task_model == "banana" else body.resolution
    tasks = create_tasks(
        db,
        user_id=user.id,
        model=task_model,
        source="api",
        mode=body.mode,
        prompt=body.prompt,
        num_images=1,
        size=body.size,
        resolution=resolved_resolution,
        custom_size=body.custom_size,
        reference_images=[],
        source_image="",
        mask_image="",
        board_id=body.board_id,
    )

    from app.workers.generation import _process_task, register_task_inline_images

    try:
        for task in tasks:
            register_task_inline_images(
                task.id,
                reference_images=reference_images,
            )
            _process_task(task.id, use_distributed_lock=False)
    except Exception as exc:
        task_logger.exception(
            "sync task processing failed",
            extra={
                "event": "task.sync.exception",
                "user_id": user_external_id(user),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=sanitize_api_public_message(f"任务同步处理失败：{exc}"),
        ) from exc

    task_logger.info(
        "sync task request completed",
        extra={
            "event": "task.api.sync_completed",
            "user_id": user_external_id(user),
            "task_count": len(tasks),
            "mode": body.mode,
            "model": task_model,
        },
    )
    for task in tasks:
        db.refresh(task)
    cos_config = get_optional_cos_config(db)
    return [serialize_task(task, cos_config=cos_config) for task in tasks]
