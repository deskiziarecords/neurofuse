# file: src/schemas/payload.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union
from datetime import datetime

class Payload(BaseModel):
    """
    Represents a data artifact produced by a system.
    Can be a small blob (bytes/string) or a URI to larger storage.
    """
    id: str
    plugin_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    mime_type: str = "application/octet-stream"
    data: Optional[Union[str, bytes]] = None
    uri: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
