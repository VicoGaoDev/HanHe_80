import json
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload
from app.models.task import Task
from app.models.image import Image
from app.models.regenerate_log import RegenerateLog
from app.models.credit_log import CreditLog
from app.models.prompt_history import PromptHistory
from app.models.history_pin import HistoryPin
from app.models.user import User
from app.services.prompt_reverse_service import (
    PROMPT_REVERSE_CREDIT_LOG_DESCRIPTION,
    PROMPT_REVERSE_MODE,
    PROMPT_REVERSE_MODEL,
)
from app.services.image_delivery_service import (
    get_optional_cos_config,
    serialize_asset_urls,
    serialize_image,
)
from app.services.business_id_service import task_external_id
from app.utils.business_id import normalize_business_id


def _parse_refs(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        refs = json.loads(raw)
        return refs if isinstance(refs, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _resolve_history_card_status(task_status: str | None, image_status: str | None) -> str:
    if image_status == "pending" and task_status in {"pending", "queued", "processing", "failed"}:
        return task_status
    return image_status or task_status or "pending"


def _build_history_pin_key(item_type: str, image_id: int | None = None, history_id: int | None = None) -> str:
    if item_type == "task" and isinstance(image_id, int):
        return f"task:{image_id}"
    if item_type == "prompt_history" and isinstance(history_id, int):
        return f"prompt_history:{history_id}"
    raise ValueError("invalid_history_pin_target")


def _serialize_history_pin(pin: HistoryPin | None) -> tuple[bool, datetime | None]:
    if not pin:
        return False, None
    return True, pin.pinned_at


def _serialize_history_images(
    images: list[Image],
    *,
    cos_config,
    include_deleted: bool = False,
) -> list[dict]:
    result: list[dict] = []
    for img in sorted(images, key=lambda item: item.id, reverse=True):
        if not include_deleted and img.is_deleted:
            continue
        result.append(serialize_image(img, cos_config=cos_config))
    return result


def get_user_history(
    db: Session,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    respect_pins: bool = True,
    mode: str | None = None,
    source: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    status: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    cos_config = get_optional_cos_config(db)
    history_pins = (
        db.query(HistoryPin)
        .filter(HistoryPin.user_id == user_id)
        .order_by(HistoryPin.pinned_at.desc(), HistoryPin.id.desc())
        .all()
        if respect_pins
        else []
    )
    history_pin_map = {pin.item_key: pin for pin in history_pins}
    image_query = (
        db.query(Image)
        .join(Task, Image.task_id == Task.id)
        .options(selectinload(Image.task).selectinload(Task.images))
        .filter(Task.user_id == user_id)
        .filter(Image.is_deleted.is_(False))
    )
    prompt_reverse_query = (
        db.query(PromptHistory)
        .filter(
            PromptHistory.user_id == user_id,
            PromptHistory.mode == PROMPT_REVERSE_MODE,
        )
    )
    if mode:
        image_query = image_query.filter(Task.mode == mode)
        if mode != PROMPT_REVERSE_MODE:
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
    if source:
        image_query = image_query.filter(Task.source == source)
        if source != "web":
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
    if model:
        image_query = image_query.filter(Task.model == model)
        if model != PROMPT_REVERSE_MODEL:
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
    if prompt:
        keyword = prompt.strip()
        if keyword:
            image_query = image_query.filter(Task.prompt.ilike(f"%{keyword}%"))
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.prompt.ilike(f"%{keyword}%"))
    if status:
        if status == "processing":
            image_query = image_query.filter(Image.status == "pending", Task.status == "processing")
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
        elif status == "pending":
            image_query = image_query.filter(Image.status == "pending", Task.status.in_(["pending", "queued"]))
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
        elif status == "failed":
            image_query = image_query.filter(or_(Image.status == "failed", and_(Image.status == "pending", Task.status == "failed")))
            prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.id.is_(None))
        else:
            image_query = image_query.filter(Image.status == status)
    if start_date:
        image_query = image_query.filter(Task.created_at >= start_date)
        prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.created_at >= start_date)
    if end_date:
        image_query = image_query.filter(Task.created_at <= end_date)
        prompt_reverse_query = prompt_reverse_query.filter(PromptHistory.created_at <= end_date)
    images = image_query.order_by(Task.created_at.desc(), Image.id.desc()).all()
    prompt_reverse_rows = prompt_reverse_query.order_by(PromptHistory.created_at.desc(), PromptHistory.id.desc()).all()

    items = []
    for image in images:
        task = image.task
        image_payload = serialize_image(image, cos_config=cos_config)
        source_asset = serialize_asset_urls(task.source_image or "", cos_config=cos_config)
        mask_asset = serialize_asset_urls(task.mask_image or "", cos_config=cos_config)
        reference_assets = [serialize_asset_urls(ref, cos_config=cos_config) for ref in _parse_refs(task.reference_images)]
        visible_images = _serialize_history_images(task.images, cos_config=cos_config)
        is_pinned, pinned_at = _serialize_history_pin(history_pin_map.get(_build_history_pin_key("task", image_id=image.id)))
        items.append({
            "history_id": None,
            "item_type": "task",
            "display_id": task_external_id(task),
            "task_id": task_external_id(task),
            "image_id": image.id,
            "is_pinned": is_pinned,
            "pinned_at": pinned_at,
            "image_url": image_payload["image_url"],
            "preview_url": image_payload["preview_url"],
            "thumb_url": image_payload["thumb_url"],
            "status": _resolve_history_card_status(task.status, image.status),
            "image_format": image_payload["image_format"],
            "image_size_bytes": image_payload["image_size_bytes"],
            "is_soft_deleted": False,
            "model": task.model or "",
            "source": task.source or "web",
            "mode": task.mode or "generate",
            "prompt": task.prompt or "",
            "reference_images": [asset["image_url"] for asset in reference_assets],
            "reference_image_thumbs": [asset["thumb_url"] for asset in reference_assets],
            "source_image": source_asset["image_url"],
            "source_image_thumb": source_asset["thumb_url"],
            "mask_image": mask_asset["image_url"],
            "mask_image_thumb": mask_asset["thumb_url"],
            "num_images": task.num_images,
            "size": task.size,
            "resolution": task.resolution or "",
            "custom_size": task.custom_size or "",
            "credit_cost": int(task.credit_cost or 0),
            "created_at": task.created_at,
            "error_message": task.error_message or "",
            "images": visible_images,
        })

    for row in prompt_reverse_rows:
        source_asset = serialize_asset_urls(row.source_image or "", cos_config=cos_config)
        is_pinned, pinned_at = _serialize_history_pin(history_pin_map.get(_build_history_pin_key("prompt_history", history_id=row.id)))
        items.append({
            "history_id": row.id,
            "item_type": "prompt_history",
            "display_id": f"PR-{row.id}",
            "task_id": None,
            "image_id": -row.id,
            "is_pinned": is_pinned,
            "pinned_at": pinned_at,
            "image_url": "",
            "preview_url": "",
            "thumb_url": "",
            "status": "success",
            "image_format": "",
            "image_size_bytes": 0,
            "is_soft_deleted": False,
            "model": PROMPT_REVERSE_MODEL,
            "source": "web",
            "mode": PROMPT_REVERSE_MODE,
            "prompt": row.prompt or "",
            "reference_images": [],
            "reference_image_thumbs": [],
            "source_image": source_asset["image_url"],
            "source_image_thumb": source_asset["thumb_url"],
            "mask_image": "",
            "mask_image_thumb": "",
            "num_images": 0,
            "size": "-",
            "resolution": "",
            "custom_size": "",
            "credit_cost": 0,
            "created_at": row.created_at,
            "error_message": "",
            "images": [],
        })

    if respect_pins:
        items.sort(
            key=lambda item: (
                1 if item.get("is_pinned") else 0,
                item.get("pinned_at") or datetime.min,
                item.get("created_at") or datetime.min,
            ),
            reverse=True,
        )
    else:
        items.sort(key=lambda item: item.get("created_at") or datetime.min, reverse=True)
    total = len(items)
    start_index = (page - 1) * page_size
    return {"total": total, "items": items[start_index:start_index + page_size]}


def delete_user_history_task(db: Session, user_id: int, task_id: str):
    normalized_task_id = normalize_business_id(task_id)
    task = db.query(Task).filter(Task.business_id == normalized_task_id, Task.user_id == user_id).first()
    if not task:
        return False

    image_ids = [img.id for img in task.images]
    if image_ids:
        db.query(RegenerateLog).filter(RegenerateLog.image_id.in_(image_ids)).delete(synchronize_session=False)
        for image in list(task.images):
            db.delete(image)

    db.query(CreditLog).filter(CreditLog.task_id == task.id).update(
        {"task_id": None},
        synchronize_session=False,
    )
    db.delete(task)
    db.commit()
    return True


def toggle_history_pin(
    db: Session,
    user_id: int,
    *,
    item_type: str,
    image_id: int | None = None,
    history_id: int | None = None,
):
    item_key = _build_history_pin_key(item_type, image_id=image_id, history_id=history_id)

    if item_type == "task":
        if not isinstance(image_id, int):
            raise ValueError("invalid_history_pin_target")
        image_exists = (
            db.query(Image.id)
            .join(Task, Image.task_id == Task.id)
            .filter(
                Image.id == image_id,
                Image.is_deleted.is_(False),
                Task.user_id == user_id,
            )
            .first()
        )
        if not image_exists:
            raise LookupError("history_item_not_found")
    elif item_type == "prompt_history":
        if not isinstance(history_id, int):
            raise ValueError("invalid_history_pin_target")
        prompt_history_exists = (
            db.query(PromptHistory.id)
            .filter(
                PromptHistory.id == history_id,
                PromptHistory.user_id == user_id,
                PromptHistory.mode == PROMPT_REVERSE_MODE,
            )
            .first()
        )
        if not prompt_history_exists:
            raise LookupError("history_item_not_found")
    else:
        raise ValueError("invalid_history_pin_target")

    pin = (
        db.query(HistoryPin)
        .filter(HistoryPin.user_id == user_id, HistoryPin.item_key == item_key)
        .first()
    )
    if pin:
        db.delete(pin)
        db.commit()
        return {"is_pinned": False, "pinned_at": None}

    pin = HistoryPin(
        user_id=user_id,
        item_type=item_type,
        item_key=item_key,
        image_id=image_id if item_type == "task" else None,
        history_id=history_id if item_type == "prompt_history" else None,
        pinned_at=datetime.utcnow(),
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)
    return {"is_pinned": True, "pinned_at": pin.pinned_at}


def get_all_history(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    source: Optional[str] = None,
    model: Optional[str] = None,
    mode: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    cos_config = get_optional_cos_config(db)
    task_query = (
        db.query(Task)
        .join(User, User.id == Task.user_id)
        .filter(User.role != "superadmin", User.is_whitelisted.is_(False))
    )
    reverse_query = (
        db.query(CreditLog)
        .join(User, User.id == CreditLog.user_id)
        .filter(
            CreditLog.type == "consume",
            CreditLog.description == PROMPT_REVERSE_CREDIT_LOG_DESCRIPTION,
            User.role != "superadmin",
            User.is_whitelisted.is_(False),
        )
    )

    if status:
        task_query = task_query.filter(Task.status == status)
        if status != "success":
            reverse_query = reverse_query.filter(CreditLog.id.is_(None))
    if user_id:
        task_query = task_query.filter(Task.user_id == user_id)
        reverse_query = reverse_query.filter(CreditLog.user_id == user_id)
    if source:
        task_query = task_query.filter(Task.source == source)
        if source != "web":
            reverse_query = reverse_query.filter(CreditLog.id.is_(None))
    if model:
        task_query = task_query.filter(Task.model == model)
        if model != PROMPT_REVERSE_MODEL:
            reverse_query = reverse_query.filter(CreditLog.id.is_(None))
    if mode:
        task_query = task_query.filter(Task.mode == mode)
        if mode != PROMPT_REVERSE_MODE:
            reverse_query = reverse_query.filter(CreditLog.id.is_(None))
    if start_date:
        task_query = task_query.filter(Task.created_at >= start_date)
        reverse_query = reverse_query.filter(CreditLog.created_at >= start_date)
    if end_date:
        task_query = task_query.filter(Task.created_at <= end_date)
        reverse_query = reverse_query.filter(CreditLog.created_at <= end_date)

    tasks = task_query.order_by(Task.created_at.desc()).all()
    reverse_logs = reverse_query.order_by(CreditLog.created_at.desc()).all()
    total = len(tasks) + len(reverse_logs)
    total_credit_cost = (
        sum(int(task.credit_cost or 0) for task in tasks)
        + sum(max(0, int(-(log.amount or 0))) for log in reverse_logs)
    )

    user_cache: dict[int, dict[str, str]] = {}
    items = []
    for task in tasks:
        if task.user_id not in user_cache:
            u = db.query(User).filter(User.id == task.user_id).first()
            user_cache[task.user_id] = {
                "username": u.username if u else "未知",
                "avatar_url": (u.avatar_url or "") if u else "",
            }

        soft_deleted_count = sum(1 for img in task.images if img.is_deleted)

        items.append({
            "item_type": "task",
            "task_id": task_external_id(task),
            "history_id": None,
            "display_id": task_external_id(task),
            "username": user_cache[task.user_id]["username"],
            "avatar_url": user_cache[task.user_id]["avatar_url"],
            "model": task.model or "",
            "source": task.source or "web",
            "mode": task.mode or "generate",
            "prompt": task.prompt or "",
            "reference_images": _parse_refs(task.reference_images),
            "num_images": task.num_images,
            "size": task.size,
            "resolution": task.resolution or "",
            "custom_size": task.custom_size or "",
            "credit_cost": int(task.credit_cost or 0),
            "status": task.status,
            "error_message": task.error_message or "",
            "is_soft_deleted": soft_deleted_count > 0,
            "soft_deleted_count": soft_deleted_count,
            "created_at": task.created_at,
            "images": _serialize_history_images(
                task.images,
                cos_config=cos_config,
                include_deleted=True,
            ),
        })

    for log in reverse_logs:
        if log.user_id not in user_cache:
            u = db.query(User).filter(User.id == log.user_id).first()
            user_cache[log.user_id] = {
                "username": u.username if u else "未知",
                "avatar_url": (u.avatar_url or "") if u else "",
            }

        items.append({
            "item_type": "prompt_history",
            "task_id": None,
            "history_id": log.id,
            "display_id": f"PR-{log.id}",
            "username": user_cache[log.user_id]["username"],
            "avatar_url": user_cache[log.user_id]["avatar_url"],
            "model": PROMPT_REVERSE_MODEL,
            "source": "web",
            "mode": PROMPT_REVERSE_MODE,
            "prompt": "",
            "reference_images": [],
            "num_images": 0,
            "size": "-",
            "resolution": "",
            "custom_size": "",
            "credit_cost": max(0, int(-(log.amount or 0))),
            "status": "success",
            "error_message": "",
            "is_soft_deleted": False,
            "soft_deleted_count": 0,
            "created_at": log.created_at,
            "images": [],
        })

    items.sort(key=lambda item: item["created_at"] or datetime.min, reverse=True)
    start_index = (page - 1) * page_size
    paged_items = items[start_index:start_index + page_size]

    return {"total": total, "total_credit_cost": total_credit_cost, "items": paged_items}
