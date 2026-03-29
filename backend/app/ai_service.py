import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from .translator import translate_text


load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)

_PREFERRED_MODELS = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

_TERM_TRANSLATIONS = {
    "en": {
        "Asosiy rasmiy bosqichlar": "Required official steps",
        "Hujjatlar": "Documents",
        "Yo'l xaritasi va xizmatlar": "Roadmap & Services",
    },
    "ru": {
        "Asosiy rasmiy bosqichlar": "Основные официальные шаги",
        "Hujjatlar": "Документы",
        "Yo'l xaritasi va xizmatlar": "Дорожная карта и услуги",
    },
}

_WORD_TRANSLATIONS = {
    "en": {
        "xizmat": "service",
        "xizmatlari": "services",
        "davlat": "state",
        "hujjat": "document",
        "hujjatlar": "documents",
        "qabul": "acceptance",
        "qilish": "processing",
        "ariza": "application",
        "berish": "issuance",
        "olish": "obtaining",
        "ruxsatnoma": "permit",
        "royxat": "register",
        "royxatdan": "registration",
        "otkazish": "recording",
        "tugilganlik": "birth",
        "guvohnoma": "certificate",
        "pasport": "passport",
        "fuqaro": "citizen",
        "shaxs": "person",
        "manzil": "address",
        "bola": "child",
        "nafaqa": "benefit",
        "nikoh": "marriage",
        "ish": "employment",
        "uy": "housing",
        "soliq": "tax",
        "kadastr": "cadastre",
        "adliya": "justice",
        "vazirligi": "ministry",
        "respublikasi": "republic",
        "ozbekiston": "uzbekistan",
        "orqali": "via",
        "yagona": "single",
        "portal": "portal",
    },
    "ru": {
        "xizmat": "услуга",
        "xizmatlari": "услуги",
        "davlat": "государственный",
        "hujjat": "документ",
        "hujjatlar": "документы",
        "qabul": "прием",
        "qilish": "оформление",
        "ariza": "заявление",
        "berish": "выдача",
        "olish": "получение",
        "ruxsatnoma": "разрешение",
        "royxat": "реестр",
        "royxatdan": "регистрация",
        "otkazish": "оформление",
        "tugilganlik": "рождение",
        "guvohnoma": "свидетельство",
        "pasport": "паспорт",
        "fuqaro": "гражданин",
        "shaxs": "лицо",
        "manzil": "адрес",
        "bola": "ребенок",
        "nafaqa": "пособие",
        "nikoh": "брак",
        "ish": "трудоустройство",
        "uy": "жилье",
        "soliq": "налог",
        "kadastr": "кадастр",
        "adliya": "юстиция",
        "vazirligi": "министерство",
        "respublikasi": "республика",
        "ozbekiston": "узбекистан",
        "orqali": "через",
        "yagona": "единый",
        "portal": "портал",
    },
}

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "what",
    "when",
    "where",
    "which",
    "how",
    "who",
    "why",
    "you",
    "your",
    "need",
    "after",
    "before",
    "about",
    "can",
    "only",
    "help",
    "have",
    "has",
    "had",
    "was",
    "were",
    "are",
    "is",
    "am",
    "to",
    "of",
    "in",
    "on",
    "a",
    "an",
    "it",
    "i",
    "we",
    "me",
    "my",
    "our",
}

_L10N = {
    "en": {
        "unrelated": "I can only help with government services and official procedures.",
        "no_exact": "We could not find exact services, but here are closest matches.",
        "answer_prefix": "Based on your situation, start with these official services:",
        "reason_match": "Relevant to your life situation and required official steps.",
        "reason_doc": "Document-related service needed in this process.",
        "section_main": "Required official steps",
        "section_docs": "Documents",
        "dynamic_section": "Roadmap & Services",
        "portal_header": "my.gov.uz - Government Services Portal of Uzbekistan",
        "profile": "User Profile",
        "profile_content": "Sign in to view your profile details",
    },
    "uz": {
        "unrelated": "Men faqat davlat xizmatlari va rasmiy tartiblar bo'yicha yordam bera olaman.",
        "no_exact": "Aniq xizmat topilmadi, lekin eng yaqin mos xizmatlar ko'rsatildi.",
        "answer_prefix": "Holatingiz bo'yicha quyidagi rasmiy xizmatlardan boshlang:",
        "reason_match": "Hayotiy holatingiz va rasmiy bosqichlarga mos.",
        "reason_doc": "Jarayon uchun zarur hujjatga oid xizmat.",
        "section_main": "Asosiy rasmiy bosqichlar",
        "section_docs": "Hujjatlar",
        "dynamic_section": "Yo'l xaritasi va xizmatlar",
        "portal_header": "my.gov.uz - O'zbekiston davlat xizmatlari portali",
        "profile": "Foydalanuvchi profili",
        "profile_content": "Profil ma'lumotlarini ko'rish uchun tizimga kiring",
    },
    "ru": {
        "unrelated": "Я могу помогать только по государственным услугам и официальным процедурам.",
        "no_exact": "Точные услуги не найдены, но показаны ближайшие подходящие варианты.",
        "answer_prefix": "По вашей ситуации начните со следующих официальных услуг:",
        "reason_match": "Соответствует вашей жизненной ситуации и обязательным шагам.",
        "reason_doc": "Услуга связана с необходимыми документами.",
        "section_main": "Основные официальные шаги",
        "section_docs": "Документы",
        "dynamic_section": "Дорожная карта и услуги",
        "portal_header": "my.gov.uz - Портал государственных услуг Республики Узбекистан",
        "profile": "Профиль пользователя",
        "profile_content": "Войдите, чтобы увидеть данные профиля",
    },
}

_INTENT_HINTS = {
    "birth": [
        "birth",
        "born",
        "child",
        "children",
        "newborn",
        "baby",
        "registration",
        "benefit",
        "bola",
        "tug",
        "nafaqa",
        "ребен",
        "рожд",
        "родил",
        "родилась",
        "пособ",
    ],
    "housing": ["housing", "home", "house", "mortgage", "registry", "property", "uy", "kadastr", "ипотек", "жиль", "реестр"],
    "pension": ["pension", "retire", "retirement", "benefit", "pensiya", "nafaqa", "пенси", "пенсию", "пособ"],
    "marriage": ["marriage", "wedding", "nikoh", "oila", "брак", "семья"],
    "work": ["work", "job", "employment", "labor", "ish", "bandlik", "работ", "труд"],
}

_DOC_HINTS = {
    "document",
    "documents",
    "certificate",
    "passport",
    "registration",
    "hujjat",
    "hujjatlar",
    "guvohnoma",
    "pasport",
    "документ",
    "документы",
    "свидетель",
    "паспорт",
    "справк",
}

_DOMAIN_KEYWORDS = {
    "government",
    "service",
    "services",
    "document",
    "documents",
    "application",
    "applications",
    "official",
    "procedure",
    "procedures",
    "birth",
    "born",
    "child",
    "children",
    "newborn",
    "baby",
    "marriage",
    "pension",
    "retire",
    "retirement",
    "housing",
    "work",
    "passport",
    "certificate",
    "register",
    "registration",
    "benefit",
    "benefits",
    "gov",
    "state",
    "xizmat",
    "xizmatlar",
    "hujjat",
    "hujjatlar",
    "ariza",
    "rasmiy",
    "tartib",
    "tug",
    "nikoh",
    "pensiya",
    "nafaq",
    "uy",
    "ish",
    "pasport",
    "guvohnoma",
    "davlat",
    "услуга",
    "услуги",
    "документ",
    "документы",
    "заявка",
    "заявление",
    "официаль",
    "процедур",
    "рожд",
    "родил",
    "родилась",
    "ребен",
    "брак",
    "пенси",
    "жиль",
    "работ",
    "паспорт",
    "справк",
    "гос",
}


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    return " ".join(lowered.split())


def _tokenize(text: str) -> set[str]:
    return {token for token in _normalize_text(text).split() if len(token) >= 3 and token not in _STOPWORDS}


def _text(lang: str, key: str) -> str:
    return _L10N.get(lang, _L10N["en"]).get(key, _L10N["en"][key])


def _translate_text(text: str, lang: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return clean

    dictionary_hit = _TERM_TRANSLATIONS.get(lang, {}).get(clean)
    if dictionary_hit:
        return dictionary_hit

    translated_by_gemini = translate_text(clean, lang)
    if translated_by_gemini:
        return translated_by_gemini

    word_map = _WORD_TRANSLATIONS.get(lang, {})
    parts = re.split(r"(\W+)", clean)
    changed = False
    translated_parts: list[str] = []
    for part in parts:
        key = _normalize_text(part)
        translated_part = word_map.get(key)
        if translated_part:
            translated_parts.append(translated_part)
            changed = True
        else:
            translated_parts.append(part)

    if changed:
        return "".join(translated_parts).strip()

    return clean


def localize_services(services: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    return [localize_service_record(service, language) for service in services]


def localize_service_record(service: dict[str, Any], language: str) -> dict[str, Any]:
    localized = dict(service)
    original_name = str(service.get("name", "")).strip()
    original_description = str(service.get("description", "")).strip()
    translated_name = _translate_text(original_name, language)
    translated_description = _translate_text(original_description, language)

    localized["original_name"] = original_name
    localized["original_description"] = original_description
    localized["translated_name"] = translated_name
    localized["translated_description"] = translated_description
    localized["name"] = translated_name or original_name
    localized["description"] = translated_description or original_description
    localized["category"] = _translate_text(str(service.get("category", "")).strip(), language) or str(service.get("category", "")).strip()

    if isinstance(service.get("required_documents"), list):
        localized["required_documents"] = [_translate_text(str(doc), language) for doc in service.get("required_documents", [])]

    return localized


def localize_roadmap(roadmap: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    if language == "uz":
        return roadmap

    localized: list[dict[str, Any]] = []
    for section in roadmap:
        section_title = _translate_text(str(section.get("section", "")).strip(), language)
        localized_steps: list[dict[str, Any]] = []
        for step in section.get("steps", []):
            original_title = str(step.get("title", "")).strip()
            original_description = str(step.get("description", "")).strip()
            translated_title = _translate_text(original_title, language)
            translated_description = _translate_text(original_description, language)
            localized_steps.append(
                {
                    **step,
                    "title": translated_title or original_title,
                    "description": translated_description or original_description,
                    "original_name": original_title,
                    "original_description": original_description,
                    "translated_name": translated_title,
                    "translated_description": translated_description,
                }
            )
        localized.append({"section": section_title or str(section.get("section", "")).strip(), "steps": localized_steps})

    return localized


def localize_recommended_services(services: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    if language == "uz":
        return services

    localized: list[dict[str, Any]] = []
    for item in services:
        original_name = str(item.get("name", "")).strip()
        original_description = str(item.get("description", "")).strip()
        translated_name = _translate_text(original_name, language)
        translated_description = _translate_text(original_description, language)
        localized.append(
            {
                **item,
                "name": translated_name or original_name,
                "category": _translate_text(str(item.get("category", "")).strip(), language) or str(item.get("category", "")).strip(),
                "description": translated_description or original_description,
                "reason": _translate_text(str(item.get("reason", "")).strip(), language) or str(item.get("reason", "")).strip(),
                "original_name": original_name,
                "original_description": original_description,
                "translated_name": translated_name,
                "translated_description": translated_description,
            }
        )
    return localized


def _detect_language(query: str) -> str:
    if any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in query):
        return "ru"

    normalized = _normalize_text(query)
    if any(token in normalized for token in ["xizmat", "hujjat", "bola", "tug", "nafaqa", "uy", "pasport"]):
        return "uz"

    return "en"


def _detect_intent(query: str) -> str:
    normalized = _normalize_text(query)
    for intent, hints in _INTENT_HINTS.items():
        if any(hint in normalized for hint in hints):
            return intent
    return "general"


def _expand_query_tokens(query: str) -> set[str]:
    tokens = set(_tokenize(query))
    intent = _detect_intent(query)
    if intent in _INTENT_HINTS:
        tokens.update(token for token in _INTENT_HINTS[intent] if len(token) >= 3)
    return tokens


def _service_text_blob(service: dict[str, Any]) -> str:
    return " ".join(
        [
            str(service.get("name", "")),
            str(service.get("category", "")),
            str(service.get("description", "")),
            " ".join(str(item) for item in service.get("keywords", []) if str(item).strip()),
        ]
    ).strip()


def _is_document_service(service: dict[str, Any]) -> bool:
    blob_tokens = _tokenize(_service_text_blob(service))
    return any(any(token.startswith(hint) for hint in _DOC_HINTS) for token in blob_tokens)


def _score_service(query_tokens: set[str], service: dict[str, Any]) -> int:
    service_tokens = _tokenize(_service_text_blob(service))
    if not service_tokens:
        return 0

    score = 0
    for token in query_tokens:
        if token in service_tokens:
            score += 2
            continue
        if len(token) >= 4 and any(st.startswith(token) or token.startswith(st) for st in service_tokens):
            score += 1

    if _is_document_service(service):
        score += 1
    return score


def _select_relevant_services(query: str, services: list[dict[str, Any]], min_items: int = 3, max_items: int = 6) -> list[dict[str, Any]]:
    query_tokens = _expand_query_tokens(query)
    if not query_tokens:
        return services[:max_items]

    ranked = sorted(
        ((_score_service(query_tokens, service), service) for service in services),
        key=lambda item: (item[0], str(item[1].get("name", "")).lower()),
        reverse=True,
    )

    non_zero = [item[1] for item in ranked if item[0] > 0]
    if len(non_zero) >= min_items:
        return non_zero[:max_items]

    return [item[1] for item in ranked[:max(min_items, min(max_items, len(ranked)))]]


def _is_government_related_query(query: str) -> bool:
    tokens = _tokenize(query)
    if not tokens:
        return False
    return any(token in _DOMAIN_KEYWORDS or any(token.startswith(stem) for stem in _DOMAIN_KEYWORDS) for token in tokens)


def _build_context(services: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for service in services:
        chunks.append(
            "\n".join(
                [
                    f"Service: {str(service.get('name', '')).strip()}",
                    f"Category: {str(service.get('category', '')).strip()}",
                    f"Description: {str(service.get('description', '')).strip()}",
                ]
            )
        )
    return "\n\n---\n\n".join(chunks)


def _build_prompt(query: str, context: str, lang: str) -> str:
    return f'''You are a government services assistant.

STRICT RULES:
1. You ONLY answer government services and official procedures.
2. Use ONLY provided services data.
3. Return only relevant services for this query.
4. Keep response concise and practical.
5. If unrelated query, answer with a polite refusal.

User question:
{query}

IMPORTANT:
You must answer in {lang}.
You must return all service names, descriptions, and roadmap in this language: {lang}

Available services:
{context}

LANGUAGE: {lang}

Return ONLY JSON:
{{
  "answer": "...",
  "roadmap": [
    {{
      "section": "...",
      "steps": [
        {{
          "title": "...",
          "description": "...",
          "estimated_time": "1-3 days"
        }}
      ]
    }}
  ],
  "recommended_services": [
    {{
      "name": "...",
      "category": "...",
      "reason": "..."
    }}
  ]
}}
'''


def _build_roadmap_from_services(items: list[dict[str, Any]], section: str, max_steps: int) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for item in items[:max_steps]:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        steps.append(
            {
                "title": name,
                "description": str(item.get("description", "")).strip() or "Follow official procedure for this service.",
                "estimated_time": "1-3 days",
            }
        )

    if not steps:
        return []

    return [{"section": section, "steps": steps}]


def _build_practical_roadmap(items: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    if not items:
        return []

    doc_services = [item for item in items if _is_document_service(item)]
    main_services = [item for item in items if item not in doc_services]

    roadmap: list[dict[str, Any]] = []
    roadmap.extend(_build_roadmap_from_services(main_services, _text(lang, "section_main"), 4))
    roadmap.extend(_build_roadmap_from_services(doc_services, _text(lang, "section_docs"), 3))

    if roadmap:
        return roadmap

    return _build_roadmap_from_services(items, _text(lang, "section_main"), 4)


def _build_recommended_services(items: list[dict[str, Any]], reason: str, max_items: int = 6) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items[:max_items]:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        result.append(
            {
                "name": name,
                "category": str(item.get("category", "")).strip() or "General",
                "reason": reason,
                "description": str(item.get("description", "")).strip(),
                "original_name": name,
                "original_description": str(item.get("description", "")).strip(),
                "translated_name": name,
                "translated_description": str(item.get("description", "")).strip(),
            }
        )
    return result


def _build_static_sections(lang: str) -> list[dict[str, str | None]]:
    return [
        {
            "title": "Portal Header",
            "content": _text(lang, "portal_header"),
            "icon": "shield-check",
        },
        {
            "title": _text(lang, "profile"),
            "content": _text(lang, "profile_content"),
            "icon": "user",
        },
    ]


def _build_dynamic_sections(roadmap: list[dict[str, Any]], recommended_services: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for section in roadmap:
        for step in section.get("steps", []):
            title = str(step.get("title", "")).strip()
            if not title:
                continue
            steps.append(
                {
                    "title": title,
                    "description": str(step.get("description", "")).strip() or "",
                    "estimated_time": str(step.get("estimated_time", "1-3 days")).strip() or "1-3 days",
                }
            )

    dynamic_services = [
        {
            "name": str(item.get("name", "")).strip(),
            "reason": str(item.get("reason", "")).strip() or _text(lang, "reason_match"),
        }
        for item in recommended_services
        if str(item.get("name", "")).strip()
    ]

    if not steps and not dynamic_services:
        return []

    return [
        {
            "section": _text(lang, "dynamic_section"),
            "steps": steps,
            "recommended_services": dynamic_services,
        }
    ]


def _extract_json_payload(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None

    return None


def _sanitize_response(data: dict[str, Any], lang: str) -> dict[str, Any]:
    answer = str(data.get("answer", "")).strip() or _text(lang, "no_exact")

    roadmap = data.get("roadmap", [])
    if not isinstance(roadmap, list):
        roadmap = []

    recommended_services = data.get("recommended_services", [])
    if not isinstance(recommended_services, list):
        recommended_services = []

    roadmap = localize_roadmap(roadmap, lang)
    recommended_services = localize_recommended_services(recommended_services, lang)

    static_sections = _build_static_sections(lang)
    dynamic_sections = _build_dynamic_sections(roadmap, recommended_services, lang)

    return {
        "answer": answer,
        "roadmap": roadmap,
        "recommended_services": recommended_services,
        "static_sections": static_sections,
        "dynamic_sections": dynamic_sections,
    }


def _build_unrelated_response(closest_services: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    recommended = _build_recommended_services(closest_services, _text(lang, "reason_match"), max_items=3)
    roadmap = _build_practical_roadmap(closest_services, lang)
    roadmap = localize_roadmap(roadmap, lang)
    recommended = localize_recommended_services(recommended, lang)
    return {
        "answer": _text(lang, "unrelated"),
        "roadmap": roadmap,
        "recommended_services": recommended,
        "static_sections": _build_static_sections(lang),
        "dynamic_sections": _build_dynamic_sections(roadmap, recommended, lang),
    }


def _build_deterministic_fallback(relevant_services: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    if not relevant_services:
        return {
            "answer": _text(lang, "no_exact"),
            "roadmap": [],
            "recommended_services": [],
            "static_sections": _build_static_sections(lang),
            "dynamic_sections": [],
        }

    top_services = relevant_services[:3]
    service_names = [str(item.get("name", "")).strip() for item in top_services if str(item.get("name", "")).strip()]
    answer = f"{_text(lang, 'answer_prefix')} " + ", ".join(service_names) + "."

    recommended = _build_recommended_services(relevant_services, _text(lang, "reason_match"), max_items=6)
    roadmap = _build_practical_roadmap(relevant_services, lang)
    roadmap = localize_roadmap(roadmap, lang)
    recommended = localize_recommended_services(recommended, lang)

    return {
        "answer": answer,
        "roadmap": roadmap,
        "recommended_services": recommended,
        "static_sections": _build_static_sections(lang),
        "dynamic_sections": _build_dynamic_sections(roadmap, recommended, lang),
    }


def generate_service_details(service_name: str, language: str, services: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate complete end-to-end workflow for a service."""
    lang = language if language in {"uz", "ru", "en"} else "en"
    
    # Find the service
    target_service = None
    for svc in services:
        if str(svc.get("name", "")).lower().strip() == service_name.lower().strip():
            target_service = svc
            break
    
    if not target_service:
        return {
            "error": f"Service '{service_name}' not found",
            "type": "service_details",
            "language": lang,
        }
    
    # Localize the service
    localized = localize_service_record(target_service, lang)
    
    # Translate texts based on language
    translations = {
        "en": {
            "service_overview": "Service Overview",
            "who_needs": "Who Needs It",
            "step_by_step": "Step-by-Step Process",
            "go_to": "Go to",
            "required_documents": "Required Documents",
            "optional": "Optional",
            "required": "Required",
            "time_cost": "Time & Cost",
            "processing_time": "Estimated Processing Time",
            "cost": "Cost",
            "free": "Free",
            "problems_solutions": "Common Problems & Solutions",
            "problem": "Problem",
            "solution": "Solution",
            "recommendations": "Smart Recommendations",
            "related_services": "Related Services",
            "tips": "Ways to Make Process Faster",
            "multi_language": "This service supports multiple languages",
            "online": "Online",
            "offline": "Offline",
            "visit": "Visit",
            "call": "Call",
            "submit": "Submit",
            "complete": "Complete",
            "receive": "Receive",
        },
        "ru": {
            "service_overview": "Обзор услуги",
            "who_needs": "Кто в этом нуждается",
            "step_by_step": "Пошаговый процесс",
            "go_to": "Перейти на",
            "required_documents": "Необходимые документы",
            "optional": "Необязательный",
            "required": "Обязательный",
            "time_cost": "Время и стоимость",
            "processing_time": "Ориентировочное время обработки",
            "cost": "Стоимость",
            "free": "Бесплатно",
            "problems_solutions": "Распространённые проблемы и решения",
            "problem": "Проблема",
            "solution": "Решение",
            "recommendations": "Умные рекомендации",
            "related_services": "Связанные услуги",
            "tips": "Способы ускорить процесс",
            "multi_language": "Эта услуга поддерживает несколько языков",
            "online": "Онлайн",
            "offline": "Офлайн",
            "visit": "Посетить",
            "call": "Позвонить",
            "submit": "Подать",
            "complete": "Завершить",
            "receive": "Получить",
        },
        "uz": {
            "service_overview": "Xizmat haqida",
            "who_needs": "Bunga kimlar muhtaj",
            "step_by_step": "Qadambaqadam jarayon",
            "go_to": "O'tish",
            "required_documents": "Kerakli hujjatlar",
            "optional": "Ixtiyoriy",
            "required": "Majburiy",
            "time_cost": "Vaqt va xarajat",
            "processing_time": "Taxminan qayta ishlash vaqti",
            "cost": "Xarajat",
            "free": "Bepul",
            "problems_solutions": "Keng tarqalgan muammolar va yechimlar",
            "problem": "Muammo",
            "solution": "Yechim",
            "recommendations": "Aqlli tavsiyalar",
            "related_services": "Tegishli xizmatlar",
            "tips": "Jarayonni tezlashtirish usullari",
            "multi_language": "Ushbu xizmat bir nechta tillarni qo'llab-quvvatlaydi",
            "online": "Onlayn",
            "offline": "Oflayn",
            "visit": "Tashrif buyuring",
            "call": "Qo'ng'iroq qiling",
            "submit": "Topshirish",
            "complete": "To'ldirib",
            "receive": "Olish",
        },
    }
    
    tr = translations.get(lang, translations["en"])
    
    # Build the response structure
    details = {
        "type": "service_details",
        "language": lang,
        "service_name": localized.get("name", service_name),
        
        # 1. Service Overview
        "service_overview": {
            "title": tr["service_overview"],
            "description": localized.get("description", "") or str(localized.get("name", "")),
            "organization": localized.get("provider", ""),
            "category": localized.get("category", ""),
        },
        
        # 2. Step-by-Step Process
        "steps": {
            "title": tr["step_by_step"],
            "process": [
                {
                    "order": 1,
                    "title": f"{tr['visit']} {tr['online']}",
                    "description": f"Navigate to my.gov.uz portal",
                    "location": "online",
                    "action": tr["visit"],
                },
                {
                    "order": 2,
                    "title": f"{tr['submit']} Application",
                    "description": "Fill in and submit the application form",
                    "location": "online",
                    "action": tr["submit"],
                },
                {
                    "order": 3,
                    "title": f"{tr['complete']} Documents",
                    "description": "Prepare and upload required documents",
                    "location": "online",
                    "action": tr["complete"],
                },
                {
                    "order": 4,
                    "title": f"{tr['receive']} Confirmation",
                    "description": "Wait for status updates",
                    "location": "online",
                    "action": "Track",
                },
            ],
        },
        
        # 3. Required Documents
        "documents": {
            "title": tr["required_documents"],
            "list": [
                {
                    "name": doc,
                    "type": tr["required"],
                    "description": f"Document: {doc}",
                }
                for doc in (localized.get("required_documents", []) or [])
            ] or [
                {
                    "name": "ID or Passport",
                    "type": tr["required"],
                    "description": "Valid identification document",
                }
            ],
        },
        
        # 4. Time & Cost
        "time_and_cost": {
            "title": tr["time_cost"],
            "processing_time": localized.get("estimated_time", "") or "3-5 business days",
            "cost": {
                "amount": 0,
                "currency": "UZS",
                "description": tr["free"],
            },
        },
        
        # 5. Common Problems & Solutions
        "problems_and_solutions": {
            "title": tr["problems_solutions"],
            "items": [
                {
                    "problem": "Document rejection",
                    "solution": "Ensure all documents are clear, original, and meet requirements",
                },
                {
                    "problem": "Technical issues with submission",
                    "solution": "Use modern browser, clear cookies, or try again later",
                },
                {
                    "problem": "Status not updating",
                    "solution": "Contact support or visit office during business hours",
                },
            ],
        },
        
        # 6. Smart Recommendations
        "recommendations": {
            "title": tr["recommendations"],
            "related_services": [
                {
                    "name": svc.get("name", ""),
                    "reason": f"Complementary service to {localized.get('name', '')}",
                }
                for svc in services[:3]
                if svc.get("name") != service_name
            ][:4],
            "tips": [
                f"Use {tr['online']} submission to save time",
                "Have all documents ready before starting",
                "Keep confirmation number for future reference",
                "Contact support for any clarifications needed",
            ],
        },
        
        "multi_language_note": tr["multi_language"],
    }
    
    return details


def _resolve_model_name() -> str:
    try:
        available = {
            model.name.replace("models/", "")
            for model in genai.list_models()
            if "generateContent" in (getattr(model, "supported_generation_methods", []) or [])
        }
    except Exception:
        return _PREFERRED_MODELS[0]

    for model_name in _PREFERRED_MODELS:
        if model_name in available:
            return model_name

    return _PREFERRED_MODELS[0]


def generate_ai_response(query: str, services: list[dict[str, Any]], language: str) -> dict[str, Any]:
    if not str(query).strip() or not isinstance(services, list) or len(services) == 0:
        lang = language if language in {"uz", "ru", "en"} else "en"
        return {
            "answer": _text(lang, "no_exact"),
            "roadmap": [],
            "recommended_services": [],
            "static_sections": _build_static_sections(lang),
            "dynamic_sections": [],
        }

    lang = language if language in {"uz", "ru", "en"} else _detect_language(query)
    relevant_services = _select_relevant_services(query=query, services=services)

    if not _is_government_related_query(query):
        return _build_unrelated_response(relevant_services, lang)

    context = _build_context(relevant_services)
    prompt = _build_prompt(query=query, context=context, lang=lang)

    try:
        logger.info("Sending request to Gemini...")
        logger.info("Prompt length: %s", len(prompt))
        model = genai.GenerativeModel(_resolve_model_name())
        response = model.generate_content(prompt)
        raw_text = getattr(response, "text", "") or ""
        logger.info("Raw Gemini response: %s", raw_text)

        payload = _extract_json_payload(raw_text)
        if payload is None:
            fallback = _build_deterministic_fallback(relevant_services, lang)
            fallback["error"] = "Gemini response is not valid JSON"
            fallback["_debug_prompt_length"] = len(prompt)
            fallback["_debug_raw_response"] = raw_text
            fallback["_debug_parsed_json"] = None
            return fallback

        sanitized = _sanitize_response(payload, lang)
        sanitized["_debug_prompt_length"] = len(prompt)
        sanitized["_debug_raw_response"] = raw_text
        sanitized["_debug_parsed_json"] = payload
        return sanitized
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini call failed")
        fallback = _build_deterministic_fallback(relevant_services, lang)
        fallback["error"] = str(exc)
        fallback["_debug_prompt_length"] = len(prompt)
        fallback["_debug_raw_response"] = ""
        fallback["_debug_parsed_json"] = None
        return fallback


def test_gemini_connection() -> dict[str, Any]:
    prompt = "Say hello in JSON format"
    try:
        model = genai.GenerativeModel(_resolve_model_name())
        response = model.generate_content(prompt)
        return {
            "ok": True,
            "model": _resolve_model_name(),
            "raw_response": getattr(response, "text", "") or "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini /test-ai call failed")
        return {
            "ok": False,
            "model": _resolve_model_name(),
            "error": str(exc),
            "raw_response": "",
        }
