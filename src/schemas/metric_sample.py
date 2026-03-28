from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict

class MetricSample(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system: str
    name: str                     # e.g., "loss", "fps"
    value: float
    tags: Dict[str, str] = Field(default_factory=dict)
