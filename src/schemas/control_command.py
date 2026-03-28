from pydantic import BaseModel, Field
from typing import Literal, Dict, Any

class ControlCommand(BaseModel):
    action: Literal["start", "stop", "tune", "pause", "resume"]
    payload: Dict[str, Any] = Field(default_factory=dict)
