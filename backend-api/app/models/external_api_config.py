from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from app.database import Base


class ExternalApiConfig(Base):
    __tablename__ = "external_api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=False, default="")
    group_name = Column(String(100), nullable=False, default="默认")
    model_key = Column(String(50), nullable=False, default="")
    model_label = Column(String(100), nullable=False, default="")
    model_description = Column(String(255), nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    hide_resolution = Column(Boolean, nullable=False, default=False)
    request_url = Column(String(500), nullable=False, default="")
    request_format = Column(String(20), nullable=False, default="json")
    headers_json = Column(Text, nullable=False, default="{}")
    payload_json = Column(Text, nullable=False, default="{}")
    response_json = Column(Text, nullable=False, default="{}")
    result_base64_field = Column(String(255), nullable=False, default="")
    supports_generation = Column(Boolean, nullable=False, default=False)
    supports_inpaint = Column(Boolean, nullable=False, default=False)
    supports_prompt_reverse = Column(Boolean, nullable=False, default=False)
    is_active_generation = Column(Boolean, nullable=False, default=False)
    is_active_inpaint = Column(Boolean, nullable=False, default=False)
    is_active_prompt_reverse = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="enabled")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
