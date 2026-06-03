from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.credit_redeem_key import CreditRedeemKey
from app.models.credit_log import CreditLog
from app.models.payment_order import PaymentOrder
from app.models.task import Task
from app.services.admin_service import REDEEM_UNIT_PRICES
from app.utils.datetime_utils import now_local
from app.services.wecom_notify_service import is_wecom_notify_enabled, send_wecom_markdown

PAYMENT_SUCCESS_STATUSES = ("paid", "credited")


@dataclass(frozen=True)
class DailyReportStats:
    start_at: datetime
    end_at: datetime
    revenue_fen: int
    paid_order_count: int
    redeem_revenue_yuan: float
    redeem_used_count: int
    task_total_count: int
    task_success_count: int
    task_failed_count: int
    credit_consumed: int


@dataclass(frozen=True)
class DailyReportSendResult:
    sent: bool
    stats: DailyReportStats


def get_previous_day_window(reference_time: datetime | None = None) -> tuple[datetime, datetime]:
    current = reference_time or now_local()
    today_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    start_at = today_start - timedelta(days=1)
    return start_at, today_start


def collect_daily_report_stats(
    db: Session,
    *,
    start_at: datetime,
    end_at: datetime,
) -> DailyReportStats:
    revenue_fen, paid_order_count = (
        db.query(
            func.coalesce(func.sum(PaymentOrder.amount_fen), 0),
            func.count(PaymentOrder.id),
        )
        .filter(
            PaymentOrder.status.in_(PAYMENT_SUCCESS_STATUSES),
            PaymentOrder.credited_at.is_not(None),
            PaymentOrder.credited_at >= start_at,
            PaymentOrder.credited_at < end_at,
        )
        .one()
    )

    redeem_rows = (
        db.query(
            CreditRedeemKey.credit_amount,
            func.count(CreditRedeemKey.id).label("used_count"),
        )
        .filter(
            CreditRedeemKey.used_at.is_not(None),
            CreditRedeemKey.used_at >= start_at,
            CreditRedeemKey.used_at < end_at,
        )
        .group_by(CreditRedeemKey.credit_amount)
        .all()
    )
    redeem_revenue_yuan = 0.0
    redeem_used_count = 0
    for row in redeem_rows:
        credit_amount = int(row.credit_amount or 0)
        used_count = int(row.used_count or 0)
        redeem_used_count += used_count
        redeem_revenue_yuan += used_count * float(REDEEM_UNIT_PRICES.get(credit_amount, 0.0))

    task_total_count, task_success_count, task_failed_count = (
        db.query(
            func.count(Task.id),
            func.sum(case((Task.status == "success", 1), else_=0)),
            func.sum(case((Task.status == "failed", 1), else_=0)),
        )
        .filter(
            Task.created_at >= start_at,
            Task.created_at < end_at,
            Task.is_deleted.is_(False),
        )
        .one()
    )

    credit_consumed = (
        db.query(func.coalesce(func.sum(-CreditLog.amount), 0))
        .filter(
            CreditLog.type == "consume",
            CreditLog.created_at >= start_at,
            CreditLog.created_at < end_at,
        )
        .scalar()
    )

    return DailyReportStats(
        start_at=start_at,
        end_at=end_at,
        revenue_fen=int(revenue_fen or 0),
        paid_order_count=int(paid_order_count or 0),
        redeem_revenue_yuan=round(redeem_revenue_yuan, 2),
        redeem_used_count=redeem_used_count,
        task_total_count=int(task_total_count or 0),
        task_success_count=int(task_success_count or 0),
        task_failed_count=int(task_failed_count or 0),
        credit_consumed=int(credit_consumed or 0),
    )


def build_daily_report_markdown(stats: DailyReportStats) -> str:
    revenue_yuan = f"{stats.revenue_fen / 100:.2f}"
    report_date = stats.start_at.strftime("%Y-%m-%d")
    return (
        f"## 📊 每日经营数据日报\n"
        f"> 📅 日期: **{report_date}**\n"
        f"> 🕒 统计区间: {stats.start_at.strftime('%Y-%m-%d %H:%M')} ~ {stats.end_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"> 💵 在线支付营业额: <font color=\"warning\">¥{revenue_yuan}</font>\n"
        f"> ✅ 支付成功订单数: **{stats.paid_order_count}**\n"
        f"> 🎟️ 兑换码营业额: <font color=\"warning\">¥{stats.redeem_revenue_yuan:.2f}</font>\n"
        f"> 🔑 兑换码使用次数: **{stats.redeem_used_count}**\n"
        f"> 🖼️ 任务总数: **{stats.task_total_count}**\n"
        f"> 🟢 成功任务数: **{stats.task_success_count}**\n"
        f"> 🔴 失败任务数: **{stats.task_failed_count}**\n"
        f"> ⚡ 积分消耗: **{stats.credit_consumed}**"
    )


def send_previous_day_report(
    db: Session,
    *,
    reference_time: datetime | None = None,
) -> DailyReportSendResult:
    start_at, end_at = get_previous_day_window(reference_time)
    stats = collect_daily_report_stats(db, start_at=start_at, end_at=end_at)
    sent = False
    if is_wecom_notify_enabled():
        sent = send_wecom_markdown(build_daily_report_markdown(stats))
    return DailyReportSendResult(sent=sent, stats=stats)
