from pydantic import BaseModel
from typing import List, Optional


class Task(BaseModel):
    task_name: str
    enabled: bool
    keyword: str
    description: str
    max_pages: int
    personal_only: bool
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: str
    ai_prompt_criteria_file: str
    is_running: Optional[bool] = False
    generating_ai_criteria: Optional[bool] = False


class TaskUpdate(BaseModel):
    task_name: Optional[str] = None
    enabled: Optional[bool] = None
    keyword: Optional[str] = None
    description: Optional[str] = None
    max_pages: Optional[int] = None
    personal_only: Optional[bool] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    cron: Optional[str] = None
    ai_prompt_base_file: Optional[str] = None
    ai_prompt_criteria_file: Optional[str] = None
    is_running: Optional[bool] = None
    generating_ai_criteria: Optional[bool] = None


class TaskGenerateRequest(BaseModel):
    task_name: str
    keyword: str
    description: str
    personal_only: bool = True
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    max_pages: int = 3
    cron: Optional[str] = None


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
    PCURL_TO_MOBILE: Optional[bool] = True
    NOTIFY_AFTER_TASK_COMPLETE: Optional[bool] = True


class NewPromptRequest(BaseModel):
    filename: str
    content: str


class DeleteResultItemRequest(BaseModel):
    filename: str
    item: dict


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
