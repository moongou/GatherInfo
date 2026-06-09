"""Search tool config schemas."""
from pydantic import BaseModel, Field
from .common import IsoDT


class SearchToolConfigCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    tool_type: str = Field(default="web_search")
    is_active: bool = True
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool = False


class SearchToolConfigUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool | None = None


class SearchToolConfigOut(BaseModel):
    id: str
    name: str
    tool_type: str
    is_active: bool
    config_json: dict | None = None
    api_key_ref: str | None = None
    is_default: bool = False
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}
