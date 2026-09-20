"""Service JSON file persistence under data/services/."""
from __future__ import annotations

import json
from pathlib import Path

from app.models.service import Service
from app.persistence.paths import SERVICES_DIR


def list_service_ids() -> list[str]:
    return [p.stem for p in sorted(SERVICES_DIR.glob("*.json"))]


def load_service(service_id: str) -> Service:
    path = SERVICES_DIR / f"{service_id}.json"
    return load_service_from_path(path)


def load_service_from_path(path: str | Path) -> Service:
    return Service.from_json_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_service(service: Service) -> None:
    SERVICES_DIR.mkdir(parents=True, exist_ok=True)
    path = SERVICES_DIR / f"{service.id}.json"
    path.write_text(json.dumps(service.to_json_dict(), indent=2), encoding="utf-8")


def delete_service(service_id: str) -> None:
    path = SERVICES_DIR / f"{service_id}.json"
    path.unlink(missing_ok=True)


def save_service_to_path(service: Service, path: str) -> None:
    """Save service to a specific file path."""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(service.to_json_dict(), indent=2), encoding="utf-8")
