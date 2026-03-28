# file: src/schemas/scenario.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Union, Optional

class ScenarioEvent(BaseModel):
    timestamp: float  # Relative offset in seconds
    system: str
    action: str  # e.g., "start", "stop", "tune"
    payload: Dict[str, Any] = Field(default_factory=dict)

class TriggerCondition(BaseModel):
    source_system: str
    metric_name: str
    operator: str  # ">", "<", "==", "!="
    threshold: float

class TriggeredAction(BaseModel):
    target_system: str
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)

class Scenario(BaseModel):
    name: str
    timeline: List[ScenarioEvent] = Field(default_factory=list)
    triggers: List[Dict[str, Union[TriggerCondition, TriggeredAction]]] = Field(default_factory=list)
