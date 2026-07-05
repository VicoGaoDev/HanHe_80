import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, inspect, text
from app.database import engine, Base
from app.config import settings
from app.logging_utils import clear_request_context, set_request_context, setup_logging
from app.utils.business_id import generate_business_id
import app.models  # noqa: F401 — ensure all models are registered

setup_logging(level=settings.LOG_LEVEL, json_logs=settings.LOG_JSON)

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.error")

app = FastAPI(title="Banana Web - AI 绘图系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.user_id = None
    set_request_context(request_id)
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code if response else 500
        user_id = getattr(request.state, "user_id", None)
        set_request_context(request_id, user_id)
        access_logger.info(
            "request completed",
            extra={
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        clear_request_context()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    user_id = getattr(request.state, "user_id", None)
    set_request_context(request_id, user_id)
    error_logger.exception(
        "unhandled exception",
        extra={
            "event": "http.request.unhandled_exception",
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
        },
    )
    clear_request_context()
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误", "request_id": request_id})


@app.on_event("startup")
def on_startup():
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    if settings.DB_AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.should_run_startup_schema_sync:
        _run_startup_schema_sync()
    if settings.should_run_seed:
        _seed_default_data()


def _run_startup_schema_sync():
    _ensure_user_credit_schema()
    _ensure_payment_order_schema()
    _ensure_offline_order_schema()
    _ensure_credit_redeem_key_schema()
    _ensure_user_api_key_schema()
    _drop_legacy_user_credits_column()
    _ensure_user_whitelist_column()
    _ensure_user_referral_schema()
    _ensure_user_promo_code_schema()
    _ensure_user_identity_schema()
    _ensure_business_id_schema()
    _ensure_prompt_history_columns()
    _ensure_image_required_columns()
    _ensure_task_credit_cost_column()
    _ensure_external_api_config_required_columns()
    _ensure_scene_binding_required_columns()
    _ensure_template_required_columns()
    _ensure_feedback_schema()
    _ensure_system_message_schema()
    _ensure_history_pin_schema()
    _ensure_user_board_schema()
    _ensure_user_canvas_schema()
    if settings.should_run_schema_compat:
        _ensure_schema_compat()
    _backfill_task_credit_costs()
    _initialize_template_sort_orders()


def _ensure_schema_compat():
    inspector = inspect(engine)

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "avatar_url" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500) DEFAULT ''"))
        if "is_whitelisted" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_whitelisted BOOLEAN DEFAULT 0"))
    task_columns = {col["name"] for col in inspector.get_columns("tasks")}
    with engine.begin() as conn:
        if "model" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN model VARCHAR(50) DEFAULT ''"))
        if "source" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN source VARCHAR(20) DEFAULT 'web'"))
        if "resolution" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN resolution VARCHAR(10) DEFAULT '4K'"))
        if "custom_size" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN custom_size VARCHAR(50) DEFAULT ''"))
        if "prompt" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN prompt TEXT DEFAULT ''"))
        if "num_images" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN num_images INTEGER DEFAULT 4"))
        if "reference_images" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN reference_images TEXT DEFAULT ''"))
        if "mode" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN mode VARCHAR(20) DEFAULT 'generate'"))
        if "source_image" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN source_image VARCHAR(500) DEFAULT ''"))
        if "mask_image" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN mask_image VARCHAR(500) DEFAULT ''"))
        if "credit_cost" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN credit_cost INTEGER DEFAULT 0"))
        if "error_message" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN error_message TEXT"))
        if "is_deleted" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "enqueued_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN enqueued_at DATETIME"))
        if "request_started_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN request_started_at DATETIME"))
        if "request_finished_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN request_finished_at DATETIME"))

    image_columns = {col["name"] for col in inspector.get_columns("images")}
    with engine.begin() as conn:
        if "is_deleted" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "deleted_at" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN deleted_at DATETIME"))
        if "preview_url" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN preview_url VARCHAR(500) DEFAULT ''"))
        if "image_format" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN image_format VARCHAR(20) DEFAULT ''"))
        if "image_size_bytes" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN image_size_bytes INTEGER DEFAULT 0"))
        if "error_message" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN error_message VARCHAR(2000) DEFAULT ''"))

    api_key_tables = set(inspector.get_table_names())
    if "prompt_history" in api_key_tables:
        prompt_history_columns = {col["name"] for col in inspector.get_columns("prompt_history")}
        with engine.begin() as conn:
            if "mode" not in prompt_history_columns:
                conn.execute(text("ALTER TABLE prompt_history ADD COLUMN mode VARCHAR(20) DEFAULT 'generate'"))
            if "source_image" not in prompt_history_columns:
                conn.execute(text("ALTER TABLE prompt_history ADD COLUMN source_image VARCHAR(500) DEFAULT ''"))

    if "api_keys" in api_key_tables:
        api_key_columns = {col["name"] for col in inspector.get_columns("api_keys")}
        with engine.begin() as conn:
            if "tongyi_key" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN tongyi_key VARCHAR(255) DEFAULT ''"))
            if "contact_qr_image" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN contact_qr_image VARCHAR(500) DEFAULT ''"))
            if "cos_secret_id" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN cos_secret_id VARCHAR(255) DEFAULT ''"))
            if "cos_secret_key" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN cos_secret_key VARCHAR(255) DEFAULT ''"))
            if "cos_bucket" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN cos_bucket VARCHAR(255) DEFAULT ''"))
            if "cos_region" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN cos_region VARCHAR(100) DEFAULT ''"))
            if "cos_public_base_url" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN cos_public_base_url VARCHAR(500) DEFAULT ''"))
            if "announcement_enabled" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN announcement_enabled INTEGER DEFAULT 0"))
            if "announcement_content" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN announcement_content VARCHAR(5000) DEFAULT ''"))
            if "announcement_updated_at" not in api_key_columns:
                conn.execute(text("ALTER TABLE api_keys ADD COLUMN announcement_updated_at DATETIME"))

    if "external_api_configs" in api_key_tables:
        external_api_columns = {col["name"] for col in inspector.get_columns("external_api_configs")}
        with engine.begin() as conn:
            if "group_name" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN group_name VARCHAR(100) DEFAULT '默认'"))
            if "model_key" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN model_key VARCHAR(50) DEFAULT ''"))
            if "model_label" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN model_label VARCHAR(100) DEFAULT ''"))
            if "model_description" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN model_description VARCHAR(255) DEFAULT ''"))
            if "sort_order" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN sort_order INTEGER DEFAULT 0"))
            if "hide_resolution" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN hide_resolution BOOLEAN DEFAULT 0"))
            if "request_format" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN request_format VARCHAR(20) DEFAULT 'json'"))
            if "response_json" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN response_json TEXT"))
            if "result_base64_field" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN result_base64_field VARCHAR(255) DEFAULT ''"))
            if "supports_inpaint" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN supports_inpaint BOOLEAN DEFAULT 0"))
            if "is_active_inpaint" not in external_api_columns:
                conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN is_active_inpaint BOOLEAN DEFAULT 0"))
            conn.execute(
                text(
                    """
                    UPDATE external_api_configs
                    SET request_format = 'json'
                    WHERE request_format IS NULL OR request_format = ''
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_configs
                    SET response_json = :response_json
                    WHERE response_json IS NULL OR response_json = ''
                    """
                ),
                {
                    "response_json": '{"candidates":[{"content":{"parts":[{"inlineData":{"mimeType":"image/png","data":"<base64>"}}]}}]}',
                },
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_configs
                    SET result_base64_field = :result_base64_field
                    WHERE result_base64_field IS NULL OR result_base64_field = ''
                    """
                ),
                {"result_base64_field": "candidates.0.content.parts.0.inlineData.data"},
            )

    if "external_api_scene_bindings" in api_key_tables:
        scene_binding_columns = {col["name"] for col in inspector.get_columns("external_api_scene_bindings")}
        credit_cost_added = False
        max_reference_images_added = False
        with engine.begin() as conn:
            if "is_deleted" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
            if "scene_type" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN scene_type VARCHAR(30) DEFAULT 'generate'"))
            if "scene_label" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN scene_label VARCHAR(100) DEFAULT ''"))
            if "scene_description" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN scene_description VARCHAR(255) DEFAULT ''"))
            if "sort_order" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN sort_order INTEGER DEFAULT 0"))
            if "hide_aspect_ratio" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_aspect_ratio BOOLEAN DEFAULT 0"))
            if "hide_resolution" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_resolution BOOLEAN DEFAULT 0"))
            if "hide_custom_size" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_custom_size BOOLEAN DEFAULT 1"))
            if "status" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN status VARCHAR(20) DEFAULT 'enabled'"))
            if "api_config_id" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN api_config_id INTEGER"))
            if "display_name" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN display_name VARCHAR(100) DEFAULT ''"))
            if "subtitle" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN subtitle VARCHAR(255) DEFAULT ''"))
            if "credit_cost" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN credit_cost INTEGER DEFAULT 0"))
                credit_cost_added = True
            if "max_reference_images" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN max_reference_images INTEGER DEFAULT 0"))
                max_reference_images_added = True
            if "aspect_ratio_options_json" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN aspect_ratio_options_json TEXT"))
            if "image_size_options_json" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN image_size_options_json TEXT"))
            if "custom_size_options_json" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN custom_size_options_json TEXT"))
            if "resolution_credit_costs_json" not in scene_binding_columns:
                conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN resolution_credit_costs_json TEXT"))
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET is_deleted = 0
                    WHERE is_deleted IS NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET resolution_credit_costs_json = '{}'
                    WHERE resolution_credit_costs_json IS NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET status = 'enabled'
                    WHERE status IS NULL OR status = ''
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET aspect_ratio_options_json = '[]'
                    WHERE aspect_ratio_options_json IS NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET image_size_options_json = '[]'
                    WHERE image_size_options_json IS NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE external_api_scene_bindings
                    SET custom_size_options_json = '[]'
                    WHERE custom_size_options_json IS NULL
                    """
                )
            )

    from app.services.external_api_config_service import get_default_credit_cost, get_default_max_reference_images

    if "external_api_scene_bindings" in api_key_tables:
        with engine.begin() as conn:
            for scene_key in [
                "banana",
                "banana2",
                "banana_pro",
                "banana_pro_plus",
                "banana_edit",
                "banana2_edit",
                "banana_pro_edit",
                "banana_pro_plus_edit",
                "prompt_reverse",
                "inpaint",
            ]:
                conn.execute(
                    text(
                        """
                        UPDATE external_api_scene_bindings
                        SET credit_cost = :credit_cost
                        WHERE scene_key = :scene_key
                          AND credit_cost IS NULL
                        """
                    ),
                    {"scene_key": scene_key, "credit_cost": get_default_credit_cost(scene_key)},
                )
                if credit_cost_added:
                    conn.execute(
                        text(
                            """
                            UPDATE external_api_scene_bindings
                            SET credit_cost = :credit_cost
                            WHERE scene_key = :scene_key
                              AND credit_cost = 0
                            """
                        ),
                        {"scene_key": scene_key, "credit_cost": get_default_credit_cost(scene_key)},
                    )
            if max_reference_images_added:
                conn.execute(
                    text(
                        """
                        UPDATE external_api_scene_bindings
                        SET max_reference_images = :image_edit_default
                        WHERE scene_type = 'image_edit'
                          AND (max_reference_images IS NULL OR max_reference_images = 0)
                        """
                    ),
                    {"image_edit_default": get_default_max_reference_images("image_edit")},
                )


def _ensure_template_required_columns():
    inspector = inspect(engine)
    if "templates" not in inspector.get_table_names():
        return

    template_columns = {col["name"] for col in inspector.get_columns("templates")}
    with engine.begin() as conn:
        if "model" not in template_columns:
            conn.execute(text("ALTER TABLE templates ADD COLUMN model VARCHAR(50) DEFAULT 'banana_pro'"))
        if "sort_order" not in template_columns:
            conn.execute(text("ALTER TABLE templates ADD COLUMN sort_order INTEGER DEFAULT 0"))
        if "custom_size" not in template_columns:
            conn.execute(text("ALTER TABLE templates ADD COLUMN custom_size VARCHAR(50) DEFAULT ''"))


def _ensure_user_whitelist_column():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "is_whitelisted" in user_columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN is_whitelisted BOOLEAN DEFAULT 0"))


def _ensure_user_referral_schema():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "referrer_id" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN referrer_id INTEGER NULL"))
            conn.execute(text("CREATE INDEX ix_users_referrer_id ON users (referrer_id)"))
            conn.execute(
                text(
                    """
                    ALTER TABLE users
                    ADD CONSTRAINT fk_users_referrer_id
                    FOREIGN KEY (referrer_id) REFERENCES users (id)
                    """
                )
            )
        if "used_promo_code_id" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN used_promo_code_id INTEGER NULL"))
            conn.execute(text("CREATE INDEX ix_users_used_promo_code_id ON users (used_promo_code_id)"))


def _ensure_user_promo_code_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "user_promo_codes" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_promo_codes (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        user_id INTEGER NOT NULL,
                        code VARCHAR(32) NOT NULL,
                        platform_name VARCHAR(50) NOT NULL DEFAULT '',
                        status VARCHAR(20) NOT NULL DEFAULT 'enabled',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_user_promo_codes_code (code),
                        INDEX ix_user_promo_codes_user_id (user_id),
                        INDEX ix_user_promo_codes_code (code),
                        INDEX ix_user_promo_codes_status (status),
                        CONSTRAINT fk_user_promo_codes_user_id FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                    """
                )
            )
        inspector = inspect(engine)

    promo_columns = {col["name"] for col in inspector.get_columns("user_promo_codes")}
    with engine.begin() as conn:
        if "platform_name" not in promo_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_promo_codes
                    ADD COLUMN platform_name VARCHAR(50) NOT NULL DEFAULT ''
                    AFTER code
                    """
                )
            )
        if "status" not in promo_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_promo_codes
                    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'enabled'
                    AFTER platform_name
                    """
                )
            )
        conn.execute(
            text(
                """
                UPDATE user_promo_codes
                SET status = 'enabled'
                WHERE status IS NULL OR status = ''
                """
            )
        )


def _ensure_user_credit_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "user_credits" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_credits (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        user_id INTEGER NOT NULL,
                        type INTEGER NOT NULL DEFAULT 0,
                        remain_credit INTEGER NOT NULL DEFAULT 0,
                        used_credit INTEGER NOT NULL DEFAULT 0,
                        status TINYINT(1) NOT NULL DEFAULT 1,
                        expire_time DATETIME NOT NULL DEFAULT '2027-12-30 23:59:59',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_user_credits_user_id_type UNIQUE (user_id, type),
                        INDEX ix_user_credits_user_id (user_id),
                        INDEX ix_user_credits_type (type),
                        CONSTRAINT fk_user_credits_user_id FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                    """
                )
            )
        inspector = inspect(engine)

    user_credit_columns = {col["name"] for col in inspector.get_columns("user_credits")}
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "remain_credit" not in user_credit_columns and "balance" in user_credit_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_credits
                    CHANGE COLUMN balance remain_credit INTEGER NOT NULL DEFAULT 0
                    """
                )
            )
            inspector = inspect(engine)
            user_credit_columns = {col["name"] for col in inspector.get_columns("user_credits")}
        if "used_credit" not in user_credit_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_credits
                    ADD COLUMN used_credit INTEGER NOT NULL DEFAULT 0
                    AFTER remain_credit
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE user_credits uc
                    LEFT JOIN (
                        SELECT user_id, COALESCE(SUM(ABS(amount)), 0) AS total_used_credit
                        FROM credit_logs
                        WHERE type = 'consume'
                        GROUP BY user_id
                    ) cl ON cl.user_id = uc.user_id
                    SET uc.used_credit = COALESCE(cl.total_used_credit, 0)
                    WHERE uc.type = 0
                    """
                )
            )
            inspector = inspect(engine)
            user_credit_columns = {col["name"] for col in inspector.get_columns("user_credits")}
        if "status" not in user_credit_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_credits
                    ADD COLUMN status TINYINT(1) NOT NULL DEFAULT 1
                    AFTER used_credit
                    """
                )
            )
            conn.execute(text("UPDATE user_credits SET status = 1 WHERE status IS NULL"))
            inspector = inspect(engine)
            user_credit_columns = {col["name"] for col in inspector.get_columns("user_credits")}
        user_credit_status_type = next(
            (str(col["type"]) for col in inspector.get_columns("user_credits") if col["name"] == "status"),
            "",
        ).lower()
        if "varchar" in user_credit_status_type or "char" in user_credit_status_type:
            conn.execute(
                text(
                    """
                    UPDATE user_credits
                    SET status = CASE
                        WHEN status IN ('enabled', '1', 'true', 'TRUE') THEN 1
                        ELSE 0
                    END
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE user_credits
                    MODIFY COLUMN status TINYINT(1) NOT NULL DEFAULT 1
                    """
                )
            )
        if "expire_time" not in user_credit_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE user_credits
                    ADD COLUMN expire_time DATETIME NOT NULL DEFAULT '2027-12-30 23:59:59'
                    AFTER status
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE user_credits
                    SET expire_time = '2027-12-30 23:59:59'
                    WHERE expire_time IS NULL
                    """
                )
            )
        if "credits" in user_columns:
            conn.execute(
                text(
                    """
                    INSERT INTO user_credits (user_id, type, remain_credit, used_credit, status, expire_time, created_at, updated_at)
                    SELECT users.id, 0, COALESCE(users.credits, 0), 0, 1, '2027-12-30 23:59:59', NOW(), NOW()
                    FROM users
                    LEFT JOIN user_credits
                      ON user_credits.user_id = users.id
                     AND user_credits.type = 0
                    WHERE user_credits.id IS NULL
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO user_credits (user_id, type, remain_credit, used_credit, status, expire_time, created_at, updated_at)
                    SELECT users.id, 0, 0, 0, 1, '2027-12-30 23:59:59', NOW(), NOW()
                    FROM users
                    LEFT JOIN user_credits
                      ON user_credits.user_id = users.id
                     AND user_credits.type = 0
                    WHERE user_credits.id IS NULL
                    """
                )
            )


def _ensure_credit_redeem_key_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "credit_redeem_keys" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE credit_redeem_keys (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        redeem_key VARCHAR(16) NOT NULL,
                        credit_amount INTEGER NOT NULL DEFAULT 0,
                        batch_no VARCHAR(32) NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'enabled',
                        created_by INTEGER NULL,
                        used_by_user_id INTEGER NULL,
                        used_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_credit_redeem_keys_redeem_key (redeem_key),
                        INDEX ix_credit_redeem_keys_redeem_key (redeem_key),
                        INDEX ix_credit_redeem_keys_batch_no (batch_no),
                        INDEX ix_credit_redeem_keys_status (status),
                        INDEX ix_credit_redeem_keys_created_by (created_by),
                        INDEX ix_credit_redeem_keys_used_by_user_id (used_by_user_id),
                        CONSTRAINT fk_credit_redeem_keys_created_by FOREIGN KEY (created_by) REFERENCES users (id),
                        CONSTRAINT fk_credit_redeem_keys_used_by_user_id FOREIGN KEY (used_by_user_id) REFERENCES users (id)
                    )
                    """
                )
            )
        return

    credit_redeem_columns = {col["name"] for col in inspector.get_columns("credit_redeem_keys")}
    with engine.begin() as conn:
        if "status" not in credit_redeem_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE credit_redeem_keys
                    ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'enabled'
                    AFTER batch_no
                    """
                )
            )
        conn.execute(
            text(
                """
                UPDATE credit_redeem_keys
                SET status = 'enabled'
                WHERE status IS NULL OR status = ''
                """
            )
        )


def _ensure_payment_order_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "payment_orders" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE payment_orders (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        order_no VARCHAR(64) NOT NULL,
                        user_id INTEGER NOT NULL,
                        plan_key VARCHAR(50) NOT NULL DEFAULT '',
                        subject VARCHAR(255) NOT NULL DEFAULT '',
                        amount_fen INTEGER NOT NULL DEFAULT 0,
                        credits INTEGER NOT NULL DEFAULT 0,
                        status VARCHAR(20) NOT NULL DEFAULT 'created',
                        out_trade_no VARCHAR(64) NOT NULL,
                        alipay_trade_no VARCHAR(64) NULL,
                        buyer_id VARCHAR(64) NOT NULL DEFAULT '',
                        trade_status VARCHAR(32) NOT NULL DEFAULT '',
                        notify_payload TEXT NULL,
                        return_payload TEXT NULL,
                        paid_at DATETIME NULL,
                        credited_at DATETIME NULL,
                        closed_at DATETIME NULL,
                        failed_at DATETIME NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_payment_orders_order_no (order_no),
                        UNIQUE KEY uq_payment_orders_out_trade_no (out_trade_no),
                        UNIQUE KEY uq_payment_orders_alipay_trade_no (alipay_trade_no),
                        INDEX ix_payment_orders_user_id (user_id),
                        INDEX ix_payment_orders_status (status),
                        INDEX ix_payment_orders_user_created_at (user_id, created_at),
                        CONSTRAINT fk_payment_orders_user_id FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                    """
                )
            )
        return

    payment_columns = {col["name"] for col in inspector.get_columns("payment_orders")}
    with engine.begin() as conn:
        if "subject" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN subject VARCHAR(255) NOT NULL DEFAULT '' AFTER plan_key"))
        if "trade_status" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN trade_status VARCHAR(32) NOT NULL DEFAULT '' AFTER buyer_id"))
        if "notify_payload" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN notify_payload TEXT NULL AFTER trade_status"))
        if "return_payload" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN return_payload TEXT NULL AFTER notify_payload"))
        if "paid_at" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN paid_at DATETIME NULL AFTER return_payload"))
        if "credited_at" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN credited_at DATETIME NULL AFTER paid_at"))
        if "closed_at" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN closed_at DATETIME NULL AFTER credited_at"))
        if "failed_at" not in payment_columns:
            conn.execute(text("ALTER TABLE payment_orders ADD COLUMN failed_at DATETIME NULL AFTER closed_at"))


def _ensure_offline_order_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "offline_orders" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE offline_orders (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        business_id VARCHAR(32) NOT NULL,
                        user_id INTEGER NOT NULL,
                        order_type VARCHAR(20) NOT NULL DEFAULT 'purchase',
                        credit_amount INTEGER NOT NULL DEFAULT 0,
                        amount_fen INTEGER NOT NULL DEFAULT 0,
                        remark VARCHAR(500) NOT NULL DEFAULT '',
                        created_by INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_offline_orders_business_id (business_id),
                        INDEX ix_offline_orders_user_id (user_id),
                        INDEX ix_offline_orders_order_type (order_type),
                        INDEX ix_offline_orders_created_by (created_by),
                        INDEX ix_offline_orders_created_at (created_at),
                        CONSTRAINT fk_offline_orders_user_id FOREIGN KEY (user_id) REFERENCES users (id),
                        CONSTRAINT fk_offline_orders_created_by FOREIGN KEY (created_by) REFERENCES users (id)
                    )
                    """
                )
            )
        return

    offline_order_columns_info = inspector.get_columns("offline_orders")
    offline_order_columns = {col["name"] for col in offline_order_columns_info}
    with engine.begin() as conn:
        if "business_id" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN business_id VARCHAR(32) NULL"))
        if "user_id" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN user_id INTEGER NULL"))
        if "order_type" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN order_type VARCHAR(20) NOT NULL DEFAULT 'purchase'"))
        if "credit_amount" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN credit_amount INTEGER NOT NULL DEFAULT 0"))
        if "amount_fen" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN amount_fen INTEGER NOT NULL DEFAULT 0"))
        if "remark" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN remark VARCHAR(500) NOT NULL DEFAULT ''"))
        if "created_by" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN created_by INTEGER NULL"))
        if "created_at" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in offline_order_columns:
            conn.execute(text("ALTER TABLE offline_orders ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

        if "business_id" in {col["name"] for col in inspector.get_columns("offline_orders")}:
            missing_ids = conn.execute(
                text("SELECT id FROM offline_orders WHERE business_id IS NULL OR business_id = ''")
            ).scalars().all()
            for offline_order_id in missing_ids:
                conn.execute(
                    text("UPDATE offline_orders SET business_id = :business_id WHERE id = :id"),
                    {"business_id": generate_business_id(), "id": offline_order_id},
                )

    refreshed_inspector = inspect(engine)
    refreshed_columns_info = refreshed_inspector.get_columns("offline_orders")
    refreshed_columns = {col["name"] for col in refreshed_columns_info}
    offline_order_indexes = {index["name"] for index in refreshed_inspector.get_indexes("offline_orders")}
    offline_order_foreign_keys = {fk.get("name") for fk in refreshed_inspector.get_foreign_keys("offline_orders")}
    with engine.begin() as conn:
        if "uq_offline_orders_business_id" not in offline_order_indexes:
            conn.execute(text("CREATE UNIQUE INDEX uq_offline_orders_business_id ON offline_orders (business_id)"))
        if "ix_offline_orders_user_id" not in offline_order_indexes:
            conn.execute(text("CREATE INDEX ix_offline_orders_user_id ON offline_orders (user_id)"))
        if "ix_offline_orders_order_type" not in offline_order_indexes:
            conn.execute(text("CREATE INDEX ix_offline_orders_order_type ON offline_orders (order_type)"))
        if "ix_offline_orders_created_by" not in offline_order_indexes:
            conn.execute(text("CREATE INDEX ix_offline_orders_created_by ON offline_orders (created_by)"))
        if "ix_offline_orders_created_at" not in offline_order_indexes:
            conn.execute(text("CREATE INDEX ix_offline_orders_created_at ON offline_orders (created_at)"))
        if "fk_offline_orders_user_id" not in offline_order_foreign_keys and "user_id" in refreshed_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE offline_orders
                    ADD CONSTRAINT fk_offline_orders_user_id
                    FOREIGN KEY (user_id) REFERENCES users (id)
                    """
                )
            )
        if "fk_offline_orders_created_by" not in offline_order_foreign_keys and "created_by" in refreshed_columns:
            conn.execute(
                text(
                    """
                    ALTER TABLE offline_orders
                    ADD CONSTRAINT fk_offline_orders_created_by
                    FOREIGN KEY (created_by) REFERENCES users (id)
                    """
                )
            )
        if "business_id" in refreshed_columns:
            conn.execute(text("ALTER TABLE offline_orders MODIFY COLUMN business_id VARCHAR(32) NOT NULL"))
        if "user_id" in refreshed_columns:
            conn.execute(text("ALTER TABLE offline_orders MODIFY COLUMN user_id INTEGER NOT NULL"))
        if "order_type" in refreshed_columns:
            conn.execute(text("ALTER TABLE offline_orders MODIFY COLUMN order_type VARCHAR(20) NOT NULL DEFAULT 'purchase'"))
        if "created_by" in refreshed_columns:
            conn.execute(text("ALTER TABLE offline_orders MODIFY COLUMN created_by INTEGER NOT NULL"))


def _ensure_user_api_key_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return

    if "user_api_key" not in table_names:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE user_api_key (
                        id INTEGER NOT NULL AUTO_INCREMENT,
                        user_id INTEGER NOT NULL,
                        subs_type VARCHAR(50) NOT NULL DEFAULT '',
                        expire_time DATETIME NULL,
                        api_key VARCHAR(35) NOT NULL,
                        key_name VARCHAR(100) NOT NULL DEFAULT '',
                        status VARCHAR(20) NOT NULL DEFAULT 'enabled',
                        is_delete BOOLEAN NOT NULL DEFAULT 0,
                        key_prefix VARCHAR(8) NOT NULL DEFAULT '',
                        key_last4 VARCHAR(4) NOT NULL DEFAULT '',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_user_api_key_api_key (api_key),
                        INDEX ix_user_api_key_user_id (user_id),
                        INDEX ix_user_api_key_status (status),
                        INDEX ix_user_api_key_is_delete (is_delete),
                        CONSTRAINT fk_user_api_key_user_id FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                    """
                )
            )
        return

    user_api_key_columns = {col["name"] for col in inspector.get_columns("user_api_key")}
    with engine.begin() as conn:
        if "last_used_at" in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key DROP COLUMN last_used_at"))
        if "last_used_ip" in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key DROP COLUMN last_used_ip"))
        if "subs_type" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN subs_type VARCHAR(50) NOT NULL DEFAULT '' AFTER user_id"))
        if "expire_time" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN expire_time DATETIME NULL AFTER subs_type"))
        if "api_key" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN api_key VARCHAR(35) NOT NULL AFTER expire_time"))
        if "key_name" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN key_name VARCHAR(100) NOT NULL DEFAULT '' AFTER api_key"))
        if "status" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'enabled' AFTER key_name"))
        if "is_delete" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN is_delete BOOLEAN NOT NULL DEFAULT 0 AFTER status"))
        if "key_prefix" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN key_prefix VARCHAR(8) NOT NULL DEFAULT '' AFTER is_delete"))
        if "key_last4" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN key_last4 VARCHAR(4) NOT NULL DEFAULT '' AFTER key_prefix"))
        if "created_at" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in user_api_key_columns:
            conn.execute(text("ALTER TABLE user_api_key ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))


def _drop_legacy_user_credits_column():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "credits" not in user_columns:
        return
    if "user_credits" not in inspector.get_table_names():
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN credits"))


def _ensure_user_identity_schema():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {col["name"] for col in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "email" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"))
        if "email_verified" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"))

    inspector = inspect(engine)
    unique_username_indexes: set[str] = set()
    has_plain_username_index = False
    has_email_unique_index = False

    for index in inspector.get_indexes("users"):
        columns = index.get("column_names") or []
        if columns == ["username"]:
            if index.get("unique") and index.get("name"):
                unique_username_indexes.add(index["name"])
            else:
                has_plain_username_index = True
        if columns == ["email"] and index.get("unique"):
            has_email_unique_index = True

    for constraint in inspector.get_unique_constraints("users"):
        columns = constraint.get("column_names") or []
        if columns == ["username"] and constraint.get("name"):
            unique_username_indexes.add(constraint["name"])
        if columns == ["email"]:
            has_email_unique_index = True

    with engine.begin() as conn:
        for index_name in sorted(unique_username_indexes):
            safe_index_name = index_name.replace("`", "")
            conn.execute(text(f"ALTER TABLE users DROP INDEX `{safe_index_name}`"))

        if not has_email_unique_index:
            conn.execute(text("CREATE UNIQUE INDEX uq_users_email ON users (email)"))

        if not has_plain_username_index:
            conn.execute(text("CREATE INDEX ix_users_username ON users (username)"))


def _has_unique_index(inspector, table_name: str, column_name: str) -> bool:
    for index in inspector.get_indexes(table_name):
        if index.get("unique") and (index.get("column_names") or []) == [column_name]:
            return True
    for constraint in inspector.get_unique_constraints(table_name):
        if (constraint.get("column_names") or []) == [column_name]:
            return True
    return False


def _ensure_business_id_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names and "tasks" not in table_names:
        return

    with engine.begin() as conn:
        if "users" in table_names:
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            if "business_id" not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN business_id VARCHAR(32) NULL"))
        if "tasks" in table_names:
            task_columns = {col["name"] for col in inspector.get_columns("tasks")}
            if "business_id" not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN business_id VARCHAR(32) NULL"))
        if "users" in table_names:
            missing_user_ids = conn.execute(
                text("SELECT id FROM users WHERE business_id IS NULL OR business_id = ''")
            ).scalars().all()
            for user_id in missing_user_ids:
                conn.execute(
                    text("UPDATE users SET business_id = :business_id WHERE id = :id"),
                    {"business_id": generate_business_id(), "id": user_id},
                )
        if "tasks" in table_names:
            missing_task_ids = conn.execute(
                text("SELECT id FROM tasks WHERE business_id IS NULL OR business_id = ''")
            ).scalars().all()
            for task_id in missing_task_ids:
                conn.execute(
                    text("UPDATE tasks SET business_id = :business_id WHERE id = :id"),
                    {"business_id": generate_business_id(), "id": task_id},
                )

    inspector = inspect(engine)
    with engine.begin() as conn:
        if "users" in table_names and not _has_unique_index(inspector, "users", "business_id"):
            conn.execute(text("CREATE UNIQUE INDEX uq_users_business_id ON users (business_id)"))
        if "tasks" in table_names and not _has_unique_index(inspector, "tasks", "business_id"):
            conn.execute(text("CREATE UNIQUE INDEX uq_tasks_business_id ON tasks (business_id)"))
        if "users" in table_names:
            conn.execute(text("ALTER TABLE users MODIFY COLUMN business_id VARCHAR(32) NOT NULL"))
        if "tasks" in table_names:
            conn.execute(text("ALTER TABLE tasks MODIFY COLUMN business_id VARCHAR(32) NOT NULL"))


def _ensure_image_required_columns():
    inspector = inspect(engine)
    if "images" not in inspector.get_table_names():
        return

    image_columns = {col["name"] for col in inspector.get_columns("images")}
    with engine.begin() as conn:
        if "is_deleted" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "deleted_at" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN deleted_at DATETIME"))
        if "preview_url" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN preview_url VARCHAR(500) DEFAULT ''"))
        if "image_format" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN image_format VARCHAR(20) DEFAULT ''"))
        if "image_size_bytes" not in image_columns:
            conn.execute(text("ALTER TABLE images ADD COLUMN image_size_bytes INTEGER DEFAULT 0"))


def _ensure_prompt_history_columns():
    inspector = inspect(engine)
    if "prompt_history" not in inspector.get_table_names():
        return

    prompt_history_columns_info = inspector.get_columns("prompt_history")
    prompt_history_columns = {col["name"] for col in prompt_history_columns_info}
    prompt_column = next((col for col in prompt_history_columns_info if col["name"] == "prompt"), None)
    with engine.begin() as conn:
        if prompt_column is not None and "VARCHAR(2000)" in str(prompt_column["type"]).upper():
            conn.execute(text("ALTER TABLE prompt_history MODIFY COLUMN prompt VARCHAR(5000) NOT NULL"))
        if "mode" not in prompt_history_columns:
            conn.execute(text("ALTER TABLE prompt_history ADD COLUMN mode VARCHAR(20) DEFAULT 'generate'"))
        if "source_image" not in prompt_history_columns:
            conn.execute(text("ALTER TABLE prompt_history ADD COLUMN source_image VARCHAR(500) DEFAULT ''"))


def _ensure_task_credit_cost_column():
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    task_columns = {col["name"] for col in inspector.get_columns("tasks")}
    if (
        "credit_cost" in task_columns
        and "custom_size" in task_columns
        and "enqueued_at" in task_columns
        and "request_started_at" in task_columns
        and "request_finished_at" in task_columns
        and "source" in task_columns
    ):
        return

    with engine.begin() as conn:
        if "credit_cost" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN credit_cost INTEGER DEFAULT 0"))
        if "custom_size" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN custom_size VARCHAR(50) DEFAULT ''"))
        if "enqueued_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN enqueued_at DATETIME"))
        if "request_started_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN request_started_at DATETIME"))
        if "request_finished_at" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN request_finished_at DATETIME"))
        if "source" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN source VARCHAR(20) DEFAULT 'web'"))


def _ensure_external_api_config_required_columns():
    inspector = inspect(engine)
    if "external_api_configs" not in inspector.get_table_names():
        return

    external_api_columns = {col["name"] for col in inspector.get_columns("external_api_configs")}
    with engine.begin() as conn:
        if "request_format" not in external_api_columns:
            conn.execute(text("ALTER TABLE external_api_configs ADD COLUMN request_format VARCHAR(20) DEFAULT 'json'"))
        conn.execute(
            text(
                """
                UPDATE external_api_configs
                SET request_format = 'json'
                WHERE request_format IS NULL OR request_format = ''
                """
            )
        )


def _ensure_scene_binding_required_columns():
    inspector = inspect(engine)
    if "external_api_scene_bindings" not in inspector.get_table_names():
        return

    scene_binding_columns = {col["name"] for col in inspector.get_columns("external_api_scene_bindings")}
    with engine.begin() as conn:
        if "is_deleted" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        if "hide_aspect_ratio" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_aspect_ratio BOOLEAN DEFAULT 0"))
        if "hide_resolution" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_resolution BOOLEAN DEFAULT 0"))
        if "hide_custom_size" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN hide_custom_size BOOLEAN DEFAULT 1"))
        if "max_reference_images" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN max_reference_images INTEGER DEFAULT 0"))
        if "aspect_ratio_options_json" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN aspect_ratio_options_json TEXT"))
        if "image_size_options_json" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN image_size_options_json TEXT"))
        if "custom_size_options_json" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN custom_size_options_json TEXT"))
        if "resolution_mapping_json" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN resolution_mapping_json TEXT"))
        if "resolution_credit_costs_json" not in scene_binding_columns:
            conn.execute(text("ALTER TABLE external_api_scene_bindings ADD COLUMN resolution_credit_costs_json TEXT"))
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET is_deleted = 0
                WHERE is_deleted IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET aspect_ratio_options_json = '[]'
                WHERE aspect_ratio_options_json IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET image_size_options_json = '[]'
                WHERE image_size_options_json IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET custom_size_options_json = '[]'
                WHERE custom_size_options_json IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET resolution_mapping_json = '{}'
                WHERE resolution_mapping_json IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE external_api_scene_bindings
                SET resolution_credit_costs_json = '{}'
                WHERE resolution_credit_costs_json IS NULL
                """
            )
        )


def _ensure_feedback_schema():
    inspector = inspect(engine)
    if "feedback" not in inspector.get_table_names():
        return

    feedback_columns = {col["name"] for col in inspector.get_columns("feedback")}
    feedback_indexes = {index["name"] for index in inspector.get_indexes("feedback")}

    with engine.begin() as conn:
        if "business_id" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN business_id VARCHAR(32) NULL"))
        if "user_id" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN user_id INTEGER"))
        if "task_id" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN task_id INTEGER"))
        elif engine.dialect.name == "mysql":
            conn.execute(text("ALTER TABLE feedback MODIFY COLUMN task_id INTEGER NULL"))
        if "content" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN content TEXT"))
        if "status" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))
        if "is_read" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN is_read TINYINT(1) DEFAULT 0"))
        if "process_note" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN process_note VARCHAR(5000) DEFAULT ''"))
        if "result_note" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN result_note VARCHAR(5000) DEFAULT ''"))
        if "handled_by" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN handled_by INTEGER"))
        if "handled_at" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN handled_at DATETIME"))
        if "created_at" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in feedback_columns:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

        conn.execute(text("UPDATE feedback SET process_note = '' WHERE process_note IS NULL"))
        conn.execute(text("UPDATE feedback SET result_note = '' WHERE result_note IS NULL"))
        conn.execute(text("UPDATE feedback SET status = 'pending' WHERE status IS NULL OR status = ''"))
        conn.execute(text("UPDATE feedback SET is_read = 0 WHERE is_read IS NULL"))

        if "ix_feedback_user_id" not in feedback_indexes:
            conn.execute(text("CREATE INDEX ix_feedback_user_id ON feedback (user_id)"))
        if "ix_feedback_task_id" not in feedback_indexes:
            conn.execute(text("CREATE INDEX ix_feedback_task_id ON feedback (task_id)"))
        if "ix_feedback_status" not in feedback_indexes:
            conn.execute(text("CREATE INDEX ix_feedback_status ON feedback (status)"))
        if "ix_feedback_is_read" not in feedback_indexes:
            conn.execute(text("CREATE INDEX ix_feedback_is_read ON feedback (is_read)"))
        if "ix_feedback_handled_by" not in feedback_indexes:
            conn.execute(text("CREATE INDEX ix_feedback_handled_by ON feedback (handled_by)"))

    from app.database import SessionLocal
    from app.models.feedback import Feedback

    db = SessionLocal()
    try:
        changed = False
        rows = db.query(Feedback).filter((Feedback.business_id.is_(None)) | (Feedback.business_id == "")).all()
        for row in rows:
            row.business_id = generate_business_id()
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()

    refreshed_indexes = {index["name"] for index in inspect(engine).get_indexes("feedback")}
    if "ix_feedback_business_id" not in refreshed_indexes:
        with engine.begin() as conn:
            conn.execute(text("CREATE UNIQUE INDEX ix_feedback_business_id ON feedback (business_id)"))


def _ensure_system_message_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return
    if "system_messages" not in table_names:
        from app.models.system_message import SystemMessage

        SystemMessage.__table__.create(bind=engine)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
    if "system_message_recipients" not in table_names:
        from app.models.system_message import SystemMessageRecipient

        SystemMessageRecipient.__table__.create(bind=engine)
        inspector = inspect(engine)

    message_columns = {col["name"] for col in inspector.get_columns("system_messages")}
    recipient_columns = {col["name"] for col in inspector.get_columns("system_message_recipients")}
    message_indexes = {index["name"] for index in inspector.get_indexes("system_messages")}
    recipient_indexes = {index["name"] for index in inspector.get_indexes("system_message_recipients")}

    with engine.begin() as conn:
        if "business_id" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN business_id VARCHAR(32) NULL"))
        if "subject" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN subject VARCHAR(200) NOT NULL DEFAULT ''"))
        if "content_html" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN content_html LONGTEXT"))
        if "content_text" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN content_text LONGTEXT"))
        if "sender_id" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN sender_id INTEGER"))
        if "recipient_scope" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN recipient_scope VARCHAR(20) DEFAULT 'selected'"))
        if "recipient_count" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN recipient_count INTEGER DEFAULT 0"))
        if "created_at" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in message_columns:
            conn.execute(text("ALTER TABLE system_messages ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

        if "message_id" not in recipient_columns:
            conn.execute(text("ALTER TABLE system_message_recipients ADD COLUMN message_id INTEGER"))
        if "user_id" not in recipient_columns:
            conn.execute(text("ALTER TABLE system_message_recipients ADD COLUMN user_id INTEGER"))
        if "is_read" not in recipient_columns:
            conn.execute(text("ALTER TABLE system_message_recipients ADD COLUMN is_read TINYINT(1) DEFAULT 0"))
        if "read_at" not in recipient_columns:
            conn.execute(text("ALTER TABLE system_message_recipients ADD COLUMN read_at DATETIME"))
        if "created_at" not in recipient_columns:
            conn.execute(text("ALTER TABLE system_message_recipients ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

        conn.execute(text("UPDATE system_messages SET subject = '' WHERE subject IS NULL"))
        conn.execute(text("UPDATE system_messages SET content_html = '' WHERE content_html IS NULL"))
        conn.execute(text("UPDATE system_messages SET content_text = '' WHERE content_text IS NULL"))
        conn.execute(text("UPDATE system_messages SET recipient_scope = 'selected' WHERE recipient_scope IS NULL OR recipient_scope = ''"))
        conn.execute(text("UPDATE system_messages SET recipient_count = 0 WHERE recipient_count IS NULL"))
        conn.execute(text("UPDATE system_message_recipients SET is_read = 0 WHERE is_read IS NULL"))

        conn.execute(text("ALTER TABLE system_messages MODIFY COLUMN content_html LONGTEXT"))
        conn.execute(text("ALTER TABLE system_messages MODIFY COLUMN content_text LONGTEXT"))

        if "ix_system_messages_subject" not in message_indexes:
            conn.execute(text("CREATE INDEX ix_system_messages_subject ON system_messages (subject)"))
        if "ix_system_messages_sender_id" not in message_indexes:
            conn.execute(text("CREATE INDEX ix_system_messages_sender_id ON system_messages (sender_id)"))
        if "ix_system_messages_recipient_scope" not in message_indexes:
            conn.execute(text("CREATE INDEX ix_system_messages_recipient_scope ON system_messages (recipient_scope)"))
        if "ix_system_message_recipients_message_id" not in recipient_indexes:
            conn.execute(text("CREATE INDEX ix_system_message_recipients_message_id ON system_message_recipients (message_id)"))
        if "ix_system_message_recipients_user_id" not in recipient_indexes:
            conn.execute(text("CREATE INDEX ix_system_message_recipients_user_id ON system_message_recipients (user_id)"))
        if "ix_system_message_recipients_is_read" not in recipient_indexes:
            conn.execute(text("CREATE INDEX ix_system_message_recipients_is_read ON system_message_recipients (is_read)"))

    from app.database import SessionLocal
    from app.models.system_message import SystemMessage

    db = SessionLocal()
    try:
        changed = False
        rows = db.query(SystemMessage).filter((SystemMessage.business_id.is_(None)) | (SystemMessage.business_id == "")).all()
        for row in rows:
            row.business_id = generate_business_id()
            changed = True
        if changed:
            db.commit()
    finally:
        db.close()

    refreshed_indexes = {index["name"] for index in inspect(engine).get_indexes("system_messages")}
    refreshed_unique_constraints = {
        constraint["name"]
        for constraint in inspect(engine).get_unique_constraints("system_message_recipients")
    }
    with engine.begin() as conn:
        if "ix_system_messages_business_id" not in refreshed_indexes:
            conn.execute(text("CREATE UNIQUE INDEX ix_system_messages_business_id ON system_messages (business_id)"))
        if "uq_system_message_recipient_message_user" not in refreshed_unique_constraints:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX uq_system_message_recipient_message_user
                    ON system_message_recipients (message_id, user_id)
                    """
                )
            )


def _ensure_history_pin_schema():
    inspector = inspect(engine)
    if "history_pins" not in inspector.get_table_names():
        from app.models.history_pin import HistoryPin

        HistoryPin.__table__.create(bind=engine)
        inspector = inspect(engine)

    history_pin_columns = {col["name"] for col in inspector.get_columns("history_pins")}
    history_pin_indexes = {index["name"] for index in inspector.get_indexes("history_pins")}

    with engine.begin() as conn:
        if "item_key" not in history_pin_columns:
            conn.execute(text("ALTER TABLE history_pins ADD COLUMN item_key VARCHAR(64)"))
        if "image_id" not in history_pin_columns:
            conn.execute(text("ALTER TABLE history_pins ADD COLUMN image_id INTEGER"))
        if "history_id" not in history_pin_columns:
            conn.execute(text("ALTER TABLE history_pins ADD COLUMN history_id INTEGER"))
        if "pinned_at" not in history_pin_columns:
            conn.execute(text("ALTER TABLE history_pins ADD COLUMN pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "created_at" not in history_pin_columns:
            conn.execute(text("ALTER TABLE history_pins ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

    refreshed_indexes = {index["name"] for index in inspect(engine).get_indexes("history_pins")}
    with engine.begin() as conn:
        if "ix_history_pins_user_pinned_at" not in refreshed_indexes:
            conn.execute(text("CREATE INDEX ix_history_pins_user_pinned_at ON history_pins (user_id, pinned_at DESC)"))
        if "ux_history_pins_user_item_key" not in refreshed_indexes:
            conn.execute(text("CREATE UNIQUE INDEX ux_history_pins_user_item_key ON history_pins (user_id, item_key)"))


def _ensure_user_board_schema():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return
    if "user_boards" not in table_names:
        from app.models.user_board import UserBoard

        UserBoard.__table__.create(bind=engine)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

    board_columns = {col["name"] for col in inspector.get_columns("user_boards")}
    board_indexes = {index["name"] for index in inspector.get_indexes("user_boards")}
    with engine.begin() as conn:
        if "name" not in board_columns:
            conn.execute(text("ALTER TABLE user_boards ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''"))
        if "created_at" not in board_columns:
            conn.execute(text("ALTER TABLE user_boards ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in board_columns:
            conn.execute(text("ALTER TABLE user_boards ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "idx_user_boards_user_updated_at" not in board_indexes:
            conn.execute(text("CREATE INDEX idx_user_boards_user_updated_at ON user_boards (user_id, updated_at)"))

    if "tasks" not in table_names:
        return
    task_columns = {col["name"] for col in inspect(engine).get_columns("tasks")}
    task_indexes = {index["name"] for index in inspect(engine).get_indexes("tasks")}
    with engine.begin() as conn:
        if "board_id" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN board_id INTEGER NULL"))
        if "idx_tasks_board_id" not in task_indexes:
            conn.execute(text("CREATE INDEX idx_tasks_board_id ON tasks (board_id)"))
        if "idx_tasks_user_board_deleted_created" not in task_indexes:
            conn.execute(text("CREATE INDEX idx_tasks_user_board_deleted_created ON tasks (user_id, board_id, is_deleted, created_at)"))


def _ensure_user_canvas_schema():
    from app.models.user_canvas import generate_canvas_project_id

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "users" not in table_names:
        return
    if "user_canvas" not in table_names:
        from app.models.user_canvas import UserCanvas

        UserCanvas.__table__.create(bind=engine)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

    canvas_columns = {col["name"] for col in inspector.get_columns("user_canvas")}
    canvas_index_defs = inspector.get_indexes("user_canvas")
    canvas_indexes = {index["name"] for index in canvas_index_defs}
    has_canvas_project_id_index = any(index.get("column_names") == ["project_id"] for index in canvas_index_defs)
    with engine.begin() as conn:
        if "project_id" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN project_id VARCHAR(16) NULL"))
        if "name" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''"))
        if "viewport_x" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN viewport_x DOUBLE NOT NULL DEFAULT 0"))
        if "viewport_y" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN viewport_y DOUBLE NOT NULL DEFAULT 0"))
        if "zoom" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN zoom DOUBLE NOT NULL DEFAULT 0.5"))
        if "is_deleted" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0"))
        if "deleted_at" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN deleted_at DATETIME NULL"))
        if "created_at" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in canvas_columns:
            conn.execute(text("ALTER TABLE user_canvas ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        existing_project_ids = {
            str(row[0])
            for row in conn.execute(text("SELECT project_id FROM user_canvas WHERE project_id IS NOT NULL AND project_id != ''")).fetchall()
        }
        rows_missing_project_id = conn.execute(text("SELECT id FROM user_canvas WHERE project_id IS NULL OR project_id = ''")).fetchall()
        for row in rows_missing_project_id:
            project_id = generate_canvas_project_id()
            while project_id in existing_project_ids:
                project_id = generate_canvas_project_id()
            existing_project_ids.add(project_id)
            conn.execute(text("UPDATE user_canvas SET project_id = :project_id WHERE id = :id"), {"project_id": project_id, "id": row[0]})
        if not has_canvas_project_id_index and "idx_user_canvas_project_id" not in canvas_indexes:
            conn.execute(text("CREATE UNIQUE INDEX idx_user_canvas_project_id ON user_canvas (project_id)"))
        if "idx_user_canvas_user_updated_at" not in canvas_indexes:
            conn.execute(text("CREATE INDEX idx_user_canvas_user_updated_at ON user_canvas (user_id, updated_at)"))
        if "idx_user_canvas_user_deleted_updated" not in canvas_indexes:
            conn.execute(text("CREATE INDEX idx_user_canvas_user_deleted_updated ON user_canvas (user_id, is_deleted, updated_at)"))

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "tasks" in table_names:
        task_columns = {col["name"] for col in inspector.get_columns("tasks")}
        task_indexes = {index["name"] for index in inspector.get_indexes("tasks")}
        with engine.begin() as conn:
            if "canvas_id" not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN canvas_id INTEGER NULL"))
            if "idx_tasks_canvas_id" not in task_indexes:
                conn.execute(text("CREATE INDEX idx_tasks_canvas_id ON tasks (canvas_id)"))
            if "idx_tasks_user_canvas_deleted_created" not in task_indexes:
                conn.execute(text("CREATE INDEX idx_tasks_user_canvas_deleted_created ON tasks (user_id, canvas_id, is_deleted, created_at)"))

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "canvas_groups" not in table_names:
        from app.models.canvas_group import CanvasGroup

        CanvasGroup.__table__.create(bind=engine)
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())

    group_columns = {col["name"] for col in inspector.get_columns("canvas_groups")}
    group_indexes = {index["name"] for index in inspector.get_indexes("canvas_groups")}
    with engine.begin() as conn:
        if "canvas_id" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN canvas_id INTEGER NOT NULL"))
        if "name" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT ''"))
        if "color" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN color VARCHAR(32) NOT NULL DEFAULT '#ffab27'"))
        if "x" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN x DOUBLE NOT NULL DEFAULT 0"))
        if "y" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN y DOUBLE NOT NULL DEFAULT 0"))
        if "width" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN width DOUBLE NOT NULL DEFAULT 320"))
        if "height" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN height DOUBLE NOT NULL DEFAULT 220"))
        if "z_index" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN z_index INTEGER NOT NULL DEFAULT 1"))
        if "created_at" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in group_columns:
            conn.execute(text("ALTER TABLE canvas_groups ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "idx_canvas_groups_canvas_id" not in group_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_groups_canvas_id ON canvas_groups (canvas_id)"))
        if "idx_canvas_groups_canvas_z" not in group_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_groups_canvas_z ON canvas_groups (canvas_id, z_index)"))

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "canvas_nodes" not in table_names:
        from app.models.canvas_node import CanvasNode

        CanvasNode.__table__.create(bind=engine)
        inspector = inspect(engine)

    node_columns = {col["name"] for col in inspector.get_columns("canvas_nodes")}
    node_indexes = {index["name"] for index in inspector.get_indexes("canvas_nodes")}
    with engine.begin() as conn:
        if "canvas_id" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN canvas_id INTEGER NOT NULL"))
        if "group_id" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN group_id INTEGER NULL"))
        if "task_id" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN task_id INTEGER NULL"))
        else:
            try:
                conn.execute(text("ALTER TABLE canvas_nodes MODIFY task_id INTEGER NULL"))
            except Exception:
                pass
        if "node_type" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN node_type VARCHAR(20) NOT NULL DEFAULT 'task'"))
        if "content" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN content VARCHAR(5000) NOT NULL DEFAULT ''"))
        if "image_url" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN image_url VARCHAR(1000) NOT NULL DEFAULT ''"))
        if "x" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN x DOUBLE NOT NULL DEFAULT 0"))
        if "y" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN y DOUBLE NOT NULL DEFAULT 0"))
        if "width" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN width DOUBLE NOT NULL DEFAULT 320"))
        if "height" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN height DOUBLE NOT NULL DEFAULT 420"))
        if "z_index" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN z_index INTEGER NOT NULL DEFAULT 1"))
        if "created_at" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in node_columns:
            conn.execute(text("ALTER TABLE canvas_nodes ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "idx_canvas_nodes_canvas_z" not in node_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_nodes_canvas_z ON canvas_nodes (canvas_id, z_index)"))
        if "idx_canvas_nodes_group_id" not in node_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_nodes_group_id ON canvas_nodes (group_id)"))
        if "idx_canvas_nodes_task_id" not in node_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_nodes_task_id ON canvas_nodes (task_id)"))

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "canvas_edges" not in table_names:
        from app.models.canvas_edge import CanvasEdge

        CanvasEdge.__table__.create(bind=engine)
        return

    edge_columns = {col["name"] for col in inspector.get_columns("canvas_edges")}
    edge_indexes = {index["name"] for index in inspector.get_indexes("canvas_edges")}
    with engine.begin() as conn:
        if "canvas_id" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN canvas_id INTEGER NOT NULL"))
        if "source_node_id" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN source_node_id INTEGER NOT NULL"))
        if "target_node_id" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN target_node_id INTEGER NOT NULL"))
        if "edge_type" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN edge_type VARCHAR(20) NOT NULL DEFAULT 'reference'"))
        if "source_anchor" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN source_anchor VARCHAR(10) NOT NULL DEFAULT 'auto'"))
        if "target_anchor" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN target_anchor VARCHAR(10) NOT NULL DEFAULT 'auto'"))
        if "is_collapsed" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN is_collapsed BOOLEAN NOT NULL DEFAULT 0"))
        if "created_at" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "updated_at" not in edge_columns:
            conn.execute(text("ALTER TABLE canvas_edges ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
        if "idx_canvas_edges_canvas_id" not in edge_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_edges_canvas_id ON canvas_edges (canvas_id)"))
        if "idx_canvas_edges_source_node_id" not in edge_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_edges_source_node_id ON canvas_edges (source_node_id)"))
        if "idx_canvas_edges_target_node_id" not in edge_indexes:
            conn.execute(text("CREATE INDEX idx_canvas_edges_target_node_id ON canvas_edges (target_node_id)"))


def _backfill_task_credit_costs():
    from app.database import SessionLocal
    from app.models.task import Task
    from app.models.credit_log import CreditLog

    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.id.asc()).all()
        if not tasks:
            return

        task_log_costs = {
            task_id: cost
            for task_id, cost in (
                db.query(CreditLog.task_id, func.coalesce(func.sum(-CreditLog.amount), 0))
                .filter(CreditLog.type == "consume", CreditLog.task_id.is_not(None))
                .group_by(CreditLog.task_id)
                .all()
            )
        }

        changed = False
        for task in tasks:
            if (task.credit_cost or 0) > 0:
                continue

            logged_cost = int(task_log_costs.get(task.id) or 0)
            if logged_cost <= 0:
                continue

            if int(task.credit_cost or 0) != logged_cost:
                task.credit_cost = logged_cost
                changed = True

        if changed:
            db.commit()
    finally:
        db.close()


def _initialize_template_sort_orders():
    from app.database import SessionLocal
    from app.models.template import Template

    _ensure_template_required_columns()

    db = SessionLocal()
    try:
        templates = (
            db.query(Template)
            .order_by(Template.created_at.asc(), Template.id.asc())
            .all()
        )
        if not templates:
            return

        has_initialized_sort = any((template.sort_order or 0) > 0 for template in templates)
        if has_initialized_sort:
            return

        for index, template in enumerate(templates, start=1):
            template.sort_order = index

        db.commit()
    finally:
        db.close()


def _seed_default_data():
    """Create default superadmin/admin users and seed runtime configs."""
    from app.database import SessionLocal
    from app.services.user_credit_service import create_default_credit_account
    from app.services.external_api_config_service import seed_legacy_configs
    from app.models.user import User
    from app.utils.security import hash_password

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "superadmin").first():
            user = User(
                username="administrator",
                password_hash=hash_password("administrator123"),
                role="superadmin",
            )
            db.add(user)
            db.flush()
            create_default_credit_account(db, user)
            db.commit()

        if not db.query(User).filter(User.role.in_(["admin", "user"])).first():
            user = User(username="admin", password_hash=hash_password("admin123"), role="admin")
            db.add(user)
            db.flush()
            create_default_credit_account(db, user)
            db.commit()

        seed_legacy_configs(
            db,
            ai_api_url=settings.AI_API_URL,
            prompt_reverse_url="https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        )
    finally:
        db.close()


upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

from app.api import auth, boards, canvases, tasks, images, history, admin, upload, api_key, templates, prompt_reverse, external_api_config, feedback, system_messages, user_api_keys, payment  # noqa: E402
app.include_router(auth.router)
app.include_router(user_api_keys.router)
app.include_router(templates.router)
app.include_router(boards.router)
app.include_router(canvases.router)
app.include_router(tasks.router)
app.include_router(images.router)
app.include_router(history.router)
app.include_router(payment.router)
app.include_router(feedback.router)
app.include_router(system_messages.router)
app.include_router(system_messages.admin_router)
app.include_router(admin.router)
app.include_router(upload.router)
app.include_router(api_key.router)
app.include_router(api_key.cos_router)
app.include_router(api_key.secret_router)
app.include_router(api_key.public_router)
app.include_router(prompt_reverse.router)
app.include_router(external_api_config.router)
app.include_router(external_api_config.scene_router)
app.include_router(external_api_config.public_router)
