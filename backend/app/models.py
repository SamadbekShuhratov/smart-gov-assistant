from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Language = Literal["en", "ru", "uz"]


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=5, max_length=1000)
    language: Language = "en"


class ScenarioHint(BaseModel):
    id: str
    title: str
    confidence: int
    why: str


class AnalyzeResponse(BaseModel):
    language: Language
    scenarios: List[ScenarioHint]


class ServiceStep(BaseModel):
    order: int
    service: str
    purpose: str
    provider: str


class SimilarServiceDiff(BaseModel):
    service_a: str
    service_b: str
    difference: str
    when_to_choose_a: str
    when_to_choose_b: str


class ScenarioDetail(BaseModel):
    id: str
    title: str
    summary: str
    service_chain: List[ServiceStep]
    required_documents: List[str]
    similar_services: List[SimilarServiceDiff]


class AnalyzeV2Request(BaseModel):
    query: str = Field(min_length=2, max_length=1000)


class AnalyzeStep(BaseModel):
    id: int
    title: str
    description: str
    required_documents: List[str]
    estimated_time: str
    next_steps: List[int]


class AnalyzeDifference(BaseModel):
    service1: str
    service2: str
    explanation: str


class AnalyzeV2Response(BaseModel):
    language: Language
    scenario: str
    steps: List[AnalyzeStep]
    differences: List[AnalyzeDifference]
    recommendations: List[str]
    buttons: dict[str, str]
    message: str = ""


class DynamicAnalyzeRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    language: Optional[Language] = None


class DynamicAnalyzeStep(BaseModel):
    id: int
    service_name: str
    title: str
    description: str
    original_name: Optional[str] = None
    original_description: Optional[str] = None
    translated_name: Optional[str] = None
    translated_description: Optional[str] = None
    category: str
    required_documents: List[str]
    estimated_time: str
    form_fields: dict[str, bool] = Field(default_factory=dict)


class DynamicAnalyzeDifference(BaseModel):
    service1: str
    service2: str
    explanation: str


class DynamicAnalyzeSection(BaseModel):
    title: str
    steps: List[DynamicAnalyzeStep]


class DynamicAnalyzeResponse(BaseModel):
    scenario: str
    scenario_display: str = ""
    sections: List[DynamicAnalyzeSection] = Field(default_factory=list)
    steps: List[DynamicAnalyzeStep]
    differences: List[DynamicAnalyzeDifference]
    recommendations: List[str]
    suggested_scenarios: List[str] = Field(default_factory=list)
    message: str = ""


class AskAssistantRequest(BaseModel):
    question: Optional[str] = Field(default=None, min_length=2, max_length=1000)
    message: Optional[str] = Field(default=None, min_length=2, max_length=1000)
    language: Optional[Language] = None

    @model_validator(mode="after")
    def fill_question_from_message(self) -> "AskAssistantRequest":
        if not self.question and self.message:
            self.question = self.message
        if not self.question:
            raise ValueError("question or message is required")
        return self


class AskAssistantRoadmapStep(BaseModel):
    id: int
    title: str
    description: str
    estimated_time: str


class AskAssistantRoadmapSection(BaseModel):
    section: str
    steps: List[AskAssistantRoadmapStep]


class AskAssistantSuggestedService(BaseModel):
    id: str
    name: str
    category: str
    reason: str
    description: Optional[str] = None
    original_name: Optional[str] = None
    original_description: Optional[str] = None
    translated_name: Optional[str] = None
    translated_description: Optional[str] = None



class StaticSection(BaseModel):
    title: str
    content: str
    icon: Optional[str] = None


class ConversationHistoryItem(BaseModel):
    question: str
    answer: str


class DynamicSectionStep(BaseModel):
    title: str
    description: str
    estimated_time: str


class DynamicRecommendedService(BaseModel):
    name: str
    reason: str


class DynamicSection(BaseModel):
    section: str
    steps: List[DynamicSectionStep] = Field(default_factory=list)
    recommended_services: List[DynamicRecommendedService] = Field(default_factory=list)


class AskAssistantResponse(BaseModel):
    answer: str
    roadmap: List[AskAssistantRoadmapSection]
    recommended_services: List[AskAssistantSuggestedService]
    static_sections: List[StaticSection] = Field(default_factory=list)
    conversation_history: List[ConversationHistoryItem] = Field(default_factory=list)
    dynamic_sections: List[DynamicSection] = Field(default_factory=list)
    message: str = ""
    error: Optional[str] = None

class RagRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class RagSourceInfo(BaseModel):
    filename: str
    full_context_used: str
    highlight_quote: str


class RagResponse(BaseModel):
    answer: str
    source_info: RagSourceInfo


class FamilyMember(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    birth_date: str = Field(min_length=10, max_length=10)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    passport_number: str = Field(min_length=5, max_length=30)
    birth_date: str = Field(min_length=10, max_length=10)
    address: str = Field(min_length=3, max_length=300)
    family_members: List[FamilyMember] = Field(default_factory=list)


class RegisterResponse(BaseModel):
    username: str
    message: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileResponse(BaseModel):
    username: str
    full_name: str
    passport_number: str
    birth_date: str
    address: str
    family_members: List[FamilyMember]


class AutoFillRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    form_type: str = Field(min_length=2, max_length=100)


class AutoFillResponse(BaseModel):
    username: str
    form_type: str
    full_name: Optional[str] = None
    passport_number: Optional[str] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    family_members: Optional[List[FamilyMember]] = None


class ExecuteStage(BaseModel):
    stage: str
    status: Literal["done", "current", "pending"]


class QueueInfo(BaseModel):
    position: Optional[int] = None
    estimated_time: Optional[str] = None


class ExecuteServiceRequest(BaseModel):
    service_name: str = Field(min_length=2, max_length=300)
    form_data: dict = Field(default_factory=dict)


class ExecuteServiceResponse(BaseModel):
    execution_id: str
    service_name: str
    status: Literal["in_progress", "completed", "failed"]
    stages: List[ExecuteStage]
    queue_info: Optional[QueueInfo] = None
    final_result: Optional[dict] = None
