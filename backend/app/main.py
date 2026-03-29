import logging
import os
import random
import time
import traceback
from difflib import SequenceMatcher
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import (
    SCENARIOS,
    detect_scenarios,
    to_localized_scenario_detail,
    to_localized_scenario_hint,
)
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    AskAssistantRequest,
    AskAssistantResponse,
    AskAssistantRoadmapSection,
    AskAssistantRoadmapStep,
    AskAssistantSuggestedService,
    AutoFillRequest,
    AutoFillResponse,
    ConversationHistoryItem,
    DynamicAnalyzeRequest,
    DynamicAnalyzeResponse,
    DynamicRecommendedService,
    DynamicSection,
    DynamicSectionStep,
    ExecuteServiceRequest,
    ExecuteServiceResponse,
    ExecuteStage,
    LoginRequest,
    LoginResponse,
    ProfileResponse,
    QueueInfo,
    RagRequest,
    RagResponse,
    RagSourceInfo,
    RegisterRequest,
    RegisterResponse,
    ScenarioDetail,
    StaticSection,
)
from .ai_service import (
    generate_ai_response,
    generate_service_details,
    localize_services,
    localize_recommended_services,
    localize_roadmap,
    localize_service_record,
    test_gemini_connection,
)
from .services_loader import build_scenario, find_similar_services, get_services, rank_services, search_services

app = FastAPI(
    title="Smart Gov Assistant API",
    description="MVP API for life-situation based government service discovery",
    version="0.1.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.on_event("startup")
def preload_services_cache() -> None:
    logger.info("GEMINI_API_KEY loaded: %s", bool(os.getenv("GEMINI_API_KEY")))
    # Warm up Excel cache on startup for predictable first-request latency.
    try:
        get_services()
    except Exception:
        # Keep API boot resilient even when data file is temporarily unavailable.
        pass


def _detect_question_language(question: str) -> str:
    text = question.lower()

    uz_markers = (
        "o'",
        "g'",
        "sh",
        "ch",
        "qanday",
        "xizmat",
        "uchun",
        "bo'yicha",
        "tug'il",
        "pasport",
        "nafaqa",
        "uy",
        "yo'q",
    )
    en_markers = (
        "what",
        "which",
        "how",
        "service",
        "services",
        "document",
        "documents",
        "need",
        "required",
        "passport",
        "birth",
        "housing",
        "pension",
    )

    has_cyrillic = any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in question)
    if has_cyrillic:
        return "ru"

    if any(marker in text for marker in uz_markers):
        return "uz"

    if any(marker in text for marker in en_markers):
        return "en"

    # Default to Uzbek for local audience when language is ambiguous.
    return "uz"


def _resolve_language(language: str | None, text: str) -> str:
    if language in {"uz", "ru", "en"}:
        return language
    return _detect_question_language(text)


def _to_step_dict(step: Any) -> dict[str, Any]:
    if hasattr(step, "model_dump"):
        return step.model_dump()
    if isinstance(step, dict):
        return dict(step)
    return {}


def _localize_dynamic_step(step: Any, language: str) -> dict[str, Any]:
    base = _to_step_dict(step)
    localized = localize_service_record(
        {
            "name": base.get("title") or base.get("service_name") or "",
            "description": base.get("description") or "",
            "category": base.get("category") or "",
            "required_documents": base.get("required_documents") or [],
        },
        language,
    )
    base["title"] = localized.get("name", base.get("title", ""))
    base["service_name"] = localized.get("name", base.get("service_name", ""))
    base["description"] = localized.get("description", base.get("description", ""))
    base["category"] = localized.get("category", base.get("category", ""))
    base["required_documents"] = localized.get("required_documents", base.get("required_documents", []))
    base["original_name"] = localized.get("original_name")
    base["original_description"] = localized.get("original_description")
    base["translated_name"] = localized.get("translated_name")
    base["translated_description"] = localized.get("translated_description")
    return base


def _rag_unknown_answer(language: str) -> str:
    if language == "ru":
        return "Не знаю: в services.xlsx нет данных для точного ответа на этот вопрос."
    if language == "en":
        return "I don't know: services.xlsx does not contain enough data to answer this question."
    return "Bilmayman: services.xlsx faylida bu savolga aniq javob uchun ma'lumot topilmadi."


def _rag_answer_from_rows(language: str, rows: list[dict[str, Any]]) -> str:
    top = rows[0]
    name = str(top.get("name", "")).strip()
    category = str(top.get("category", "")).strip()
    description = str(top.get("description", "")).strip()

    if language == "ru":
        return (
            f"По данным services.xlsx наиболее подходящая услуга: {name}. "
            f"Категория: {category}. Описание: {description}"
        )

    if language == "en":
        return (
            f"Based on services.xlsx, the closest matching service is: {name}. "
            f"Category: {category}. Description: {description}"
        )

    return (
        f"services.xlsx ma'lumotiga ko'ra eng mos xizmat: {name}. "
        f"Kategoriya: {category}. Tavsif: {description}"
    )


def _format_row_context(rows: list[dict[str, Any]]) -> str:
    formatted_rows: list[str] = []
    for row in rows:
        formatted_rows.append(
            " | ".join(
                [
                    f"id={row.get('id', '')}",
                    f"name={row.get('name', '')}",
                    f"category={row.get('category', '')}",
                    f"keywords={', '.join(row.get('keywords', []))}",
                    f"description={row.get('description', '')}",
                ]
            )
        )
    return "\n".join(formatted_rows)


def _normalize_ask_text(text: str) -> str:
    lowered = str(text).lower().strip()
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return " ".join(cleaned.split())


def _split_ask_words(text: str) -> list[str]:
    return [word for word in _normalize_ask_text(text).split(" ") if word]


def _ask_word_match(word: str, token: str) -> bool:
    if not word or not token:
        return False
    if word == token:
        return True
    min_len = min(len(word), len(token))
    if min_len >= 4 and (word in token or token in word):
        return True
    return SequenceMatcher(None, word, token).ratio() >= 0.82


def _retrieve_services_for_ask(question: str, services: list[dict[str, Any]], limit: int = 6) -> list[tuple[int, dict[str, Any]]]:
    words = _split_ask_words(question)
    if not words:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for service in services:
        name = _normalize_ask_text(str(service.get("name", "")))
        category = _normalize_ask_text(str(service.get("category", "")))
        description = _normalize_ask_text(str(service.get("description", "")))
        keywords_raw = service.get("keywords", [])
        keywords = [_normalize_ask_text(str(item)) for item in keywords_raw if str(item).strip()]

        name_tokens = _split_ask_words(name)
        description_tokens = _split_ask_words(description)
        keyword_tokens = [token for keyword in keywords for token in _split_ask_words(keyword)]

        score = 0
        for word in words:
            keyword_hit = any(_ask_word_match(word, token) for token in keyword_tokens)
            if keyword_hit:
                score += 2

            name_hit = any(_ask_word_match(word, token) for token in name_tokens)
            if name_hit:
                score += 1

            desc_hit = any(_ask_word_match(word, token) for token in description_tokens)
            if desc_hit:
                score += 1

            # Keep some category sensitivity for roadmap grouping quality.
            if _ask_word_match(word, category):
                score += 1

        if score > 0:
            scored.append((score, service))

    if not scored:
        # Fallback to closest textual similarity so response is never empty when Excel exists.
        fallback_ranked: list[tuple[float, dict[str, Any]]] = []
        normalized_question = _normalize_ask_text(question)
        for service in services:
            blob = " ".join(
                [
                    _normalize_ask_text(str(service.get("name", ""))),
                    _normalize_ask_text(str(service.get("category", ""))),
                    _normalize_ask_text(str(service.get("description", ""))),
                ]
            )
            ratio = SequenceMatcher(None, normalized_question, blob).ratio()
            fallback_ranked.append((ratio, service))

        fallback_ranked.sort(key=lambda item: item[0], reverse=True)
        return [(1, item[1]) for item in fallback_ranked[: max(5, min(limit, 8))]]

    scored.sort(key=lambda item: (item[0], str(item[1].get("name", "")).lower()), reverse=True)
    return scored[: max(5, min(limit, 8))]


def _detect_life_intent(question: str) -> str:
    normalized = _normalize_ask_text(question)
    if any(token in normalized for token in ["bola", "tug", "birth", "newborn", "рожд", "ребен"]):
        return "birth"
    if any(token in normalized for token in ["uy", "house", "home", "housing", "ипотек", "дом", "жиль"]):
        return "housing"
    if any(token in normalized for token in ["ish", "job", "work", "employment", "работ", "труд"]):
        return "job"
    if any(token in normalized for token in ["pension", "pensiya", "nafaqa", "пенси"]):
        return "pension"
    return "general"


def _fallback_services_for_query(query: str, services: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    if not services:
        return []

    normalized = _normalize_ask_text(query)
    intent = _detect_life_intent(query)

    markers_by_intent = {
        "birth": ["tug", "bola", "birth", "born", "newborn", "ребен", "рожд"],
        "housing": ["uy", "house", "home", "housing", "ипотек", "дом", "жиль", "kadastr"],
        "job": ["ish", "job", "work", "employment", "bandlik", "работ", "труд"],
        "pension": ["pension", "pensiya", "nafaqa", "пенси"],
    }

    markers = markers_by_intent.get(intent, [])
    if markers:
        matched: list[dict[str, Any]] = []
        for service in services:
            blob = _normalize_ask_text(
                " ".join(
                    [
                        str(service.get("name", "")),
                        str(service.get("category", "")),
                        str(service.get("description", "")),
                        " ".join(str(k) for k in service.get("keywords", [])),
                    ]
                )
            )
            if any(marker in blob for marker in markers):
                matched.append(dict(service))

        if matched:
            return matched[: max(3, min(limit, 12))]

    # Last-resort fallback: always return some services instead of empty response.
    if normalized:
        ranked = sorted(
            (
                (SequenceMatcher(None, normalized, _normalize_ask_text(str(service.get("name", "")))).ratio(), dict(service))
                for service in services
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        return [item[1] for item in ranked[: max(3, min(limit, 12))]]

    return [dict(service) for service in services[: max(3, min(limit, 12))]]


def _ask_answer(language: str, intent: str, top_services: list[dict[str, Any]]) -> str:
    if top_services:
        top_names = ", ".join(str(item.get("name", "")).strip() for item in top_services[:2] if str(item.get("name", "")).strip())
    else:
        top_names = ""

    if language == "ru":
        templates = {
            "birth": "После рождения ребенка обычно нужно зарегистрировать рождение, получить свидетельство и оформить выплаты.",
            "housing": "При покупке жилья обычно нужно подготовить документы, зарегистрировать сделку и проверить налоговые/реестровые шаги.",
            "job": "При трудоустройстве обычно подают заявления, оформляют документы и активируют связанные госуслуги.",
            "pension": "Для выхода на пенсию обычно собирают подтверждающие документы, подают заявку и отслеживают статус назначения.",
            "general": "По вашему вопросу лучше начать с базовых услуг, затем пройти регистрацию и документы по шагам.",
        }
        suffix = f" Подходящие услуги: {top_names}." if top_names else ""
        return templates.get(intent, templates["general"]) + suffix

    if language == "en":
        templates = {
            "birth": "After a child is born, you usually need to register the birth, get a certificate, and apply for benefits.",
            "housing": "When buying a home, you usually prepare documents, register the deal, and complete tax/registry steps.",
            "job": "For employment, people usually submit applications, complete documents, and activate related services.",
            "pension": "For pension, you usually gather proof documents, submit the request, and track the approval status.",
            "general": "For your question, start with core services first, then complete registration and documents step by step.",
        }
        suffix = f" Relevant services: {top_names}." if top_names else ""
        return templates.get(intent, templates["general"]) + suffix

    templates = {
        "birth": "Bola tug'ilgandan keyin odatda tug'ilishni ro'yxatdan o'tkazish, guvohnoma olish va nafaqa xizmatlarini rasmiylashtirish kerak bo'ladi.",
        "housing": "Uy sotib olayotganda odatda hujjatlarni tayyorlash, bitimni ro'yxatdan o'tkazish va soliq/reyestr bosqichlarini bajarish kerak bo'ladi.",
        "job": "Ishga kirishda odatda ariza topshirish, hujjatlarni rasmiylashtirish va tegishli xizmatlarni faollashtirish kerak bo'ladi.",
        "pension": "Nafaqa uchun odatda tasdiqlovchi hujjatlar yig'iladi, ariza beriladi va holat kuzatib boriladi.",
        "general": "Savolingiz bo'yicha avval asosiy xizmatlardan boshlang, keyin ro'yxatdan o'tish va hujjat bosqichlarini ketma-ket bajaring.",
    }
    suffix = f" Mos xizmatlar: {top_names}." if top_names else ""
    return templates.get(intent, templates["general"]) + suffix


def _to_ask_sections(sections: list[dict[str, Any]], max_sections: int = 4, max_steps_total: int = 5) -> list[dict[str, Any]]:
    section_map = {
        "Registration": "Registration",
        "Documentation": "Documents",
        "Benefits": "Benefits",
        "Healthcare": "Healthcare",
        "Additional": "Additional",
    }

    result: list[dict[str, Any]] = []
    left = max_steps_total
    step_id = 1
    for section in sections[:max_sections]:
        title = section_map.get(str(section.get("title", "Additional")), "Additional")
        steps: list[dict[str, Any]] = []
        for step in section.get("steps", []):
            if left <= 0:
                break
            steps.append(
                {
                    "id": step_id,
                    "title": str(step.get("title", "Service")).strip() or "Service",
                    "description": str(step.get("description", "")).strip() or "No description",
                    "estimated_time": str(step.get("estimated_time", "1-3 days")).strip() or "1-3 days",
                }
            )
            step_id += 1
            left -= 1
        if steps:
            result.append({"section": title, "steps": steps})
        if left <= 0:
            break
    return result

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


USERS_DB: Dict[str, Dict[str, Any]] = {
    "demo": {
        "username": "demo",
        "password": "demo123",
        "full_name": "Ali Tursunov",
        "passport_number": "AA1234567",
        "birth_date": "1985-01-01",
        "address": "Tashkent, Uzbekistan",
        "family_members": [
            {"name": "Nodira Tursunova", "birth_date": "1987-05-12"},
            {"name": "Sardor Tursunov", "birth_date": "2010-03-20"},
        ],
    }
}

TOKENS_DB: Dict[str, str] = {}

EXECUTIONS_DB: Dict[str, Dict[str, Any]] = {}

FORM_TYPE_USER_KEYWORDS = {
    "user",
    "personal",
    "profile",
    "passport",
    "address",
    "birth",
    "identity",
    "citizen",
}

FORM_TYPE_FAMILY_KEYWORDS = {
    "family",
    "member",
    "children",
    "child",
    "spouse",
    "dependent",
}


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Invalid Authorization format. Use: Bearer <token>")

    return parts[1].strip()


def _build_public_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": user["username"],
        "full_name": user["full_name"],
        "passport_number": user["passport_number"],
        "birth_date": user["birth_date"],
        "address": user["address"],
        "family_members": user.get("family_members", []),
    }


def _autofill_requirements(form_type: str) -> tuple[bool, bool]:
    normalized = form_type.strip().lower()
    wants_user_info = any(keyword in normalized for keyword in FORM_TYPE_USER_KEYWORDS)
    wants_family_info = any(keyword in normalized for keyword in FORM_TYPE_FAMILY_KEYWORDS)

    if "all" in normalized or "full" in normalized:
        return True, True

    # Default to user info for generic form types in MVP.
    if not wants_user_info and not wants_family_info:
        wants_user_info = True

    return wants_user_info, wants_family_info


def _build_autofill_payload(username: str, form_type: str) -> Dict[str, Any]:
    normalized_username = username.strip().lower()
    normalized_form_type = form_type.strip()

    user = USERS_DB.get("demo") if normalized_username == "demo" else USERS_DB.get(normalized_username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    wants_user_info, wants_family_info = _autofill_requirements(normalized_form_type)

    payload: Dict[str, Any] = {
        "username": normalized_username,
        "form_type": normalized_form_type,
    }

    if wants_user_info:
        payload.update(
            {
                "full_name": user.get("full_name", ""),
                "passport_number": user.get("passport_number", ""),
                "birth_date": user.get("birth_date", ""),
                "address": user.get("address", ""),
            }
        )

    if wants_family_info:
        payload["family_members"] = user.get("family_members", [])

    return payload


def _generate_execution_stages(service_name: str) -> list[ExecuteStage]:
    base_stages = [
        ExecuteStage(stage="Application Submitted", status="done"),
        ExecuteStage(stage="Under Review", status="current"),
        ExecuteStage(stage="Processing", status="pending"),
        ExecuteStage(stage="Completed", status="pending"),
    ]
    return base_stages


def _refresh_execution_state(execution_state: Dict[str, Any]) -> None:
    if execution_state.get("status") != "in_progress":
        return

    started_at = float(execution_state.get("started_at") or time.time())
    elapsed = max(0.0, time.time() - started_at)
    stages = execution_state.get("stages", [])
    if len(stages) < 4:
        return

    # 0-4s: review, 4-8s: processing, 8-12s: finalization, >=12s: completed.
    if elapsed >= 12.0:
        for stage in stages:
            stage.status = "done"

        execution_state["status"] = "completed"
        if not execution_state.get("final_result"):
            execution_state["final_result"] = _generate_final_result(execution_state.get("service_name", ""))
        return

    transition_index = 1
    if elapsed >= 8.0:
        transition_index = 3
    elif elapsed >= 4.0:
        transition_index = 2

    for index, stage in enumerate(stages):
        if index < transition_index:
            stage.status = "done"
        elif index == transition_index:
            stage.status = "current"
        else:
            stage.status = "pending"

    queue_info = execution_state.get("queue_info")
    if queue_info and queue_info.position:
        reduced = max(1, queue_info.position - int(elapsed // 4))
        queue_info.position = reduced


def _generate_queue_info(service_name: str) -> QueueInfo | None:
    service_lower = service_name.lower()
    service_types = ["queue", "appointment", "booking", "slot", "navbat", "очеред"]
    requires_queue = any(keyword in service_lower for keyword in service_types)

    if requires_queue:
        position = random.randint(1, 15)
        est_minutes = position * 5 + random.randint(0, 10)
        return QueueInfo(position=position, estimated_time=f"{est_minutes} minutes")

    return None


def _generate_final_result(service_name: str) -> dict[str, Any]:
    service_lower = service_name.lower()

    cert_keywords = ["certificate", "sertifikat", "document", "документ", "hujjat", "guvohnoma"]
    is_cert = any(keyword in service_lower for keyword in cert_keywords)

    queue_keywords = ["queue", "appointment", "navbat", "очеред"]
    is_queue = any(keyword in service_lower for keyword in queue_keywords)

    application_keywords = [
        "application",
        "ariza",
        "request",
        "approval",
        "permit",
        "license",
        "zayav",
        "заяв",
        "разреш",
        "лиценз",
    ]
    is_application = any(keyword in service_lower for keyword in application_keywords)

    if is_cert:
        doc_suffix = random.randint(1000, 9999)
        cert_messages = [
            "You can download your certificate from the portal.",
            "The document is generated and ready for download.",
            "Download your final certificate copy below.",
        ]
        return {
            "type": "certificate",
            "title": "Your document is ready",
            "message": random.choice(cert_messages),
            "download_url": f"/api/mock-certificate-{doc_suffix}.pdf",
        }

    if is_queue:
        queue_messages = [
            "Please proceed to the service office.",
            "Counter is ready for your request now.",
            "Your queue has reached the service desk.",
        ]
        return {
            "type": "queue_turn",
            "title": "Your turn now",
            "message": random.choice(queue_messages),
            "next_steps": "Visit the office during business hours.",
        }

    if is_application:
        approved = random.random() < 0.8
        if approved:
            return {
                "type": "application",
                "decision": "approved",
                "title": "Your request has been approved",
                "message": "Your application was successfully approved.",
                "reference_number": f"REF-{uuid4().hex[:8].upper()}",
            }

        rejection_reasons = [
            "Additional supporting document is required.",
            "Data mismatch found in submitted application.",
            "Please update application details and re-submit.",
        ]
        return {
            "type": "application",
            "decision": "rejected",
            "title": "Your request has been rejected",
            "message": random.choice(rejection_reasons),
            "reference_number": f"REF-{uuid4().hex[:8].upper()}",
        }

    return {
        "type": "application",
        "decision": "approved",
        "title": "Your request has been approved",
        "message": "Your service request has been successfully processed.",
        "reference_number": f"REF-{uuid4().hex[:8].upper()}",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/register", response_model=RegisterResponse)
def register_user(request: RegisterRequest) -> RegisterResponse:
    username = request.username.strip().lower()
    if username in USERS_DB:
        raise HTTPException(status_code=409, detail="Username already exists")

    USERS_DB[username] = {
        "username": username,
        "password": request.password,
        "full_name": request.full_name,
        "passport_number": request.passport_number,
        "birth_date": request.birth_date,
        "address": request.address,
        "family_members": [member.model_dump() for member in request.family_members],
    }

    return RegisterResponse(username=username, message="User registered successfully")


@app.post("/login", response_model=LoginResponse)
def login_user(request: LoginRequest) -> LoginResponse:
    username = request.username.strip().lower()
    user = USERS_DB.get(username)
    if not user or user.get("password") != request.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = f"demo-token-{username}-{uuid4().hex[:12]}"
    TOKENS_DB[token] = username
    return LoginResponse(access_token=token)


@app.get("/profile", response_model=ProfileResponse)
def get_profile(authorization: str | None = Header(default=None)) -> ProfileResponse:
    token = _extract_bearer_token(authorization)
    username = TOKENS_DB.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = USERS_DB.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return ProfileResponse(**_build_public_profile(user))


@app.post("/autofill", response_model=AutoFillResponse)
def autofill_form(request: AutoFillRequest, authorization: str | None = Header(default=None)) -> AutoFillResponse:
    token = _extract_bearer_token(authorization)
    if token not in TOKENS_DB:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    payload = _build_autofill_payload(request.username, request.form_type)
    return AutoFillResponse(**payload)


@app.get("/autofill", response_model=AutoFillResponse)
def autofill_form_get(
    username: str = Query(min_length=3, max_length=64),
    form_type: str = Query(default="full_application_all", min_length=2, max_length=100),
    authorization: str | None = Header(default=None),
) -> AutoFillResponse:
    token = _extract_bearer_token(authorization)
    if token not in TOKENS_DB:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    payload = _build_autofill_payload(username, form_type)
    return AutoFillResponse(**payload)


@app.get("/suggest")
def suggest_services(q: str = Query(default="", min_length=0, max_length=200)) -> dict:
    query = q.strip()
    if not query:
        return {"suggestions": []}

    try:
        services = get_services()
    except FileNotFoundError:
        return {"suggestions": []}

    matched = search_services(query, services)
    suggestions = [
        {
            "name": str(service.get("name", "")).strip(),
            "category": str(service.get("category", "")).strip(),
        }
        for service in matched[:5]
        if str(service.get("name", "")).strip()
    ]
    return {"suggestions": suggestions}


@app.post("/rag/answer", response_model=RagResponse)
def rag_answer(request: RagRequest) -> RagResponse:
    language = _detect_question_language(request.question)

    try:
        services = get_services()
    except Exception:  # noqa: BLE001
        return RagResponse(
            answer=_rag_unknown_answer(language),
            source_info=RagSourceInfo(
                filename="services.xlsx",
                full_context_used="",
                highlight_quote="",
            ),
        )

    matched_services = search_services(request.question, services)
    if not matched_services:
        return RagResponse(
            answer=_rag_unknown_answer(language),
            source_info=RagSourceInfo(
                filename="services.xlsx",
                full_context_used="",
                highlight_quote="",
            ),
        )

    top_rows = matched_services[:3]
    highlight_quote = str(top_rows[0].get("description") or top_rows[0].get("name") or "").strip()

    return RagResponse(
        answer=_rag_answer_from_rows(language, top_rows),
        source_info=RagSourceInfo(
            filename="services.xlsx",
            full_context_used=_format_row_context(top_rows),
            highlight_quote=highlight_quote,
        ),
    )


@app.post("/analyze", response_model=DynamicAnalyzeResponse)
def analyze_dynamic(request: DynamicAnalyzeRequest) -> DynamicAnalyzeResponse:
    language = _resolve_language(request.language, request.query)
    friendly_empty_message = {
        "uz": "Holatingiz to'liq aniqlanmadi, lekin sizga mos xizmatlar ko'rsatildi.",
        "ru": "Ситуация определена не полностью, но показаны релевантные услуги.",
        "en": "We couldn't fully identify your situation, but here are relevant services.",
    }[language]
    suggested_scenarios = {
        "uz": ["Bola tug'ildi", "Uy sotib olish", "Ishga kirish"],
        "ru": ["Родился ребенок", "Покупка жилья", "Трудоустройство"],
        "en": ["Child was born", "Buying a home", "Getting a job"],
    }[language]

    try:
        services = get_services()
    except FileNotFoundError:
        return DynamicAnalyzeResponse(
            scenario="dynamic",
            scenario_display="",
            sections=[],
            steps=[],
            differences=[],
            recommendations=["Service data is temporarily unavailable. Please try again later."],
            suggested_scenarios=suggested_scenarios,
            message="Service catalog file was not found.",
        )

    ranked_services = rank_services(request.query, services)
    matched_services = [dict(service) for _, service in ranked_services[:10]]

    if not matched_services:
        matched_services = _fallback_services_for_query(request.query, services, limit=10)

    scenario = build_scenario(request.query, matched_services)

    localized_steps = [_localize_dynamic_step(step, language) for step in scenario.get("steps", [])]
    localized_sections: list[dict[str, Any]] = []
    for section in scenario.get("sections", []):
        section_dict = _to_step_dict(section)
        localized_section_title = localize_service_record(
            {"name": section_dict.get("title", ""), "description": "", "category": ""},
            language,
        ).get("name", section_dict.get("title", ""))
        localized_section_steps = [_localize_dynamic_step(step, language) for step in section_dict.get("steps", [])]
        localized_sections.append(
            {
                "title": localized_section_title,
                "steps": localized_section_steps,
            }
        )

    differences = find_similar_services(matched_services)
    if not differences and len(matched_services) >= 2:
        first = matched_services[0]
        second = matched_services[1]
        differences = [
            {
                "service1": str(first.get("name", "Service 1")),
                "service2": str(second.get("name", "Service 2")),
                "explanation": (
                    f"{str(first.get('name', 'Service 1'))} is usually for: {str(first.get('description', '')).split('.')[0]}. "
                    f"{str(second.get('name', 'Service 2'))} is usually for: {str(second.get('description', '')).split('.')[0]}."
                ),
            }
        ]

    recommendations = {
        "uz": [
            "Birinchi bosqichdan boshlang va xizmatlarni ketma-ket bajaring.",
            "Xizmat idorasiga borishdan oldin barcha kerakli hujjatlarni tayyorlang.",
        ],
        "ru": [
            "Начните с первого шага и проходите услуги по порядку.",
            "Подготовьте все нужные документы перед обращением в ведомство.",
        ],
        "en": [
            "Start from the first step and complete services in order.",
            "Prepare all required documents before visiting the service office.",
        ],
    }[language]

    if len(scenario.get("steps", [])) >= 3:
        recommendations.append(
            {
                "uz": "Keyingi bosqichlarda kechikmaslik uchun har qadam holatini kuzatib boring.",
                "ru": "Отслеживайте статус каждого шага, чтобы избежать задержек на следующих этапах.",
                "en": "Track status after each step to avoid delays in the next stage.",
            }[language]
        )

    strongest_score = ranked_services[0][0] if ranked_services else 0
    fallback_message = "" if strongest_score >= 3 else friendly_empty_message

    return DynamicAnalyzeResponse(
        scenario=scenario.get("scenario", "dynamic"),
        scenario_display=scenario.get("scenario_display", request.query.strip()),
        sections=localized_sections,
        steps=localized_steps,
        differences=differences,
        recommendations=recommendations,
        suggested_scenarios=suggested_scenarios,
        message=fallback_message,
    )


def _process_chat(request: AskAssistantRequest) -> AskAssistantResponse:
    raw_question = str(request.question or request.message or "").strip()
    
    # Preprocessing: append service context hints for detected life situations
    if "bola tug'ildi" in raw_question.lower():
        raw_question = raw_question + " User needs services like birth registration, certificate, and child benefits"
        logger.info("Detected 'bola tug'ildi' life situation, enriching query with service context")
    
    logger.info("Incoming request: %s", raw_question)
    is_valid = bool(raw_question and len(raw_question) >= 2)
    logger.info("Validation result: %s", is_valid)

    language = _resolve_language(request.language, raw_question)
    fallback_message = {
        "uz": "Savolingiz to'liq aniqlanmadi, lekin siz uchun mos xizmatlar topildi.",
        "ru": "Мы не смогли полностью понять ваш вопрос, но нашли связанные услуги.",
        "en": "We couldn't fully understand your question, but here are some related services.",
    }[language]

    try:
        logger.info("Loading services from Excel...")
        services = get_services()
        if not services:
            logger.warning("Empty Excel data")
    except Exception:  # noqa: BLE001
        logger.error("Failed to load Excel services\n%s", traceback.format_exc())
        return AskAssistantResponse(answer="AI service error", error="Failed to load services from Excel", roadmap=[], recommended_services=[], message=fallback_message)

    localized_services = localize_services(services, language)

    ranked = _retrieve_services_for_ask(raw_question, localized_services, limit=6)
    matched = [dict(service) for _, service in ranked]
    logger.info("Top services found: %s", [str(item.get("name", "")) for item in matched])

    fallback_services = matched if matched else [dict(service) for service in localized_services[:6]]
    if not matched:
        logger.warning("No services found by pre-ranking, using full dataset in AI mapper")

    # Gemini RAG call: uses only matched services derived from Excel data.
    logger.info("Sending request to Gemini...")
    ai_result = generate_ai_response(raw_question, localized_services, language=language)
    logger.info("Prompt length: %s", ai_result.get("_debug_prompt_length"))
    logger.info("Raw Gemini response: %s", ai_result.get("_debug_raw_response", ""))
    logger.info("Parsed JSON: %s", ai_result.get("_debug_parsed_json"))

    ai_error = str(ai_result.get("error", "")).strip() or None

    ai_roadmap = ai_result.get("roadmap", [])
    normalized_roadmap: list[dict[str, Any]] = []
    for section_index, section in enumerate(ai_roadmap, start=1):
        section_title = str(section.get("section", "General")).strip() or "General"
        raw_steps = section.get("steps", []) if isinstance(section.get("steps", []), list) else []
        steps: list[dict[str, Any]] = []
        for step_index, step in enumerate(raw_steps, start=1):
            steps.append(
                {
                    "id": step_index,
                    "title": str(step.get("title", f"Step {step_index}")).strip() or f"Step {step_index}",
                    "description": str(step.get("description", "")).strip() or "No description",
                    "estimated_time": str(step.get("estimated_time", "1-3 days")).strip() or "1-3 days",
                }
            )
        if steps:
            normalized_roadmap.append({"section": section_title, "steps": steps})

    normalized_roadmap = localize_roadmap(normalized_roadmap, language)

    ai_recommended = ai_result.get("recommended_services", [])
    normalized_recommended: list[dict[str, Any]] = []
    for index, item in enumerate(ai_recommended, start=1):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        category = str(item.get("category", "")).strip() or "General"
        reason = str(item.get("reason", "")).strip() or "Relevant to your request"
        normalized_recommended.append(
            {
                "id": str(index),
                "name": name,
                "category": category,
                "reason": reason,
                "description": str(item.get("description", "")).strip(),
                "original_name": str(item.get("original_name", name)).strip() or name,
                "original_description": str(item.get("original_description", item.get("description", ""))).strip(),
                "translated_name": str(item.get("translated_name", name)).strip() or name,
                "translated_description": str(item.get("translated_description", item.get("description", ""))).strip(),
            }
        )

    # Keep response non-empty even if AI output is partially missing.
    if not normalized_recommended:
        fallback_localized = [localize_service_record(service, language) for service in fallback_services[:6]]
        normalized_recommended = [
            {
                "id": str(index + 1),
                "name": str(service.get("name", "")).strip() or "Service",
                "category": str(service.get("category", "")).strip() or "General",
                "reason": {
                    "uz": "So'rovingizga mos xizmat",
                    "ru": "Услуга соответствует вашему запросу",
                    "en": "Relevant to your request",
                }[language],
                "description": str(service.get("description", "")).strip(),
                "original_name": str(service.get("original_name", service.get("name", ""))).strip(),
                "original_description": str(service.get("original_description", service.get("description", ""))).strip(),
                "translated_name": str(service.get("translated_name", service.get("name", ""))).strip(),
                "translated_description": str(service.get("translated_description", service.get("description", ""))).strip(),
            }
            for index, service in enumerate(fallback_localized)
        ]

    normalized_recommended = localize_recommended_services(normalized_recommended, language)

    if not normalized_roadmap:
        scenario = build_scenario(raw_question, fallback_services)
        normalized_roadmap = _to_ask_sections(scenario.get("sections", []), max_sections=4, max_steps_total=5)

    answer = str(ai_result.get("answer", "")).strip() or fallback_message
    message = "" if ranked and ranked[0][0] >= 3 else fallback_message

    ai_static = ai_result.get("static_sections", [])
    normalized_static: list[dict[str, Any]] = []
    if isinstance(ai_static, list):
        for item in ai_static:
            title = str(item.get("title", "")).strip()
            content = str(item.get("content", "")).strip()
            if not title or not content:
                continue
            normalized_static.append(
                {
                    "title": title,
                    "content": content,
                    "icon": str(item.get("icon", "")).strip() or None,
                }
            )

    # Keep static sections always visible even if AI output omitted them.
    if not normalized_static:
        normalized_static = [
            {"title": "Portal Header", "content": "my.gov.uz - O'zbekiston davlat xizmatlari portali", "icon": "shield-check"},
            {"title": "User Profile", "content": "Sign in to view your profile details", "icon": "user"},
        ]

    normalized_conversation = [{"question": raw_question, "answer": answer}]

    flattened_steps: list[dict[str, Any]] = []
    for section in normalized_roadmap:
        for step in section.get("steps", []):
            flattened_steps.append(
                {
                    "title": str(step.get("title", "")).strip(),
                    "description": str(step.get("description", "")).strip(),
                    "estimated_time": str(step.get("estimated_time", "1-3 days")).strip() or "1-3 days",
                }
            )

    normalized_dynamic = []
    if flattened_steps or normalized_recommended:
        normalized_dynamic.append(
            {
                "section": "Roadmap & Services",
                "steps": flattened_steps,
                "recommended_services": [
                    {
                        "name": item["name"],
                        "reason": item["reason"],
                    }
                    for item in normalized_recommended
                ],
            }
        )

    try:
        return AskAssistantResponse(
            answer=answer,
            roadmap=[AskAssistantRoadmapSection(**section) for section in normalized_roadmap],
            recommended_services=[AskAssistantSuggestedService(**item) for item in normalized_recommended],
            static_sections=[StaticSection(**item) for item in normalized_static],
            conversation_history=[ConversationHistoryItem(**item) for item in normalized_conversation],
            dynamic_sections=[
                DynamicSection(
                    section=item["section"],
                    steps=[DynamicSectionStep(**step) for step in item["steps"]],
                    recommended_services=[DynamicRecommendedService(**svc) for svc in item["recommended_services"]],
                )
                for item in normalized_dynamic
            ],
            message=message,
            error=ai_error,
        )
    except Exception:  # noqa: BLE001
        logger.error("Ask Assistant response build error\n%s", traceback.format_exc())
        return AskAssistantResponse(
            answer="AI service error",
            error="Response parsing failure",
            roadmap=[],
            recommended_services=[],
            static_sections=[
                StaticSection(title="Portal Header", content="my.gov.uz - O'zbekiston davlat xizmatlari portali", icon="shield-check"),
                StaticSection(title="User Profile", content="Sign in to view your profile details", icon="user"),
            ],
            conversation_history=[ConversationHistoryItem(question=raw_question, answer="AI service error")],
            dynamic_sections=[],
            message=fallback_message,
        )


@app.post("/ask-assistant", response_model=AskAssistantResponse)
def ask_assistant(request: AskAssistantRequest) -> AskAssistantResponse:
    return _process_chat(request)


@app.post("/chat", response_model=AskAssistantResponse)
def chat(request: AskAssistantRequest) -> AskAssistantResponse:
    return _process_chat(request)


@app.get("/service-details/{service_name}")
def get_service_details(
    service_name: str, 
    language: str = Query("en", regex="^(uz|ru|en)$")
) -> dict[str, Any]:
    """Get complete end-to-end workflow details for a service."""
    try:
        services = get_services(force_reload=False)
        details = generate_service_details(service_name, language, services)
        return details
    except Exception as exc:
        logging.exception("Failed to get service details")
        return {
            "error": str(exc),
            "type": "service_details",
            "language": language,
        }


@app.get("/test-ai")
def test_ai() -> dict[str, Any]:
    return test_gemini_connection()


@app.post("/execute-service", response_model=ExecuteServiceResponse)
def execute_service(request: ExecuteServiceRequest) -> ExecuteServiceResponse:
    execution_id = f"exec-{uuid4().hex[:12]}"

    stages = _generate_execution_stages(request.service_name)
    queue_info = _generate_queue_info(request.service_name)

    execution_state = {
        "execution_id": execution_id,
        "service_name": request.service_name,
        "form_data": request.form_data,
        "stages": stages,
        "queue_info": queue_info,
        "status": "in_progress",
        "current_stage_index": 0,
        "started_at": time.time(),
        "final_result": None,
    }

    EXECUTIONS_DB[execution_id] = execution_state

    return ExecuteServiceResponse(
        execution_id=execution_id,
        service_name=request.service_name,
        status="in_progress",
        stages=stages,
        queue_info=queue_info,
        final_result=None,
    )


@app.get("/execute-service/{execution_id}", response_model=ExecuteServiceResponse)
def get_execution_status(execution_id: str) -> ExecuteServiceResponse:
    if execution_id not in EXECUTIONS_DB:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution_state = EXECUTIONS_DB[execution_id]
    _refresh_execution_state(execution_state)

    stages = execution_state.get("stages", [])
    service_name = execution_state.get("service_name", "Unknown")
    status = execution_state.get("status", "in_progress")
    queue_info = execution_state.get("queue_info")
    final_result = execution_state.get("final_result")

    return ExecuteServiceResponse(
        execution_id=execution_id,
        service_name=service_name,
        status=status,
        stages=stages,
        queue_info=queue_info,
        final_result=final_result,
    )


@app.post("/execute-service/{execution_id}/complete")
def complete_service(execution_id: str) -> ExecuteServiceResponse:
    if execution_id not in EXECUTIONS_DB:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution_state = EXECUTIONS_DB[execution_id]
    _refresh_execution_state(execution_state)

    if execution_state.get("status") == "completed":
        return ExecuteServiceResponse(
            execution_id=execution_id,
            service_name=execution_state.get("service_name", "Unknown"),
            status="completed",
            stages=execution_state.get("stages", []),
            queue_info=execution_state.get("queue_info"),
            final_result=execution_state.get("final_result"),
        )

    service_name = execution_state.get("service_name", "Unknown")

    stages = execution_state.get("stages", [])
    for stage in stages:
        stage.status = "done"

    final_result = _generate_final_result(service_name)

    execution_state["status"] = "completed"
    execution_state["stages"] = stages
    execution_state["final_result"] = final_result

    return ExecuteServiceResponse(
        execution_id=execution_id,
        service_name=service_name,
        status="completed",
        stages=stages,
        queue_info=execution_state.get("queue_info"),
        final_result=final_result,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    matches = detect_scenarios(request.text)

    if not matches:
        return AnalyzeResponse(language=request.language, scenarios=[])

    localized = [
        to_localized_scenario_hint(
            scenario_id=match["id"],
            confidence=match["confidence"],
            language=request.language,
            matched_keywords=match["matched_keywords"],
        )
        for match in matches[:3]
    ]

    return AnalyzeResponse(language=request.language, scenarios=localized)


@app.get("/api/scenarios")
def list_scenarios(language: str = "en") -> dict:
    language = language if language in {"en", "ru", "uz"} else "en"
    return {
        "scenarios": [
            {
                "id": scenario_id,
                "title": scenario["title"].in_lang(language),
            }
            for scenario_id, scenario in SCENARIOS.items()
        ]
    }

    language = language if language in {"en", "ru", "uz"} else "en"
    detail = to_localized_scenario_detail(scenario_id=scenario_id, language=language)
    return ScenarioDetail(**detail)
