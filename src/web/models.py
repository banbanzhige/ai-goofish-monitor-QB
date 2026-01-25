from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union


def _normalize_filter_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "" or cleaned == "__none__":
            return None
        return cleaned
    return value


def _normalize_region_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    parts = [
        part.strip().removesuffix("省").removesuffix("市")
        for part in value.split("/")
    ]
    normalized = "/".join(part for part in parts if part)
    return normalized or None


class Task(BaseModel):
    task_name: str
    order: Optional[int] = None
    enabled: bool
    keyword: str
    description: str
    max_pages: int
    personal_only: bool
    min_price: Optional[Union[str, int, float]] = None
    max_price: Optional[Union[str, int, float]] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str
    ai_prompt_criteria_file: str
    is_running: Optional[bool] = False
    generating_ai_criteria: Optional[bool] = False
    bound_account: Optional[str] = None  # 绑定的咸鱼账号名
    auto_switch_on_risk: Optional[bool] = False  # 风控时自动切换账号
    free_shipping: Optional[bool] = False
    inspection_service: Optional[bool] = False
    account_assurance: Optional[bool] = False
    super_shop: Optional[bool] = False
    brand_new: Optional[bool] = False
    strict_selected: Optional[bool] = False
    resale: Optional[bool] = False
    new_publish_option: Optional[str] = Field(None, pattern="^(1天内|3天内|7天内|14天内)$")
    region: Optional[str] = Field(None, pattern="^[\u4e00-\u9fa5]+(/[\u4e00-\u9fa5]+)*$")

    @field_validator("new_publish_option", "region", mode="before")
    def normalize_filters(cls, value, info):
        if info.field_name == "region":
            return _normalize_region_value(value)
        return _normalize_filter_value(value)


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    order: Optional[int] = None
    enabled: Optional[bool] = None
    keyword: Optional[str] = None
    description: Optional[str] = None
    max_pages: Optional[int] = None
    personal_only: Optional[bool] = None
    min_price: Optional[Union[str, int, float]] = None
    max_price: Optional[Union[str, int, float]] = None
    cron: Optional[str] = None
    ai_prompt_base_file: Optional[str] = None
    ai_prompt_criteria_file: Optional[str] = None
    is_running: Optional[bool] = None
    generating_ai_criteria: Optional[bool] = None
    bound_account: Optional[str] = None
    auto_switch_on_risk: Optional[bool] = None
    free_shipping: Optional[bool] = None
    inspection_service: Optional[bool] = None
    account_assurance: Optional[bool] = None
    super_shop: Optional[bool] = None
    brand_new: Optional[bool] = None
    strict_selected: Optional[bool] = None
    resale: Optional[bool] = None
    new_publish_option: Optional[str] = Field(None, pattern="^(1天内|3天内|7天内|14天内)$")
    region: Optional[str] = Field(None, pattern="^[\u4e00-\u9fa5]+(/[\u4e00-\u9fa5]+)*$")

    @field_validator("new_publish_option", "region", mode="before")
    def normalize_filters(cls, value, info):
        if info.field_name == "region":
            return _normalize_region_value(value)
        return _normalize_filter_value(value)


class TaskGenerateRequest(BaseModel):
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    free_shipping: bool = False
    inspection_service: bool = False
    account_assurance: bool = False
    super_shop: bool = False
    brand_new: bool = False
    strict_selected: bool = False
    resale: bool = False
    new_publish_option: Optional[str] = Field(None, pattern="^(1天内|3天内|7天内|14天内)$")
    region: Optional[str] = Field(None, pattern="^[\u4e00-\u9fa5]+(/[\u4e00-\u9fa5]+)*$")

    @field_validator("new_publish_option", "region", mode="before")
    def normalize_filters(cls, value, info):
        if info.field_name == "region":
            return _normalize_region_value(value)
        return _normalize_filter_value(value)


class TaskGenerateRequestWithReference(BaseModel):
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None
    reference_file: Optional[str] = None
    free_shipping: bool = False
    inspection_service: bool = False
    account_assurance: bool = False
    super_shop: bool = False
    brand_new: bool = False
    strict_selected: bool = False
    resale: bool = False
    new_publish_option: Optional[str] = Field(None, pattern="^(1天内|3天内|7天内|14天内)$")
    region: Optional[str] = Field(None, pattern="^[\u4e00-\u9fa5]+(/[\u4e00-\u9fa5]+)*$")

    @field_validator("new_publish_option", "region", mode="before")
    def normalize_filters(cls, value, info):
        if info.field_name == "region":
            return _normalize_region_value(value)
        return _normalize_filter_value(value)


class TaskOrderUpdate(BaseModel):
    ordered_ids: List[int]


class PromptUpdate(BaseModel):
    content: str


class LoginStateUpdate(BaseModel):
    content: str


class NotificationSettings(BaseModel):
    NTFY_TOPIC_URL: Optional[str] = None
    NTFY_ENABLED: Optional[bool] = False
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    GOTIFY_ENABLED: Optional[bool] = False
    BARK_URL: Optional[str] = None
    BARK_ENABLED: Optional[bool] = False
    WX_BOT_URL: Optional[str] = None
    WX_BOT_ENABLED: Optional[bool] = False
    WX_CORP_ID: Optional[str] = None
    WX_AGENT_ID: Optional[str] = None
    WX_SECRET: Optional[str] = None
    WX_TO_USER: Optional[str] = None
    WX_APP_ENABLED: Optional[bool] = False
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_ENABLED: Optional[bool] = False
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_ENABLED: Optional[bool] = False
    WEBHOOK_METHOD: Optional[str] = "POST"
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = "JSON"
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    DINGTALK_WEBHOOK: Optional[str] = None
    DINGTALK_SECRET: Optional[str] = None
    DINGTALK_ENABLED: Optional[bool] = False
    PCURL_TO_MOBILE: Optional[bool] = True
    NOTIFY_AFTER_TASK_COMPLETE: Optional[bool] = True


class NewPromptRequest(BaseModel):
    filename: str
    content: str


class DeleteResultItemRequest(BaseModel):
    filename: str
    item: dict


class ResultDeleteFilters(BaseModel):
    recommended_only: Optional[bool] = False
    task_name: Optional[str] = None
    keyword: Optional[str] = None
    ai_criteria: Optional[str] = None
    manual_keyword: Optional[str] = None


class DeleteResultsBatchRequest(BaseModel):
    filename: str
    filters: Optional[ResultDeleteFilters] = None
    item_ids: Optional[List[str]] = None


class GenericSettings(BaseModel):
    LOGIN_IS_EDGE: Optional[bool] = None
    RUN_HEADLESS: Optional[bool] = None
    AI_DEBUG_MODE: Optional[bool] = None
    ENABLE_THINKING: Optional[bool] = None
    ENABLE_RESPONSE_FORMAT: Optional[bool] = None
    SEND_URL_FORMAT_IMAGE: Optional[bool] = None
    SERVER_PORT: Optional[int] = None
    WEB_USERNAME: Optional[str] = None
    WEB_PASSWORD: Optional[str] = None


class NotificationRequest(BaseModel):
    商品信息: dict
    ai_analysis: Optional[dict] = None


class TestNotificationRequest(BaseModel):
    channel: str


class TestTaskCompletionNotificationRequest(BaseModel):
    channel: str


class TestProductNotificationRequest(BaseModel):
    channel: str
