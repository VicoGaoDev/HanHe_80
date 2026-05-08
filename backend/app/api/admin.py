from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import require_admin, require_superadmin
from app.models.user import User
from app.schemas.admin import (
    CreateUserRequest, UserOut, UpdateStatusRequest, UpdateRoleRequest,
    UpdateWhitelistRequest, ResetPasswordRequest, StatsOut, AllocateCreditsRequest, ResetCreditsRequest, CreditLogOut,
    AnalyticsSummaryOut, AnalyticsTimeseriesOut, AnalyticsBreakdownOut,
)
from app.schemas.feedback import FeedbackDetail, FeedbackListResponse, FeedbackUpdateRequest
from app.schemas.history import HistoryResponse
from app.services.business_id_service import get_user_by_business_id
from app.services.admin_service import (
    create_user, list_users, update_user_status, update_user_role,
    update_user_whitelist, reset_user_password, get_stats, allocate_credits, reset_user_credits, get_credit_logs,
    get_analytics_summary, get_analytics_timeseries, get_analytics_breakdown,
)
from app.services.feedback_service import get_feedback_detail, list_feedbacks, update_feedback
from app.services.history_service import get_all_history

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _resolve_optional_user_id(db: Session, user_id: str | None) -> int | None:
    if not user_id:
        return None
    user = get_user_by_business_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.id


@router.post("/users", response_model=UserOut)
def admin_create_user(
    body: CreateUserRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_user(db, body.username, body.password, body.role, operator=_user)


@router.get("/users", response_model=list[UserOut])
def admin_list_users(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_users(db)


@router.put("/users/{user_id}/status", response_model=UserOut)
def admin_update_status(
    user_id: str,
    body: UpdateStatusRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return update_user_status(db, user_id, body.status)


@router.put("/users/{user_id}/role", response_model=UserOut)
def admin_update_role(
    user_id: str,
    body: UpdateRoleRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return update_user_role(db, user_id, body.role)


@router.put("/users/{user_id}/whitelist", response_model=UserOut)
def admin_update_whitelist(
    user_id: str,
    body: UpdateWhitelistRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_user_whitelist(db, user_id, body.is_whitelisted)


@router.put("/users/{user_id}/reset-password", response_model=UserOut)
def admin_reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return reset_user_password(db, user_id, body.new_password)


@router.post("/users/{user_id}/credits", response_model=UserOut)
def admin_allocate_credits(
    user_id: str,
    body: AllocateCreditsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return allocate_credits(db, user_id, body.amount, body.description, admin.id)


@router.post("/users/{user_id}/credits/reset", response_model=UserOut)
def admin_reset_credits(
    user_id: str,
    body: ResetCreditsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return reset_user_credits(db, user_id, body.description, admin.id)


@router.get("/credit-logs", response_model=dict)
def admin_credit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    direction: Optional[str] = Query(None, pattern="^(increase|decrease)$"),
    mode: Optional[str] = Query(None, pattern="^(generate|inpaint|promptReverse|manual)$"),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_credit_logs(db, user_id=_resolve_optional_user_id(db, user_id), page=page, page_size=page_size,
                           start_date=start_date, end_date=end_date, direction=direction, mode=mode)


@router.get("/stats", response_model=StatsOut)
def admin_stats(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_stats(db)


@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
def admin_analytics_summary(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(generate|inpaint|promptReverse)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_summary(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/analytics/timeseries", response_model=AnalyticsTimeseriesOut)
def admin_analytics_timeseries(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(generate|inpaint|promptReverse)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_timeseries(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/analytics/breakdown", response_model=AnalyticsBreakdownOut)
def admin_analytics_breakdown(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(generate|inpaint|promptReverse)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_breakdown(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/history", response_model=HistoryResponse)
def admin_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(generate|inpaint|promptReverse)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_all_history(
        db, page, page_size,
        status=status, user_id=resolved_user_id,
        source=source,
        model=model, mode=mode,
        start_date=start_date, end_date=end_date,
    )


@router.get("/feedback", response_model=FeedbackListResponse)
def admin_feedback_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feedback_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|processing|completed)$"),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_feedbacks(
        db,
        feedback_id=feedback_id,
        user_id=_resolve_optional_user_id(db, user_id),
        task_id=task_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )


@router.get("/feedback/{feedback_id}", response_model=FeedbackDetail)
def admin_feedback_detail(
    feedback_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_feedback_detail(db, feedback_id)


@router.patch("/feedback/{feedback_id}", response_model=FeedbackDetail)
def admin_feedback_update(
    feedback_id: str,
    body: FeedbackUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_feedback(
        db,
        feedback_id,
        admin=admin,
        status_value=body.status,
        process_note=body.process_note,
        result_note=body.result_note,
    )
