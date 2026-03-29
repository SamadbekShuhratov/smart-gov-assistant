from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import pandas as pd

# FastAPI project structure: backend/app/data_loader.py -> ../data/services.xlsx
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL_PATH = os.path.abspath(os.path.join(MODULE_DIR, "..", "..", "data", "services.xlsx"))
LEGACY_EXCEL_PATH = os.path.abspath(os.path.join(MODULE_DIR, "..", "data", "services.xlsx"))
REQUIRED_COLUMNS = ["id", "name", "category", "keywords", "description"]

_SERVICES_CACHE: Optional[List[Dict[str, Any]]] = None


def _normalize_keywords(value: Any) -> List[str]:
    if pd.isna(value):
        return []

    return [
        keyword.strip().lower()
        for keyword in str(value).split(",")
        if keyword and keyword.strip()
    ]


def get_services() -> List[Dict[str, Any]]:
    global _SERVICES_CACHE

    if _SERVICES_CACHE is not None:
        print("[data_loader] Returning services from memory cache")
        return [dict(item) for item in _SERVICES_CACHE]

    source_path = DEFAULT_EXCEL_PATH
    if not os.path.exists(source_path) and os.path.exists(LEGACY_EXCEL_PATH):
        source_path = LEGACY_EXCEL_PATH

    print(f"[data_loader] Loading Excel file: {source_path}")

    if not os.path.exists(source_path):
        print(f"[data_loader] File not found: {source_path}")
        raise FileNotFoundError(f"Services Excel file not found: {source_path}")

    try:
        dataframe = pd.read_excel(source_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[data_loader] Failed to read Excel: {exc}")
        raise

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        print(f"[data_loader] Missing required columns: {', '.join(missing_columns)}")
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    records: List[Dict[str, Any]] = []
    for row in dataframe[REQUIRED_COLUMNS].to_dict(orient="records"):
        records.append(
            {
                "id": "" if pd.isna(row.get("id")) else row.get("id"),
                "name": "" if pd.isna(row.get("name")) else str(row.get("name")).strip(),
                "category": "" if pd.isna(row.get("category")) else str(row.get("category")).strip(),
                "keywords": _normalize_keywords(row.get("keywords")),
                "description": ""
                if pd.isna(row.get("description"))
                else str(row.get("description")).strip(),
            }
        )

    _SERVICES_CACHE = records
    print(f"[data_loader] Loaded {_SERVICES_CACHE.__len__()} services into memory cache")
    return [dict(item) for item in _SERVICES_CACHE]
