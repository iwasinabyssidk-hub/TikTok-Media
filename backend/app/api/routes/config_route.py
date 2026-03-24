from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/config", tags=["config"])

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


def _load() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save(data: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


@router.get("")
async def get_config() -> dict[str, Any]:
    return _load()


@router.put("")
async def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    from app.core.job_manager import job_manager

    running = any(j.status == "running" for j in job_manager.all())
    if running:
        raise HTTPException(status_code=409, detail="Cannot update config while a job is running")
    current = _load()
    _deep_merge(current, updates)
    _save(current)
    return current


def _deep_merge(base: dict, updates: dict) -> None:
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
