from __future__ import annotations

import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import pandas as pd

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SERVICES_XLSX = os.path.abspath(os.path.join(MODULE_DIR, "..", "data", "services.xlsx"))
WORKSPACE_SERVICES_XLSX = os.path.abspath(os.path.join(MODULE_DIR, "..", "..", "data", "services.xlsx"))
REQUIRED_COLUMNS = ["id", "name", "category", "keywords", "description"]

COLUMN_ALIASES = {
    "id": ["id", "service_id", "xizmat_id", "ид", "номер"],
    "name": ["name", "service_name", "xizmat nomi", "xizmat", "название", "услуга"],
    "category": ["category", "soha", "segment", "sector", "категория", "сфера"],
    "keywords": ["keywords", "keyword", "kalit so'zlar", "ключевые слова"],
    "description": ["description", "desc", "ta'rif", "izoh", "mas'ul tashkilot", "ответственная организация"],
}

_SERVICES_CACHE: Optional[List[Dict[str, Any]]] = None
_SERVICES_CACHE_SOURCE: Optional[str] = None
_SERVICES_CACHE_MTIME: Optional[float] = None

CYRILLIC_TO_LATIN = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "j",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "x",
        "ц": "s",
        "ч": "ch",
        "ш": "sh",
        "щ": "sh",
        "ъ": "",
        "ы": "i",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "қ": "q",
        "ғ": "g",
        "ў": "o",
        "ҳ": "h",
    }
)

QUERY_SYNONYMS: Dict[str, List[str]] = {
    "passport": ["pasport", "паспорт"],
    "pasport": ["passport", "паспорт"],
    "паспорт": ["passport", "pasport"],
    "birth": ["tugildi", "tugilish", "bola", "рождение"],
    "tugildi": ["birth", "tugilish", "bola"],
    "tugilish": ["birth", "tugildi", "bola"],
    "рождение": ["birth", "tugildi", "bola"],
    "child": ["birth", "newborn", "tugildi", "tugilish", "bola", "ребенок", "родился"],
    "children": ["child", "birth", "bola", "ребенок"],
    "born": ["birth", "newborn", "tugildi", "tugilish", "родился", "рождение"],
    "newborn": ["birth", "born", "tugildi", "bola", "ребенок"],
    "baby": ["child", "birth", "newborn", "bola", "ребенок"],
    "ребенок": ["child", "birth", "родился", "рождение", "bola", "tugildi"],
    "ребёнок": ["child", "birth", "родился", "рождение", "bola", "tugildi"],
    "родился": ["born", "birth", "ребенок", "рождение", "tugildi", "bola"],
    "родилась": ["born", "birth", "ребенок", "рождение", "tugildi", "bola"],
    "рожд": ["birth", "born", "ребенок", "родился", "tugildi"],
    "pension": ["pensiya", "nafaqa", "пенсия"],
    "pensiya": ["pension", "nafaqa", "пенсия"],
    "nafaqa": ["pension", "pensiya", "пенсия"],
    "пенсия": ["pension", "pensiya", "nafaqa"],
    "notary": ["notarius", "нотариус"],
    "notarius": ["notary", "нотариус"],
    "нотариус": ["notary", "notarius"],
    "home": ["uy", "house", "дом"],
    "house": ["uy", "home", "дом"],
    "uy": ["home", "house", "дом"],
    "дом": ["home", "house", "uy"],
}


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    no_punctuation = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    collapsed = re.sub(r"\s+", " ", no_punctuation)
    return collapsed.strip()


def _split_words(text: str) -> List[str]:
    normalized = _normalize_text(text)
    return [word for word in normalized.split(" ") if word]


def _to_latin(text: str) -> str:
    return text.translate(CYRILLIC_TO_LATIN)


def _expand_query_terms(words: List[str]) -> List[str]:
    expanded: List[str] = []
    for word in words:
        normalized_word = _normalize_text(word)
        if not normalized_word:
            continue

        expanded.append(normalized_word)

        latin = _normalize_text(_to_latin(normalized_word))
        if latin and latin != normalized_word:
            expanded.append(latin)

            for synonym in QUERY_SYNONYMS.get(latin, []):
                normalized_synonym = _normalize_text(synonym)
                if normalized_synonym:
                    expanded.append(normalized_synonym)

        for synonym in QUERY_SYNONYMS.get(normalized_word, []):
            normalized_synonym = _normalize_text(synonym)
            if normalized_synonym:
                expanded.append(normalized_synonym)

    # Preserve order and remove duplicates.
    return list(dict.fromkeys(expanded))


def _word_matches_token(word: str, token: str) -> bool:
    if not word or not token:
        return False

    min_len = min(len(word), len(token))
    if min_len < 3:
        return word == token

    if word == token:
        return True

    # Containment checks are useful for inflections, but require meaningful token length.
    if min_len >= 4 and word in token:
        return True

    return SequenceMatcher(None, word, token).ratio() >= 0.84


def _parse_keywords(raw_keywords: Any) -> List[str]:
    if pd.isna(raw_keywords):
        return []

    parts = str(raw_keywords).split(",")
    normalized = [part.strip().lower() for part in parts if part and part.strip()]
    return normalized


def _build_service_description(name: str, category: str, provider: str) -> str:
    clean_name = str(name).strip() or "Service"
    clean_category = str(category).strip() or "General"
    clean_provider = str(provider).strip()

    if clean_provider:
        return (
            f"Service area: {clean_category}. "
            f"This service helps with '{clean_name}'. "
            f"Responsible organization: {clean_provider}."
        )

    return (
        f"Service area: {clean_category}. "
        f"This service helps with '{clean_name}'."
    )


def _normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return ""
    return value


def _resolve_column_mapping(columns: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for target, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in columns:
                mapping[target] = alias
                break
    return mapping


def _build_keywords_from_name(name: str) -> List[str]:
    words = _split_words(name)
    unique_words = list(dict.fromkeys(words))
    return unique_words[:8]


def get_services(file_path: Optional[str] = None, force_reload: bool = False) -> List[Dict[str, Any]]:
    global _SERVICES_CACHE
    global _SERVICES_CACHE_SOURCE
    global _SERVICES_CACHE_MTIME

    if file_path:
        source_path = os.path.abspath(file_path)
    else:
        if os.path.exists(DEFAULT_SERVICES_XLSX):
            source_path = DEFAULT_SERVICES_XLSX
        elif os.path.exists(WORKSPACE_SERVICES_XLSX):
            source_path = WORKSPACE_SERVICES_XLSX
        else:
            source_path = DEFAULT_SERVICES_XLSX

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Services Excel file not found: {source_path}")

    current_mtime = os.path.getmtime(source_path)
    if (
        _SERVICES_CACHE is not None
        and not force_reload
        and _SERVICES_CACHE_SOURCE == source_path
        and _SERVICES_CACHE_MTIME == current_mtime
    ):
        return [dict(item) for item in _SERVICES_CACHE]

    try:
        dataframe = pd.read_excel(source_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to read services Excel file: {source_path}") from exc

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]

    column_mapping = _resolve_column_mapping(list(dataframe.columns))

    # For minimal spreadsheets, only id/name/category are required.
    required_base = ["id", "name", "category"]
    missing_base = [column for column in required_base if column not in column_mapping]
    if missing_base:
        missing = ", ".join(missing_base)
        raise ValueError(f"Missing required columns in services Excel file: {missing}")

    records: List[Dict[str, Any]] = []
    for row in dataframe.to_dict(orient="records"):
        name = str(_normalize_value(row.get(column_mapping["name"]))).strip()
        category = str(_normalize_value(row.get(column_mapping["category"]))).strip()

        raw_keywords = row.get(column_mapping["keywords"]) if "keywords" in column_mapping else ""
        parsed_keywords = _parse_keywords(raw_keywords)
        keywords = parsed_keywords if parsed_keywords else _build_keywords_from_name(name)

        raw_description = row.get(column_mapping["description"]) if "description" in column_mapping else ""
        description_source = str(_normalize_value(raw_description)).strip()

        # In current Excel, description alias often points to "Mas'ul tashkilot".
        # Build a user-readable description instead of showing only organization name.
        description_alias = str(column_mapping.get("description", "")).strip().lower()
        is_provider_column = description_alias in {"mas'ul tashkilot", "ответственная организация"}
        if is_provider_column:
            description = _build_service_description(name=name, category=category, provider=description_source)
        else:
            description = description_source or _build_service_description(name=name, category=category, provider="")

        record = {
            "id": _normalize_value(row.get(column_mapping["id"])),
            "name": name,
            "category": category,
            "keywords": keywords,
            "description": description,
            "provider": description_source if is_provider_column else "",
        }
        records.append(record)

    _SERVICES_CACHE = records
    _SERVICES_CACHE_SOURCE = source_path
    _SERVICES_CACHE_MTIME = current_mtime
    return [dict(item) for item in _SERVICES_CACHE]


def rank_services(query: str, services: List[Dict[str, Any]]) -> List[tuple[int, Dict[str, Any]]]:
    words = _expand_query_terms(_split_words(query))
    if not words or not services:
        return []

    scored_results: List[tuple[int, Dict[str, Any]]] = []

    for service in services:
        score = 0
        normalized_name = _normalize_text(str(service.get("name", "")))
        name_tokens = _split_words(normalized_name)
        normalized_category = _normalize_text(str(service.get("category", "")))
        category_tokens = _split_words(normalized_category)
        normalized_keywords = [_normalize_text(str(keyword)) for keyword in service.get("keywords", [])]
        keyword_tokens = [token for keyword in normalized_keywords for token in _split_words(keyword)]

        for word in words:
            keyword_match = any(
                _word_matches_token(word, keyword) for keyword in normalized_keywords if keyword
            )
            if not keyword_match:
                keyword_match = any(_word_matches_token(word, token) for token in keyword_tokens)
            if keyword_match:
                score += 2

            name_match = _word_matches_token(word, normalized_name) or any(
                _word_matches_token(word, token) for token in name_tokens
            )
            if name_match:
                score += 1

            category_match = _word_matches_token(word, normalized_category) or any(
                _word_matches_token(word, token) for token in category_tokens
            )
            if category_match:
                score += 1

        if score > 0:
            scored_results.append((score, service))

    scored_results.sort(key=lambda item: (item[0], str(item[1].get("name", "")).lower()), reverse=True)
    return scored_results


def search_services(query: str, services: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    ranked = rank_services(query=query, services=services)
    top_results = ranked[: max(1, min(limit, 10))]
    return [dict(service) for _, service in top_results]


def _extract_required_documents(description: str) -> List[str]:
    normalized = description.strip()
    if not normalized:
        return ["Check official service portal for required documents"]

    direct_patterns = [
        r"required documents?\s*:\s*([^\.\n]+)",
        r"documents? needed\s*:\s*([^\.\n]+)",
        r"hujjatlar\s*:\s*([^\.\n]+)",
    ]

    for pattern in direct_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            chunk = match.group(1)
            parts = [item.strip(" .;:-") for item in re.split(r",|;|/", chunk)]
            extracted = [item for item in parts if item]
            if extracted:
                return extracted[:3]

    doc_terms = [
        "passport",
        "id",
        "certificate",
        "extract",
        "application",
        "statement",
        "proof",
        "contract",
    ]

    lowered = normalized.lower()
    discovered: List[str] = []
    for term in doc_terms:
        if term in lowered:
            discovered.append(term.title())

    if discovered:
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(discovered))[:3]

    return ["Check official service portal for required documents"]


def _extract_documents_from_name_and_category(name: str, category: str) -> List[str]:
    blob = _normalize_text(f"{name} {category}")
    docs: List[str] = []

    if any(token in blob for token in ["passport", "pasport", "паспорт", "id", "identity"]):
        docs.append("Passport/ID")
    if any(token in blob for token in ["birth", "tug", "рожд", "ребен", "guvohnoma"]):
        docs.append("Birth certificate")
    if any(token in blob for token in ["home", "house", "housing", "uy", "dom", "жиль", "kadastr"]):
        docs.append("Property/housing documents")
    if any(token in blob for token in ["pension", "pensiya", "пенси", "nafaqa"]):
        docs.append("Employment and pension records")
    if any(token in blob for token in ["notary", "notarius", "нотариус", "contract", "shartnoma"]):
        docs.append("Application and supporting contracts")

    if not docs:
        docs = ["Application form", "Passport/ID", "Additional supporting documents"]

    return docs[:3]


def _infer_stage(category: str, name: str, description: str) -> str:
    normalized_category = _normalize_text(category)
    normalized = " ".join([normalized_category, _normalize_text(name), _normalize_text(description)])

    if any(token in normalized_category for token in ["registr", "ro'yxat", "регистра"]):
        return "registration"
    if any(token in normalized_category for token in ["document", "certif", "extract", "hujjat", "документ"]):
        return "document"
    if any(token in normalized_category for token in ["benefit", "allowance", "subsid", "nafaqa", "пособ"]):
        return "benefit"

    if any(token in normalized for token in ["register", "registration", "registry", "ro'yxat", "регистра"]):
        return "registration"
    if any(token in normalized for token in ["certificate", "extract", "document", "hujjat", "документ"]):
        return "document"
    if any(token in normalized for token in ["benefit", "allowance", "subsid", "nafaqa", "пособ"]):
        return "benefit"
    if any(token in normalized for token in ["health", "clinic", "vaccin", "doctor", "tibb", "sog'liq", "здоров", "поликл"]):
        return "healthcare"
    return "additional"


def _format_scenario_title(query: str) -> str:
    normalized = _normalize_text(query)
    if not normalized:
        return "Life situation"

    if any(token in normalized for token in ["tug", "bola", "birth", "newborn", "рожд"]):
        return "Bola tug'ilishi"
    if any(token in normalized for token in ["uy", "house", "home", "housing", "sotib", "mortgage", "дом", "жиль"]):
        return "Uy sotib olish"
    if any(token in normalized for token in ["pension", "pensiya", "nafaqa", "пенси"]):
        return "Nafaqaga chiqish"

    return query.strip().capitalize()


def _section_title_for_stage(stage: str) -> str:
    mapping = {
        "registration": "Registration",
        "document": "Documentation",
        "benefit": "Benefits",
        "healthcare": "Healthcare",
        "additional": "Additional",
    }
    return mapping.get(stage, "Additional")


def _infer_form_fields(category: str, name: str, description: str, required_documents: List[str]) -> Dict[str, bool]:
    normalized = " ".join(
        [
            _normalize_text(category),
            _normalize_text(name),
            _normalize_text(description),
            _normalize_text(" ".join(required_documents or [])),
        ]
    )

    def has_any(tokens: List[str]) -> bool:
        return any(token in normalized for token in tokens)

    queue_related = has_any(["queue", "appointment", "booking", "slot", "navbat", "очеред"])
    family_related = has_any(
        [
            "family",
            "spouse",
            "children",
            "child",
            "dependent",
            "household",
            "marriage",
            "guardian",
            "сем",
            "дет",
            "oila",
            "farzand",
        ]
    )
    address_related = has_any(
        [
            "address",
            "residence",
            "domicile",
            "registration",
            "property",
            "housing",
            "house",
            "home",
            "manzil",
            "uy",
            "адрес",
            "пропис",
            "квартир",
            "дом",
        ]
    )
    birth_related = has_any(
        [
            "birth",
            "born",
            "newborn",
            "minor",
            "date of birth",
            "tug",
            "bola",
            "рожд",
            "ребен",
        ]
    )
    passport_related = has_any(["passport", "pasport", "identity", "id card", "паспорт", "удостовер"])

    full_name = True
    family_members = family_related
    birth_date = birth_related or family_members
    address = address_related

    # Queue-only requests should stay minimal and avoid unnecessary personal details.
    passport_number = passport_related or (not queue_related)

    return {
        "full_name": full_name,
        "passport_number": passport_number,
        "birth_date": birth_date,
        "address": address,
        "family_members": family_members,
    }


def build_scenario(query: str, matched_services: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not matched_services:
        return {"scenario": "dynamic", "scenario_display": "Life situation", "sections": [], "steps": []}

    stage_priority = {"registration": 0, "document": 1, "benefit": 2, "healthcare": 3, "additional": 4}

    grouped_by_stage: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for service in matched_services:
        category = str(service.get("category", "")).strip()
        name = str(service.get("name", "")).strip() or "Service"
        description = str(service.get("description", "")).strip()
        stage = _infer_stage(category=category, name=name, description=description)

        grouped_by_stage[stage].append(
            {
                "name": name,
                "description": description,
                "category": category or stage,
            }
        )

    sections: List[Dict[str, Any]] = []
    flattened_steps: List[Dict[str, Any]] = []
    step_id = 1

    for stage in sorted(grouped_by_stage.keys(), key=lambda item: stage_priority.get(item, 99)):
        stage_services = grouped_by_stage[stage]
        section_steps: List[Dict[str, Any]] = []

        for service in stage_services:
            description = service["description"]
            required_documents = _extract_required_documents(description)
            if required_documents == ["Check official service portal for required documents"]:
                required_documents = _extract_documents_from_name_and_category(
                    name=service["name"],
                    category=service["category"],
                )
            step = {
                "id": step_id,
                "service_name": service["name"],
                "title": service["name"],
                "description": description,
                "category": service["category"],
                "required_documents": required_documents,
                "estimated_time": "1-3 days",
                "form_fields": _infer_form_fields(
                    category=service["category"],
                    name=service["name"],
                    description=description,
                    required_documents=required_documents,
                ),
            }
            section_steps.append(step)
            flattened_steps.append(step)
            step_id += 1

            if len(flattened_steps) >= 10:
                break

        if section_steps:
            sections.append(
                {
                    "title": _section_title_for_stage(stage),
                    "steps": section_steps,
                }
            )

        if len(flattened_steps) >= 10:
            break

    return {
        "scenario": "dynamic",
        "scenario_display": _format_scenario_title(query),
        "sections": sections,
        "steps": flattened_steps,
    }


def _first_sentence(text: str) -> str:
    cleaned = str(text).strip()
    if not cleaned:
        return "No detailed description is available."

    sentence = re.split(r"[.!?]", cleaned)[0].strip()
    if not sentence:
        return "No detailed description is available."
    return sentence


def _common_suffix_length(a: str, b: str) -> int:
    max_len = min(len(a), len(b))
    length = 0
    for index in range(1, max_len + 1):
        if a[-index] == b[-index]:
            length += 1
        else:
            break
    return length


def _service_name_similarity(name_a: str, name_b: str) -> float:
    normalized_a = _normalize_text(name_a)
    normalized_b = _normalize_text(name_b)
    if not normalized_a or not normalized_b:
        return 0.0

    sequence_score = SequenceMatcher(None, normalized_a, normalized_b).ratio()
    words_a = set(_split_words(normalized_a))
    words_b = set(_split_words(normalized_b))
    overlap_score = (len(words_a.intersection(words_b)) / max(len(words_a.union(words_b)), 1)) if words_a and words_b else 0

    suffix_len = _common_suffix_length(normalized_a, normalized_b)
    suffix_bonus = 0.2 if suffix_len >= 4 else 0.0

    return max(sequence_score, overlap_score) + suffix_bonus


def find_similar_services(services: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    if not services:
        return []

    pairs: List[tuple[float, Dict[str, str]]] = []

    for left_index in range(len(services)):
        for right_index in range(left_index + 1, len(services)):
            left = services[left_index]
            right = services[right_index]

            name_left = str(left.get("name", "")).strip()
            name_right = str(right.get("name", "")).strip()
            if not name_left or not name_right:
                continue

            similarity_score = _service_name_similarity(name_left, name_right)
            if similarity_score < 0.62:
                continue

            left_focus = _first_sentence(str(left.get("description", "")))
            right_focus = _first_sentence(str(right.get("description", "")))

            explanation = (
                f"{name_left} focuses on: {left_focus}. "
                f"{name_right} focuses on: {right_focus}. "
                "Choose the one that matches your exact goal."
            )

            pairs.append(
                (
                    similarity_score,
                    {
                        "service1": name_left,
                        "service2": name_right,
                        "explanation": explanation,
                    },
                )
            )

    pairs.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in pairs[:10]]
