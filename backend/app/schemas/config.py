from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ModelConfigBase(BaseModel):
    name: str
    base_url: str
    api_key: str
    model_name: str
    role: str  # "analyze" | "import"
    max_output_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95


class ModelConfigCreate(ModelConfigBase):
    pass


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


class ModelConfigResponse(BaseModel):
    id: int
    name: str
    base_url: str
    model_name: str
    role: str
    is_active: bool
    max_output_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    api_key_masked: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptBase(BaseModel):
    prompt_type: str
    title: str
    content: str


class PromptUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class PromptResponse(BaseModel):
    id: int
    prompt_type: str
    title: str
    content: str
    updated_at: datetime

    class Config:
        from_attributes = True


class SpeechConfigBase(BaseModel):
    provider: str  # "web_speech" | "whisper"
    whisper_api_url: Optional[str] = None
    whisper_api_key: Optional[str] = None
    whisper_model: Optional[str] = None


class SpeechConfigUpdate(BaseModel):
    provider: Optional[str] = None
    whisper_api_url: Optional[str] = None
    whisper_api_key: Optional[str] = None
    whisper_model: Optional[str] = None


class SpeechConfigResponse(SpeechConfigBase):
    id: int
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class FetchModelsRequest(BaseModel):
    base_url: str
    api_key: str


class FetchModelsResponse(BaseModel):
    models: list[str]
