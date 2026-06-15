from decimal import Decimal

from pydantic import BaseModel, Field
from datetime import datetime


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None = None
    avatar_url: str = ""
    role: str
    status: str
    is_whitelisted: bool = False
    credits: int = 0
    consumed_credits: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AllocateCreditsRequest(BaseModel):
    amount: int
    description: str = ""


class ResetCreditsRequest(BaseModel):
    description: str = ""


class CreateRedeemKeysBatchRequest(BaseModel):
    count: int
    credit_amount: int


class CreateOfflineOrderRequest(BaseModel):
    user_id: str
    credit_amount: int = Field(ge=1)
    amount_yuan: Decimal = Field(gt=0)
    remark: str = ""


class UpdateRedeemKeyStatusRequest(BaseModel):
    status: str


class RedeemKeyOut(BaseModel):
    id: int
    redeem_key: str
    credit_amount: int
    batch_no: str
    status: str
    is_used: bool
    used_at: datetime | None = None
    used_by_user_id: str | None = None
    used_by_username: str = ""
    used_by_user_email: str = ""
    created_by_user_id: str | None = None
    created_by_username: str = ""
    created_at: datetime | None = None


class RedeemKeyBatchOut(BaseModel):
    batch_no: str
    credit_amount: int
    count: int
    items: list[RedeemKeyOut]


class CreditLogOut(BaseModel):
    id: int
    user_id: str
    username: str = ""
    amount: int
    type: str
    mode: str = ""
    description: str = ""
    operator_name: str = ""
    task_id: str | None = None
    created_at: datetime | None = None


class PaymentOrderAdminOut(BaseModel):
    id: int
    order_no: str
    out_trade_no: str
    alipay_trade_no: str = ""
    user_id: str
    username: str = ""
    user_email: str = ""
    plan_key: str = ""
    subject: str = ""
    amount_fen: int
    amount_yuan: float
    credits: int
    status: str
    trade_status: str = ""
    buyer_id: str = ""
    paid_at: datetime | None = None
    credited_at: datetime | None = None
    closed_at: datetime | None = None
    failed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OfflineOrderOut(BaseModel):
    id: int
    business_id: str
    user_id: str
    username: str = ""
    user_email: str = ""
    credit_amount: int
    amount_fen: int
    amount_yuan: float
    remark: str = ""
    created_by: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateStatusRequest(BaseModel):
    status: str  # "active" | "disabled"


class UpdateRoleRequest(BaseModel):
    role: str  # "user" | "admin"


class UpdateWhitelistRequest(BaseModel):
    is_whitelisted: bool


class ResetPasswordRequest(BaseModel):
    new_password: str


class StatsOut(BaseModel):
    total_users: int
    total_tasks: int
    total_credit_cost: int
    active_users: int


class AnalyticsMetricOut(BaseModel):
    current: int
    previous: int
    delta: int
    delta_pct: float | None = None


class AnalyticsSummaryOut(BaseModel):
    granularity: str
    current_range_label: str
    previous_range_label: str
    total_users: int
    tasks_created: AnalyticsMetricOut
    success_tasks: AnalyticsMetricOut
    failed_tasks: AnalyticsMetricOut
    credits_consumed: AnalyticsMetricOut
    new_users: AnalyticsMetricOut
    active_users: AnalyticsMetricOut


class AnalyticsTimeseriesPointOut(BaseModel):
    label: str
    bucket_start: datetime | None = None
    bucket_end: datetime | None = None
    tasks_created: int = 0
    success_tasks: int = 0
    failed_tasks: int = 0
    credits_consumed: int = 0
    new_users: int = 0
    active_users: int = 0


class AnalyticsTimeseriesOut(BaseModel):
    granularity: str
    current_range_label: str
    previous_range_label: str
    current: list[AnalyticsTimeseriesPointOut]
    previous: list[AnalyticsTimeseriesPointOut]


class AnalyticsBreakdownItemOut(BaseModel):
    name: str
    count: int = 0
    credit_cost: int = 0


class AnalyticsBreakdownOut(BaseModel):
    range_label: str
    status_breakdown: list[AnalyticsBreakdownItemOut]
    source_breakdown: list[AnalyticsBreakdownItemOut]
    mode_breakdown: list[AnalyticsBreakdownItemOut]
    model_breakdown: list[AnalyticsBreakdownItemOut]
    top_users_by_tasks: list[AnalyticsBreakdownItemOut]
    top_users_by_credit: list[AnalyticsBreakdownItemOut]


class AnalyticsRedeemRevenueItemOut(BaseModel):
    credit_amount: int
    unit_price: float
    used_count: int
    total_amount: float


class AnalyticsRedeemRevenueOut(BaseModel):
    range_label: str
    items: list[AnalyticsRedeemRevenueItemOut]
    total_used_count: int
    total_amount: float


class ErrorAnalyticsItemOut(BaseModel):
    error_category: str
    error_message: str
    count: int = 0


class ErrorAnalyticsOut(BaseModel):
    range_label: str
    total_failed_tasks: int
    distinct_error_categories: int
    distinct_error_messages: int
    items: list[ErrorAnalyticsItemOut]


class ErrorCategoryTimeseriesPointOut(BaseModel):
    label: str
    bucket_start: datetime | None = None
    bucket_end: datetime | None = None
    total_failed_tasks: int = 0
    categories: dict[str, int]


class ErrorCategoryTimeseriesSeriesOut(BaseModel):
    error_category: str
    total_count: int = 0


class ErrorCategoryTimeseriesOut(BaseModel):
    granularity: str
    range_label: str
    series: list[ErrorCategoryTimeseriesSeriesOut]
    points: list[ErrorCategoryTimeseriesPointOut]


class ErrorTaskItemOut(BaseModel):
    task_id: str
    user_id: str = ""
    username: str = ""
    avatar_url: str = ""
    task_type: str = "text_generate"
    model: str = ""
    source: str = "web"
    mode: str = "generate"
    prompt: str = ""
    status: str = "failed"
    error_message: str = ""
    credit_cost: int = 0
    credit_refunded: bool = False
    created_at: datetime | None = None


class ErrorTaskListOut(BaseModel):
    total: int
    items: list[ErrorTaskItemOut]


class DailyReportTestOut(BaseModel):
    sent: bool
    report_date: str
    range_start: datetime
    range_end: datetime
    revenue_fen: int
    revenue_yuan: float
    paid_order_count: int
    offline_order_revenue_fen: int
    offline_order_revenue_yuan: float
    offline_order_count: int
    redeem_revenue_yuan: float
    redeem_used_count: int
    task_total_count: int
    task_success_count: int
    task_failed_count: int
    credit_consumed: int


class AdminPromoCodeItemOut(BaseModel):
    id: int
    code: str
    platform_name: str
    status: str
    created_at: datetime | None = None
    referral_count: int = 0


class AdminPromoReferralItemOut(BaseModel):
    user_id: str
    username: str
    email_masked: str = "-"
    promo_code: str = ""
    platform_name: str = ""
    reward_credits: int = 0
    registered_at: datetime | None = None


class AdminPromoReferralActivityItemOut(BaseModel):
    user_id: str
    username: str
    email_masked: str = "-"
    activity_type: str
    credits: int = 0
    amount_fen: int | None = None
    amount_yuan: float | None = None
    redeem_key: str = ""
    order_no: str = ""
    occurred_at: datetime | None = None


class AdminPromoSummaryOut(BaseModel):
    total_referrals: int = 0
    used_code_count: int = 0
    rewarded_registrations: int = 0


class AdminUserPromoDashboardOut(BaseModel):
    user_id: str
    username: str
    summary: AdminPromoSummaryOut
    promo_codes: list[AdminPromoCodeItemOut]
    referrals: list[AdminPromoReferralItemOut]
    activities: list[AdminPromoReferralActivityItemOut] = []
