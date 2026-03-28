from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

class SystemConfig(BaseModel):
    name: str = Field(..., description="Unique identifier, matches repo folder name")
    version: str = Field("0.1.0", description="Semantic version of the plug‑in")
    enabled: bool = True
    # free‑form plug‑in specific settings – validated against its own JSON‑Schema if present
    settings: Dict[str, Any] = Field(default_factory=dict)
    # execution preferences
    launch_mode: Literal["subprocess", "asyncio"] = "subprocess"
    env: Dict[str, str] = Field(default_factory=dict)
