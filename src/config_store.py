# file: src/config_store.py
import yaml, os
from pathlib import Path
from typing import List, Optional
from .schemas.system_config import SystemConfig

# Base relative to repo root
CONFIG_DIR = Path("configs")

class ConfigStore:
    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root)
        self.config_dir = self.root / CONFIG_DIR
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.config_dir / f"{name}.yaml"

    def get(self, name: str) -> SystemConfig:
        path = self._path(name)
        if not path.exists():
            raise FileNotFoundError(f"No config for {name}")
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return SystemConfig(**data)

    def upsert(self, cfg: SystemConfig) -> None:
        path = self._path(cfg.name)
        with path.open("w") as f:
            # Pydantic v2 use model_dump
            yaml.dump(cfg.model_dump(), f, sort_keys=False)

    def list_all(self) -> List[SystemConfig]:
        return [self.get(p.stem) for p in self.config_dir.glob("*.yaml")]

class SupabaseConfigStore(ConfigStore):
    """
    Synchronizes config with Supabase for distributed state.
    Falls back to local YAML if no connection.
    """
    def __init__(self, url: str, key: str, repo_root: str | Path = "."):
        super().__init__(repo_root)
        from supabase import create_client, Client
        try:
            self.client: Optional[Client] = create_client(url, key)
        except:
            self.client = None

    def get(self, name: str) -> SystemConfig:
        if self.client:
            try:
                res = self.client.table("configs").select("*").eq("name", name).execute()
                if res.data:
                    return SystemConfig(**res.data[0]["payload"])
            except:
                pass
        return super().get(name)

    def upsert(self, cfg: SystemConfig) -> None:
        super().upsert(cfg)
        if self.client:
            try:
                self.client.table("configs").upsert({
                    "name": cfg.name,
                    "payload": cfg.model_dump()
                }).execute()
            except:
                pass
