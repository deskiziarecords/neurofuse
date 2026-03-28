# file: src/utils/storage.py
import os
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Union, Optional
from datetime import datetime

ARTIFACT_ROOT = Path("artifacts")

async def save_artifact(plugin_name: str, filename: str, content: Union[str, bytes]) -> str:
    """Save an artifact to the local filesystem and return its relative path."""
    dest_dir = ARTIFACT_ROOT / plugin_name / datetime.utcnow().strftime("%Y-%m-%d")
    await aiofiles.os.makedirs(dest_dir, exist_ok=True)

    file_path = dest_dir / filename
    mode = "wb" if isinstance(content, bytes) else "w"
    async with aiofiles.open(file_path, mode) as f:
        await f.write(content)

    return str(file_path.relative_to(ARTIFACT_ROOT.parent))

async def list_artifacts(plugin_name: Optional[str] = None):
    """List relative paths of all saved artifacts."""
    if not ARTIFACT_ROOT.exists():
        return []

    search_path = ARTIFACT_ROOT / plugin_name if plugin_name else ARTIFACT_ROOT
    artifacts = []
    for root, dirs, files in os.walk(search_path):
        for f in files:
            p = Path(root) / f
            artifacts.append(str(p.relative_to(ARTIFACT_ROOT.parent)))
    return artifacts
