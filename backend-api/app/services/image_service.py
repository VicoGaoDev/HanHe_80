from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.image import Image
from app.models.regenerate_log import RegenerateLog
from app.utils.datetime_utils import now_local


def get_image(db: Session, image_id: int) -> Image:
    image = db.query(Image).filter(Image.id == image_id, Image.is_deleted.is_(False)).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    return image


def request_regenerate(
    db: Session,
    image_id: int,
    user_id: int,
    *,
    queued: bool = True,
) -> Image:
    image = db.query(Image).filter(Image.id == image_id, Image.is_deleted.is_(False)).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

    if image.task.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此图片")

    log = RegenerateLog(image_id=image.id, old_image_url=image.image_url)
    db.add(log)

    image.task.status = "queued" if queued else "pending"
    image.task.error_message = ""
    image.status = "pending"
    image.error_message = ""
    image.image_url = ""
    image.preview_url = ""
    db.commit()
    db.refresh(image)
    return image


def restore_regenerate_request(
    db: Session,
    image_id: int,
    *,
    error_message: str,
) -> Image | None:
    image = db.query(Image).filter(Image.id == image_id, Image.is_deleted.is_(False)).first()
    if not image:
        return None

    log = (
        db.query(RegenerateLog)
        .filter(RegenerateLog.image_id == image_id, RegenerateLog.new_image_url == "")
        .order_by(RegenerateLog.created_at.desc(), RegenerateLog.id.desc())
        .first()
    )
    restored_image_url = (log.old_image_url or "").strip() if log else ""
    normalized_error = (error_message or "重新生成任务入队失败").strip()

    image.image_url = restored_image_url
    image.preview_url = ""
    image.status = "success" if restored_image_url else "failed"
    image.error_message = "" if restored_image_url else normalized_error

    task = image.task
    visible_statuses = [item.status for item in task.images if not item.is_deleted]
    if any(status_value in {"pending", "queued", "processing"} for status_value in visible_statuses):
        task.status = "processing"
        task.error_message = normalized_error
    elif visible_statuses and all(status_value == "success" for status_value in visible_statuses):
        task.status = "success"
        task.error_message = ""
    else:
        task.status = "failed"
        task.error_message = normalized_error

    db.commit()
    db.refresh(image)
    return image


def delete_image_for_user(db: Session, image_id: int, user_id: int) -> bool:
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        return False
    if image.task.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作此图片")
    if image.is_deleted:
        return True

    db.query(RegenerateLog).filter(RegenerateLog.image_id == image.id).delete(synchronize_session=False)
    image.is_deleted = True
    image.deleted_at = now_local()
    db.commit()
    return True
