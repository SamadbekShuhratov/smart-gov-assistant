import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bell,
  CheckCircle2,
  Clock3,
  FileText,
  LayoutGrid,
  Loader2,
  LogOut,
  Menu,
  ShieldCheck,
  Search,
  User2,
} from "lucide-react";
import AuthForm from "./AuthForm";
import ServiceExecutionFlow from "./ServiceExecutionFlow";
import { analyzeSituation, askAssistant, executeService, fetchAutofillData, fetchSuggestions } from "./api";
import { getStoredLanguage, getUiText, saveLanguage, translateServiceText } from "./i18n";

const QUESTION_KEYWORDS = {
  passport: [
    "passport",
    "pasport",
    "id card",
    "identity",
    "personal id",
    "паспорт",
    "удостовер",
    "id",
  ],
  birthDate: [
    "birth",
    "born",
    "date of birth",
    "child",
    "newborn",
    "minor",
    "age",
    "tug",
    "bola",
    "рожд",
    "ребен",
  ],
  address: [
    "address",
    "residence",
    "registration",
    "domicile",
    "location",
    "house",
    "home",
    "property",
    "housing",
    "квартир",
    "дом",
    "адрес",
    "пропис",
    "uy",
    "manzil",
  ],
  family: [
    "family",
    "spouse",
    "child",
    "children",
    "dependent",
    "household",
    "marriage",
    "guardian",
    "parent",
    "member",
    "семь",
    "супруг",
    "дет",
    "oila",
    "farzand",
  ],
  queueOnly: ["queue", "appointment", "booking", "slot", "navbat", "очеред"],
};

const LIFE_SITUATION_SUGGESTIONS = ["Bola tug‘ildi", "Uy sotib olish"];

function detectIntent(query) {
  const normalized = String(query || "").toLowerCase();
  if (!normalized.trim()) {
    return "unknown";
  }

  if (
    ["bola", "tug", "birth", "newborn", "ребен", "рожд"].some((token) => normalized.includes(token))
  ) {
    return "birth";
  }

  if (
    ["uy", "housing", "home", "house", "mortgage", "дом", "жиль", "ипотек"].some((token) =>
      normalized.includes(token)
    )
  ) {
    return "housing";
  }

  if (["ish", "work", "job", "employment", "работ", "труд"].some((token) => normalized.includes(token))) {
    return "employment";
  }

  if (["pension", "pensiya", "nafaqa", "пенси"].some((token) => normalized.includes(token))) {
    return "pension";
  }

  return "unknown";
}

function tokenizeForMatch(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]+/gu, " ")
    .split(/\s+/)
    .filter((token) => token.length > 2);
}

function buildQuestionConfig(step) {
  const backendFields = step?.form_fields;
  if (backendFields && typeof backendFields === "object") {
    return {
      fullName: Boolean(backendFields.full_name),
      passportNumber: Boolean(backendFields.passport_number),
      birthDate: Boolean(backendFields.birth_date),
      address: Boolean(backendFields.address),
      familyMembers: Boolean(backendFields.family_members),
    };
  }

  const title = String(step?.title || "").toLowerCase();
  const category = String(step?.category || "").toLowerCase();
  const description = String(step?.description || "").toLowerCase();
  const documents = Array.isArray(step?.required_documents)
    ? step.required_documents.join(" ").toLowerCase()
    : "";
  const fullText = `${title} ${category} ${description} ${documents}`;

  const hasKeyword = (keywords) => keywords.some((keyword) => fullText.includes(keyword));

  const queueOnly = hasKeyword(QUESTION_KEYWORDS.queueOnly) && !hasKeyword(QUESTION_KEYWORDS.family);

  const needsFamily = hasKeyword(QUESTION_KEYWORDS.family);
  const needsAddress = hasKeyword(QUESTION_KEYWORDS.address);
  const needsBirthDate = hasKeyword(QUESTION_KEYWORDS.birthDate) || needsFamily;
  const needsPassport = hasKeyword(QUESTION_KEYWORDS.passport) || !queueOnly;

  return {
    fullName: true,
    passportNumber: needsPassport,
    birthDate: needsBirthDate,
    address: needsAddress,
    familyMembers: needsFamily,
  };
}

function App() {
  const API_BASE = import.meta.env.VITE_API_BASE || "";
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [uiLanguage, setUiLanguage] = useState(() => getStoredLanguage());
  const [lastAnalyzeQuery, setLastAnalyzeQuery] = useState("");
  const [lastAssistantQuestion, setLastAssistantQuestion] = useState("");
  const [isSimpleMode, setIsSimpleMode] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isSuggestLoading, setIsSuggestLoading] = useState(false);
  const [selectedMainService, setSelectedMainService] = useState("");
  const [mainServiceStep, setMainServiceStep] = useState(null);
  const [similarServiceSuggestions, setSimilarServiceSuggestions] = useState([]);
  const [activeServiceId, setActiveServiceId] = useState(null);
  const [authToken, setAuthToken] = useState("");
  const [authUsername, setAuthUsername] = useState("");
  const [serviceForms, setServiceForms] = useState({});
  const [autoFillLoadingByStep, setAutoFillLoadingByStep] = useState({});
  const [autoFillErrorByStep, setAutoFillErrorByStep] = useState({});
  const [toastMessage, setToastMessage] = useState("");
  const [authTabTarget, setAuthTabTarget] = useState("login");
  const [showAuthForm, setShowAuthForm] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeNav, setActiveNav] = useState("menuDashboard");
  const [currentExecution, setCurrentExecution] = useState(null);
  const [showExecutionFlow, setShowExecutionFlow] = useState(false);
  const [assistantQuery, setAssistantQuery] = useState("");
  const [assistantResult, setAssistantResult] = useState(null);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState("");
  const [assistantHistory, setAssistantHistory] = useState([]);
  const [selectedAssistantHistoryId, setSelectedAssistantHistoryId] = useState(null);
  const [serviceDetailsModal, setServiceDetailsModal] = useState(null);
  const [serviceDetailsLoading, setServiceDetailsLoading] = useState(false);
  const [isFormSubmitted, setIsFormSubmitted] = useState(false);

  const ui = useMemo(() => getUiText(uiLanguage), [uiLanguage]);
  const language = uiLanguage;
  const setLanguage = setUiLanguage;
  const tService = (text, type = "text") => translateServiceText(text, uiLanguage, type);
  const detectedIntent = useMemo(() => detectIntent(query), [query]);
  const detectedIntentText =
    {
      birth: ui.intentBirth,
      housing: ui.intentHousing,
      employment: ui.intentEmployment,
      pension: ui.intentPension,
      unknown: ui.intentUnknown,
    }[detectedIntent] || ui.intentUnknown;

  // Restore auth token from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("authToken");
    const storedUsername = localStorage.getItem("authUsername");
    if (storedToken && storedUsername) {
      setAuthToken(storedToken);
      setAuthUsername(storedUsername);
      setShowAuthForm(false);
    }
  }, []);

  useEffect(() => {
    saveLanguage(uiLanguage);
  }, [uiLanguage]);

  useEffect(() => {
    // Keep results aligned with selected language.
    setAssistantError("");

    if (lastAnalyzeQuery) {
      runAnalyze(lastAnalyzeQuery);
    } else {
      setResult(null);
    }

    if (lastAssistantQuestion) {
      runAskAssistant(lastAssistantQuestion, false);
    } else {
      setAssistantResult(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uiLanguage]);

  const scenarioTitle = useMemo(() => {
    if (!result) {
      return "";
    }
    if (result?.scenario_display) {
      return result.scenario_display;
    }
    return ui.scenarioTitles?.[result.scenario] || ui.scenarioTitles?.dynamic || "";
  }, [result, ui]);

  const roadmapSections = useMemo(() => {
    if (!result) {
      return [];
    }

    if (Array.isArray(result.sections) && result.sections.length > 0) {
      return result.sections.map((section) => ({
        title: section.title,
        steps: Array.isArray(section.steps)
          ? section.steps.map((step) => ({
              ...step,
              title: step.title || step.service_name || "Service",
            }))
          : [],
      }));
    }

    if (Array.isArray(result.steps) && result.steps.length > 0) {
      return [
        {
          title: ui.general,
          steps: result.steps.map((step) => ({
            ...step,
            title: step.title || step.service_name || "Service",
          })),
        },
      ];
    }

    return [];
  }, [result, ui.general]);

  const roadmapSteps = useMemo(() => roadmapSections.flatMap((section) => section.steps || []), [roadmapSections]);
  const visibleRoadmapSections = useMemo(() => {
    // Always show full roadmap information; auth only gates actions, not visibility.
    return roadmapSections;
  }, [roadmapSections]);

  const visibleRoadmapSteps = useMemo(
    () => visibleRoadmapSections.flatMap((section) => section.steps || []),
    [visibleRoadmapSections]
  );

  const activeServiceStep = useMemo(
    () => roadmapSteps.find((step) => step.id === activeServiceId) || null,
    [roadmapSteps, activeServiceId]
  );

  useEffect(() => {
    if (!roadmapSteps.length) {
      setIsFormSubmitted(false);
      setServiceForms({});
      setMainServiceStep(null);
      setSimilarServiceSuggestions([]);
      setActiveServiceId(null);
      return;
    }

    setIsFormSubmitted(false);
    setActiveServiceId(null);
    const nextForms = {};
    roadmapSteps.forEach((step) => {
      nextForms[step.id] = {
        full_name: "",
        passport_number: "",
        birth_date: "",
        address: "",
        family_members: [{ name: "", birth_date: "" }],
      };
    });
    setServiceForms(nextForms);
    setAutoFillLoadingByStep({});
    setAutoFillErrorByStep({});
  }, [roadmapSteps]);

  useEffect(() => {
    if (!roadmapSteps.length) {
      setMainServiceStep(null);
      setSimilarServiceSuggestions([]);
      return;
    }

    const target = selectedMainService.trim().toLowerCase();
    let mainStep = roadmapSteps[0];

    if (target) {
      const exact = roadmapSteps.find((step) => step.title.trim().toLowerCase() === target);
      const partial = roadmapSteps.find((step) => step.title.trim().toLowerCase().includes(target));
      mainStep = exact || partial || mainStep;
    }

    setMainServiceStep(mainStep);

    const mainTokens = new Set(tokenizeForMatch(`${mainStep.title} ${mainStep.description} ${mainStep.category}`));
    const scoredRelated = roadmapSteps
      .filter((step) => step.id !== mainStep.id)
      .map((step) => {
        const tokens = tokenizeForMatch(`${step.title} ${step.description} ${step.category}`);
        const overlap = tokens.filter((token) => mainTokens.has(token)).length;
        const sameCategory =
          String(step.category || "").toLowerCase() === String(mainStep.category || "").toLowerCase();
        const score = overlap + (sameCategory ? 3 : 0);
        return { step, score };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 4)
      .map((item) => item.step);

    setSimilarServiceSuggestions(scoredRelated);
  }, [roadmapSteps, selectedMainService]);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSuggestions([]);
      setIsSuggestLoading(false);
      return;
    }

    const timer = window.setTimeout(async () => {
      setIsSuggestLoading(true);
      try {
        const data = await fetchSuggestions(term);
        setSuggestions(data.suggestions || []);
      } catch {
        setSuggestions([]);
      } finally {
        setIsSuggestLoading(false);
      }
    }, 350);

    return () => {
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    if (!toastMessage) {
      return;
    }

    const timer = window.setTimeout(() => {
      setToastMessage("");
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [toastMessage]);

  const runAnalyze = async (searchQuery) => {
    setError("");
    setShowSuggestions(false);
    setIsFormSubmitted(false);

    if (!searchQuery.trim()) {
      return;
    }

    setQuery(searchQuery);
    setSelectedMainService(searchQuery);
    setLastAnalyzeQuery(searchQuery.trim());
    setActiveServiceId(null);

    setIsLoading(true);
    try {
      const response = await analyzeSituation(searchQuery.trim(), uiLanguage);
      setResult(response);
    } catch {
      setError(ui.backendFriendlyError);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    await runAnalyze(query);
  };

  const handleSelectService = (service) => {
    if (!service) {
      return;
    }
    setSelectedMainService(service.title || service.name || "");
    setActiveServiceId(null);
    setIsFormSubmitted(false);
  };

  const handleOpenServiceFlow = (service) => {
    if (!service) {
      return;
    }
    setSelectedMainService(service.title || service.name || "");
    setIsFormSubmitted(false);
    if (typeof service.id === "number") {
      setActiveServiceId(service.id);
    }
  };

  const handleViewServiceDetails = async (serviceName) => {
    if (!serviceName) {
      return;
    }
    setServiceDetailsLoading(true);
    try {
      const response = await fetch(
        `${API_BASE}/service-details/${encodeURIComponent(serviceName)}?language=${uiLanguage}`
      );
      if (!response.ok) {
        throw new Error("Failed to load service details");
      }
      const details = await response.json();
      setServiceDetailsModal(details);
    } catch (error) {
      console.error("Error loading service details:", error);
      setToastMessage(ui.loadServiceDetailsError || "Failed to load service details");
    } finally {
      setServiceDetailsLoading(false);
    }
  };

  const handleLoginSuccess = ({ token, username }) => {
    setAuthToken(token);
    setAuthUsername(username);
    setAutoFillErrorByStep({});
    localStorage.setItem("authToken", token);
    localStorage.setItem("authUsername", username);
    setShowAuthForm(false);
    setToastMessage(ui.authLoginSuccess);
  };

  const handleLogout = () => {
    setAuthToken("");
    setAuthUsername("");
    localStorage.removeItem("authToken");
    localStorage.removeItem("authUsername");
    setShowAuthForm(false);
    setToastMessage(ui.authLogoutSuccess);
  };

  const openAuthPanel = (tab) => {
    setAuthTabTarget(tab === "register" ? "register" : "login");
    setShowAuthForm(true);
    const element = document.getElementById("auth-section");
    if (element) {
      window.setTimeout(() => {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
    }
  };

  const handleNavClick = (key) => {
    setActiveNav(key);
    if (key === "menuDashboard") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      setToastMessage(ui.dashboardOpened);
    } else {
      setToastMessage(ui.sectionSoon);
    }
    setIsSidebarOpen(false);
  };

  const handleStartService = async (stepId, title) => {
    if (!authToken) {
      setToastMessage(ui.lockTitle);
      setAuthTabTarget("login");
      setShowAuthForm(true);
      return;
    }

    setToastMessage(`${tService(title)} ${ui.started}`);

    try {
      const formData = serviceForms[stepId] || {};
      const execution = await executeService(tService(title), formData);

      setCurrentExecution(execution);
      setShowExecutionFlow(true);
    } catch {
      setToastMessage(ui.backendFriendlyError);
    }
  };

  const updateServiceField = (stepId, field, value) => {
    setServiceForms((prev) => ({
      ...prev,
      [stepId]: {
        ...(prev[stepId] || {}),
        [field]: value,
      },
    }));
  };

  const updateFamilyMember = (stepId, index, field, value) => {
    setServiceForms((prev) => {
      const current = prev[stepId] || { family_members: [] };
      const members = [...(current.family_members || [])];
      members[index] = { ...(members[index] || { name: "", birth_date: "" }), [field]: value };
      return {
        ...prev,
        [stepId]: {
          ...current,
          family_members: members,
        },
      };
    });
  };

  const addFamilyMemberRow = (stepId) => {
    setServiceForms((prev) => {
      const current = prev[stepId] || {};
      return {
        ...prev,
        [stepId]: {
          ...current,
          family_members: [...(current.family_members || []), { name: "", birth_date: "" }],
        },
      };
    });
  };

  const removeFamilyMemberRow = (stepId, index) => {
    setServiceForms((prev) => {
      const current = prev[stepId] || {};
      const existing = current.family_members || [];
      const nextMembers = existing.filter((_, itemIndex) => itemIndex !== index);
      return {
        ...prev,
        [stepId]: {
          ...current,
          family_members: nextMembers.length ? nextMembers : [{ name: "", birth_date: "" }],
        },
      };
    });
  };

  const handleAutoFill = async (stepId) => {
    if (!authToken) {
      setAutoFillErrorByStep((prev) => ({
        ...prev,
        [stepId]: ui.autoFillHelp,
      }));
      return;
    }

    setAutoFillLoadingByStep((prev) => ({ ...prev, [stepId]: true }));
    setAutoFillErrorByStep((prev) => ({ ...prev, [stepId]: "" }));
    try {
      const data = await fetchAutofillData(authUsername || "demo", "full_application_all", authToken);

      setServiceForms((prev) => ({
        ...prev,
        [stepId]: {
          ...(prev[stepId] || {}),
          full_name: data.full_name || "",
          passport_number: data.passport_number || "",
          birth_date: data.birth_date || "",
          address: data.address || "",
          family_members:
            data.family_members?.length
              ? data.family_members.map((member) => ({
                  name: member.name || "",
                  birth_date: member.birth_date || "",
                }))
              : [{ name: "", birth_date: "" }],
        },
      }));

      setToastMessage(ui.autoFilledSuccess);
    } catch (error) {
      const status = typeof error?.status === "number" ? error.status : null;
      const isUnauthorized = status === 401 || String(error?.message || "").includes("401");

      if (isUnauthorized) {
        setAuthToken("");
        setAuthUsername("");
        localStorage.removeItem("authToken");
        localStorage.removeItem("authUsername");
        setAuthTabTarget("login");
        setShowAuthForm(true);
        setAutoFillErrorByStep((prev) => ({
          ...prev,
          [stepId]: ui.autoFillSessionExpired,
        }));
        setToastMessage(ui.autoFillSessionExpired);
        return;
      }

      setAutoFillErrorByStep((prev) => ({
        ...prev,
        [stepId]: ui.autoFillUnavailable,
      }));
    } finally {
      setAutoFillLoadingByStep((prev) => ({ ...prev, [stepId]: false }));
    }
  };

  const inputBaseClass = "rounded-xl border px-3 py-2 text-sm outline-none focus:border-blue-300";
  const fieldClass = (value) =>
    `${inputBaseClass} ${value ? "border-emerald-200 bg-emerald-50/70" : "border-blue-100 bg-white"}`;

  useEffect(() => {
    try {
      const raw = localStorage.getItem("askAssistantHistory");
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        setAssistantHistory(parsed);
      }
    } catch {
      // Ignore invalid storage payload and continue with empty history.
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("askAssistantHistory", JSON.stringify(assistantHistory));
    } catch {
      // Ignore storage write failures in MVP mode.
    }
  }, [assistantHistory]);

  const displayedAssistantResult = assistantResult;

  const visibleAssistantRoadmap = useMemo(() => {
    const roadmap = displayedAssistantResult?.roadmap || [];
    if (authToken) {
      return roadmap;
    }

    let left = 2;
    return roadmap
      .map((section) => {
        if (left <= 0) {
          return { ...section, steps: [] };
        }
        const steps = (section.steps || []).slice(0, left);
        left -= steps.length;
        return { ...section, steps };
      })
      .filter((section) => (section.steps || []).length > 0);
  }, [displayedAssistantResult, authToken]);

  const runAskAssistant = async (question, saveToHistory = true) => {
    const clean = String(question || "").trim();
    if (!clean) {
      return;
    }

    setAssistantError("");
    setAssistantLoading(true);
    setLastAssistantQuestion(clean);
    try {
      console.log("Sending:", clean);
      const response = await askAssistant(clean, uiLanguage);
      console.log("Response:", response);

      // Only reject if we have no actual data to show, not just because error field is present
      const hasData = response?.answer || 
                      (response?.recommended_services && response.recommended_services.length > 0) ||
                      (response?.roadmap && response.roadmap.length > 0);
      
      if (!hasData && response?.error) {
        setAssistantResult(null);
        setAssistantError("AI not responding. Please try again.");
        return;
      }

      setAssistantResult(response);

      if (saveToHistory) {
        const historyItem = {
          id: `qa-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          question: clean,
          answer: response?.answer || ui.askAssistantFallback,
          created_at: new Date().toISOString(),
        };

        setAssistantHistory((prev) => [historyItem, ...prev].slice(0, 20));
        setSelectedAssistantHistoryId(historyItem.id);
      }
    } catch (error) {
      console.error("API error:", error);
      setAssistantResult(null);
      setAssistantError("AI not responding. Please try again.");
    } finally {
      setAssistantLoading(false);
    }
  };

  const handleAssistantSubmit = async (event) => {
    event.preventDefault();
    await runAskAssistant(assistantQuery);
  };

  return (
    <div className="portal-page min-h-screen p-3 sm:p-5">
      <div className="mx-auto grid max-w-[1440px] gap-4 lg:grid-cols-[270px_minmax(0,1fr)]">
        <aside
          className={`portal-sidebar rounded-3xl border border-white/10 p-5 text-slate-100 shadow-2xl ${
            isSidebarOpen ? "block" : "hidden"
          } lg:block`}
        >
          <div className="flex items-center gap-3 border-b border-white/10 pb-4">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-400/15 text-cyan-200">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="font-display text-lg font-bold">{ui.brandTitle}</p>
              <p className="text-xs text-slate-400">{ui.brandSubtitle}</p>
            </div>
          </div>

          <nav className="mt-5 space-y-1">
            {[
              { key: "menuDashboard" },
              { key: "menuAskAssistant" },
              { key: "menuPopularServices" },
              { key: "menuCategories" },
              { key: "menuPayments" },
              { key: "menuApplications" },
              { key: "menuRegistry" },
              { key: "menuProactiveServices" },
              { key: "menuMobileApps" },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => handleNavClick(item.key)}
                className={`portal-nav-item w-full rounded-xl px-3 py-2 text-left text-sm font-semibold transition ${
                  activeNav === item.key ? "bg-cyan-300/15 text-white" : "text-slate-300 hover:bg-white/10"
                }`}
              >
                {ui[item.key]}
              </button>
            ))}
          </nav>
        </aside>

        {isSidebarOpen && (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setIsSidebarOpen(false)}
            className="fixed inset-0 z-10 bg-slate-950/50 lg:hidden"
          />
        )}

        <main className="space-y-4">
          <header className="portal-topbar rounded-3xl border border-white/15 p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setIsSidebarOpen((prev) => !prev)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/8 text-white lg:hidden"
              >
                <Menu className="h-5 w-5" />
              </button>

              <div>
                <p className="font-display text-xl font-bold text-white">{ui.title}</p>
                <p className="text-xs text-cyan-100/80">{ui.subtitle}</p>
              </div>

              <div className="ml-auto flex items-center gap-2 sm:gap-3">
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  className="rounded-xl border border-white/25 bg-white/10 px-3 py-2 text-xs font-bold text-white outline-none"
                >
                  <option value="uz" className="text-slate-900">Uzbek</option>
                  <option value="ru" className="text-slate-900">Russian</option>
                  <option value="en" className="text-slate-900">English</option>
                </select>
                <button
                  type="button"
                  onClick={() => setToastMessage(ui.notificationsSoon)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white"
                >
                  <Bell className="h-4 w-4" />
                </button>
                {authToken ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setToastMessage(ui.profileSoon)}
                      className="inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-bold text-slate-900"
                    >
                      <User2 className="h-4 w-4" />
                      {ui.profile} ({authUsername || "user"})
                    </button>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-3 py-2 text-xs font-bold text-white transition hover:bg-white/20"
                    >
                      <LogOut className="h-4 w-4" />
                      {ui.logout}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={() => openAuthPanel("login")}
                      className="inline-flex items-center gap-2 rounded-xl border border-white/25 bg-white/10 px-3 py-2 text-xs font-bold text-white transition hover:bg-white/20"
                    >
                      {ui.login}
                    </button>
                    <button
                      type="button"
                      onClick={() => openAuthPanel("register")}
                      className="inline-flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-xs font-bold text-slate-900"
                    >
                      {ui.register}
                    </button>
                  </>
                )}
              </div>
            </div>
          </header>

          {activeNav !== "menuAskAssistant" && (
          <section className="portal-hero relative overflow-visible rounded-3xl p-5 sm:p-7">
            <div className="pointer-events-none absolute -right-10 -top-14 h-40 w-40 rounded-full bg-cyan-300/20 blur-3xl" />
            <div className="relative z-10">
              <div className="mb-4">
                <h1 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">{ui.title}</h1>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-300" />
                  <input
                    value={query}
                    onChange={(event) => {
                      setQuery(event.target.value);
                      setSelectedMainService(event.target.value);
                      setShowSuggestions(true);
                    }}
                    onFocus={() => setShowSuggestions(true)}
                    onBlur={() => {
                      window.setTimeout(() => setShowSuggestions(false), 150);
                    }}
                    placeholder={ui.placeholder}
                    className="w-full rounded-2xl border border-white/20 bg-slate-900/60 px-12 py-4 text-base text-white shadow-[0_10px_30px_rgba(2,6,23,0.35)] outline-none transition placeholder:text-slate-300 focus:border-cyan-300"
                  />

                  {showSuggestions && (isSuggestLoading || suggestions.length > 0) && (
                    <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-50 rounded-2xl border border-slate-700 bg-slate-900 p-2 text-left shadow-xl">
                      {isSuggestLoading && <p className="px-3 py-2 text-sm text-slate-300">{ui.searchingSuggestions}</p>}

                      {!isSuggestLoading &&
                        suggestions.map((item, index) => (
                          <button
                            key={`${item.name}-${index}`}
                            type="button"
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => {
                              setQuery(item.name);
                              setSelectedMainService(item.name);
                              setShowSuggestions(false);
                            }}
                            className="w-full rounded-xl px-3 py-2 text-left transition duration-200 hover:bg-white/10"
                          >
                            <p className="text-sm font-semibold text-white">{item.name}</p>
                            <p className="text-xs text-slate-300">{tService(item.category || ui.general, "category")}</p>
                          </button>
                        ))}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <p className="text-cyan-100/90">{ui.searchHint}</p>
                  <span className="rounded-full border border-cyan-200/40 bg-cyan-200/10 px-2.5 py-1 font-semibold text-cyan-50">
                    {ui.detectedIntentLabel}: {detectedIntentText}
                  </span>
                </div>

                {query.trim().length > 0 && (
                  <div className="flex flex-wrap items-center gap-2">
                    {LIFE_SITUATION_SUGGESTIONS.map((scenario) => (
                      <button
                        key={`typing-${scenario}`}
                        type="button"
                        onClick={() => {
                          setQuery(scenario);
                          setSelectedMainService(scenario);
                          runAnalyze(scenario);
                        }}
                        className="rounded-xl border border-white/20 bg-white/10 px-3 py-1.5 text-xs font-semibold text-cyan-50 transition hover:bg-white/20"
                      >
                        {scenario}
                      </button>
                    ))}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-white/10 px-3 py-2 text-sm text-white">
                    <input
                      type="checkbox"
                      checked={isSimpleMode}
                      onChange={(event) => setIsSimpleMode(event.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-cyan-500 focus:ring-cyan-400"
                    />
                    {ui.explainSimply}
                  </label>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="gov-btn-primary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    {isLoading ? ui.analyzing : ui.findServices}
                  </button>
                </div>
              </form>

              <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[ui.popularTagBirth, ui.popularTagHousing, ui.popularTagPension, ui.popularTagDocs].map((label) => (
                  <div key={label} className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-xs font-semibold text-cyan-50">
                    {label}
                  </div>
                ))}
              </div>

              <div className="mt-4">
                <p className="mb-2 text-xs font-bold uppercase tracking-wide text-cyan-100/90">{ui.suggestedScenariosTitle}</p>
                <div className="flex flex-wrap gap-2">
                  {(result?.suggested_scenarios?.length ? result.suggested_scenarios : ui.suggestedScenarios || []).map((item) => (
                    <button
                      key={`scenario-${item}`}
                      type="button"
                      onClick={() => runAnalyze(item)}
                      className="rounded-xl border border-white/20 bg-white/10 px-3 py-2 text-xs font-semibold text-cyan-50 transition hover:bg-white/20"
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>

              {isLoading && (
                <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-cyan-300/25 px-3 py-1.5 text-xs font-semibold text-cyan-50">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {ui.analyzing}
                </div>
              )}

              {error && (
                <p className="mt-4 rounded-2xl border border-rose-300/40 bg-rose-500/15 px-4 py-3 text-sm text-rose-100">
                  {error}
                </p>
              )}

              {result?.message && (
                <p className="mt-4 rounded-2xl border border-amber-300/40 bg-amber-400/15 px-4 py-3 text-sm text-amber-100">
                  {result.message}
                </p>
              )}
            </div>
          </section>
          )}

          {activeNav === "menuAskAssistant" && (
            <section className="space-y-5">
              <article className="gov-card rounded-2xl p-6">
                <h2 className="font-display text-3xl font-bold text-ink">{ui.askAssistantTitle}</h2>
                <form onSubmit={handleAssistantSubmit} className="mt-4 space-y-3">
                  <textarea
                    value={assistantQuery}
                    onChange={(event) => setAssistantQuery(event.target.value)}
                    placeholder={ui.askAssistantInputPlaceholder}
                    rows={4}
                    className="w-full rounded-2xl border border-blue-100 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-blue-300"
                  />
                  <button
                    type="submit"
                    disabled={assistantLoading}
                    className="gov-btn-primary inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm disabled:opacity-60"
                  >
                    {assistantLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    {ui.askAssistantSubmit}
                  </button>
                </form>
              </article>

              {assistantError && (
                <article className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                  {assistantError}
                </article>
              )}

              {displayedAssistantResult && (
                <>
                  <article className="rounded-2xl border border-cyan-200 bg-cyan-50 p-6 shadow-[0_10px_24px_rgba(11,79,156,0.08)]">
                    <h3 className="mb-2 font-display text-xl font-semibold text-cyan-900">{ui.askAssistantAnswer}</h3>
                    <p className="text-sm text-cyan-900">{displayedAssistantResult?.answer || ""}</p>
                    {displayedAssistantResult?.message && (
                      <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                        {displayedAssistantResult.message || ui.askAssistantFallback}
                      </p>
                    )}
                  </article>

                  {((displayedAssistantResult?.recommended_services || displayedAssistantResult?.suggested_services) || []).length > 0 && (
                    <article className="gov-card rounded-2xl p-6">
                      <h3 className="mb-4 font-display text-2xl font-semibold text-ink">{ui.askAssistantSuggestedServices}</h3>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {((displayedAssistantResult?.recommended_services || displayedAssistantResult?.suggested_services) || []).map((service, index) => (
                          <div key={`ask-service-${index}-${service.name}`} className="rounded-2xl border border-blue-100 bg-white p-4">
                            <p className="text-sm font-bold text-ink">{service.name}</p>
                            <p className="mt-1 text-xs text-slate-500">{tService(service.category, "category")}</p>
                            <p className="mt-2 text-xs text-slate-600">
                              {service.description || service.translated_description || service.reason || service.short_description}
                            </p>
                            <button
                              type="button"
                              onClick={() => handleStartService(service.id || index + 1, service.name)}
                              disabled={!authToken}
                              title={!authToken ? ui.lockTitle : ""}
                              className="gov-btn-primary mt-3 inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <ArrowRight className="h-3.5 w-3.5" />
                              {ui.startService}
                            </button>
                          </div>
                        ))}
                      </div>
                    </article>
                  )}
                </>
              )}
            </section>
          )}

          <div className="portal-widgets grid gap-4 md:grid-cols-2">
            <article className="rounded-3xl border border-cyan-200/30 bg-gradient-to-br from-[#0e2a5f] to-[#132d57] p-5 text-white">
              <p className="text-sm text-cyan-100">{ui.docsInOnePlace}</p>
              <h3 className="mt-2 font-display text-2xl font-bold">{ui.docsInOnePlaceTitle}</h3>
            </article>
            <article className="rounded-3xl border border-emerald-200/20 bg-gradient-to-br from-[#10382d] to-[#0e2d23] p-5 text-emerald-50">
              <p className="text-sm text-emerald-100">{ui.personalNotifications}</p>
              <h3 className="mt-2 font-display text-2xl font-bold">{ui.importantReminders}</h3>
            </article>
          </div>

          {showAuthForm && (
            <div id="auth-section" className="mb-8">
              <section className="gov-card rounded-3xl border-2 border-cyan-400/50 bg-gradient-to-br from-slate-800/80 to-slate-900/80 p-8 shadow-xl">
                <h2 className="font-display text-2xl font-bold text-white">{ui.authTitle}</h2>
                <p className="mt-2 text-sm text-slate-300">{ui.authSubtitle}</p>
                <div className="mt-6">
                  <AuthForm onLoginSuccess={handleLoginSuccess} activeTab={authTabTarget} language={uiLanguage} />
                </div>
              </section>
            </div>
          )}

          {!result && !isLoading && (
            <section className="gov-card rounded-3xl p-8 text-center">
              <div className="mx-auto mb-3 inline-flex h-12 w-12 items-center justify-center rounded-full bg-cyan-100 text-cyan-700">
                <LayoutGrid className="h-5 w-5" />
              </div>
              <h3 className="font-display text-xl font-semibold text-ink">{ui.emptyTitle}</h3>
              <p className="mt-1 text-sm text-slate-600">{ui.emptyBody}</p>
            </section>
          )}

          {result && (
            <section className="space-y-6">
              <article className="gov-card rounded-2xl p-6">
                <h2 className="font-display text-3xl font-bold text-ink">
                  {ui.roadmapTitlePrefix} {scenarioTitle}
                </h2>
              </article>

              {mainServiceStep && (
                <article className="gov-card rounded-2xl p-6">
                  <h3 className="mb-4 font-display text-2xl font-semibold text-ink">{ui.selectedService}</h3>
                  <div className="rounded-2xl border border-blue-100 bg-white p-4">
                    <p className="text-lg font-bold text-ink">{tService(mainServiceStep.title, "serviceName")}</p>
                    <p className="mt-1 text-xs text-slate-500">{tService(mainServiceStep.category, "category")}</p>
                    <p className="mt-2 text-sm text-slate-700">{toSimpleText(tService(mainServiceStep.description), isSimpleMode)}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleOpenServiceFlow(mainServiceStep)}
                        className="gov-btn-primary inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs"
                      >
                        <ArrowRight className="h-4 w-4" />
                        {ui.startService}
                      </button>
                    </div>
                  </div>
                </article>
              )}

              {activeServiceStep && (
                <article className="gov-card rounded-2xl p-6">
                  <h3 className="mb-5 font-display text-2xl font-semibold text-ink">{ui.serviceForm}</h3>

                  <div className="sticky top-4 z-20 mb-5 rounded-2xl border border-blue-100 bg-blue-50/90 p-4 backdrop-blur-sm shadow-[0_8px_20px_rgba(11,79,156,0.10)]">
                    <div className="mb-3 flex items-center justify-between text-sm font-semibold text-blue-800">
                      <span>
                        {isFormSubmitted ? "1/1" : "0/1"} {isFormSubmitted ? ui.formSubmissionDone : ui.formSubmissionPending}
                      </span>
                    </div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-blue-100">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-500 ease-out"
                        style={{ width: `${isFormSubmitted ? 100 : 0}%` }}
                      />
                    </div>
                  </div>

                  <div className="mb-6 rounded-2xl border border-blue-100 bg-white p-4 shadow-[0_8px_20px_rgba(11,79,156,0.08)]">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-blue-200 bg-blue-50 text-sm font-bold text-blue-700">
                        {activeServiceStep.id}
                      </span>
                      <h4 className="text-lg font-bold text-ink">{tService(activeServiceStep.title, "serviceName")}</h4>
                      <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700">
                        {tService(activeServiceStep.category, "category")}
                      </span>
                    </div>

                    <p className="text-sm leading-relaxed text-slate-700">{toSimpleText(tService(activeServiceStep.description), isSimpleMode)}</p>

                    <div className="mt-4">
                      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">{ui.documents}</p>
                      <ul className="space-y-1.5">
                        {activeServiceStep.required_documents?.map((doc, index) => (
                          <li key={`${activeServiceStep.id}-${index}-${doc}`} className="inline-flex items-start gap-2 text-sm text-slate-700">
                            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-blue-700" />
                            <span>{doc}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <p className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
                        <Clock3 className="h-4 w-4 text-blue-700" />
                        {ui.estimatedTime}: {activeServiceStep.estimated_time}
                      </p>

                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => handleViewServiceDetails(activeServiceStep.name || activeServiceStep.title)}
                          disabled={serviceDetailsLoading}
                          className="gov-btn-secondary inline-flex items-center gap-2 rounded-xl border border-blue-700 bg-white px-4 py-2 text-xs text-blue-700 transition hover:bg-blue-50 disabled:opacity-60"
                        >
                          <FileText className="h-4 w-4" />
                          {ui.viewDetails || "View Details"}
                        </button>
                      </div>
                    </div>

                    <div className="mt-4 rounded-2xl border border-blue-100 bg-slate-50/80 p-4">
                      {(() => {
                        const questionConfig = buildQuestionConfig(activeServiceStep);
                        return (
                          <>
                            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                              <h5 className="text-sm font-bold text-slate-800">{ui.serviceForm}</h5>
                              <button
                                type="button"
                                onClick={() => handleAutoFill(activeServiceStep.id)}
                                disabled={!authToken || Boolean(autoFillLoadingByStep[activeServiceStep.id])}
                                title={!authToken ? ui.autoFillHelp : ui.autoFill}
                                className="gov-btn-primary inline-flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs disabled:opacity-60"
                              >
                                {autoFillLoadingByStep[activeServiceStep.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                                {ui.autoFill}
                              </button>
                            </div>

                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                              {questionConfig.fullName && (
                                <input
                                  value={serviceForms[activeServiceStep.id]?.full_name || ""}
                                  onChange={(event) => updateServiceField(activeServiceStep.id, "full_name", event.target.value)}
                                  placeholder={ui.fullName}
                                  className={fieldClass(serviceForms[activeServiceStep.id]?.full_name)}
                                />
                              )}
                              {questionConfig.passportNumber && (
                                <input
                                  value={serviceForms[activeServiceStep.id]?.passport_number || ""}
                                  onChange={(event) => updateServiceField(activeServiceStep.id, "passport_number", event.target.value)}
                                  placeholder={ui.passportNumber}
                                  className={fieldClass(serviceForms[activeServiceStep.id]?.passport_number)}
                                />
                              )}
                              {questionConfig.birthDate && (
                                <input
                                  value={serviceForms[activeServiceStep.id]?.birth_date || ""}
                                  onChange={(event) => updateServiceField(activeServiceStep.id, "birth_date", event.target.value)}
                                  placeholder={ui.birthDate}
                                  className={fieldClass(serviceForms[activeServiceStep.id]?.birth_date)}
                                />
                              )}
                              {questionConfig.address && (
                                <input
                                  value={serviceForms[activeServiceStep.id]?.address || ""}
                                  onChange={(event) => updateServiceField(activeServiceStep.id, "address", event.target.value)}
                                  placeholder={ui.address}
                                  className={fieldClass(serviceForms[activeServiceStep.id]?.address)}
                                />
                              )}
                            </div>

                            {questionConfig.familyMembers && (
                              <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/50 p-3">
                                <div className="mb-2 flex items-center justify-between">
                                  <p className="text-xs font-bold uppercase tracking-wide text-blue-800">{ui.familyMembers}</p>
                                  <button
                                    type="button"
                                    onClick={() => addFamilyMemberRow(activeServiceStep.id)}
                                    className="rounded-lg bg-white px-2.5 py-1 text-xs font-semibold text-blue-700 transition hover:bg-blue-100"
                                  >
                                    {ui.add}
                                  </button>
                                </div>

                                <div className="space-y-2">
                                  {(serviceForms[activeServiceStep.id]?.family_members || [{ name: "", birth_date: "" }]).map((member, index) => (
                                    <div key={`${activeServiceStep.id}-member-${index}`} className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                                      <input
                                        value={member.name || ""}
                                        onChange={(event) => updateFamilyMember(activeServiceStep.id, index, "name", event.target.value)}
                                        placeholder={ui.memberName}
                                        className={`rounded-lg border px-3 py-2 text-sm outline-none focus:border-blue-300 sm:col-span-6 ${
                                          member.name ? "border-emerald-200 bg-emerald-50/70" : "border-blue-100 bg-white"
                                        }`}
                                      />
                                      <input
                                        value={member.birth_date || ""}
                                        onChange={(event) => updateFamilyMember(activeServiceStep.id, index, "birth_date", event.target.value)}
                                        placeholder={ui.birthDate}
                                        className={`rounded-lg border px-3 py-2 text-sm outline-none focus:border-blue-300 sm:col-span-4 ${
                                          member.birth_date ? "border-emerald-200 bg-emerald-50/70" : "border-blue-100 bg-white"
                                        }`}
                                      />
                                      <button
                                        type="button"
                                        onClick={() => removeFamilyMemberRow(activeServiceStep.id, index)}
                                        className="rounded-lg bg-rose-50 px-2 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 sm:col-span-2"
                                      >
                                        {ui.remove}
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {!authToken && <p className="mt-2 text-xs text-slate-500">{ui.autoFillHelp}</p>}

                            {autoFillErrorByStep[activeServiceStep.id] && (
                              <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{autoFillErrorByStep[activeServiceStep.id]}</p>
                            )}

                            <button
                              type="button"
                              onClick={() => setIsFormSubmitted(true)}
                              disabled={isFormSubmitted}
                              className="mt-4 gov-btn-primary w-full rounded-xl px-4 py-3 text-sm font-semibold disabled:opacity-60"
                            >
                              {isFormSubmitted ? `✓ ${ui.submittedLabel}` : ui.submitApplication}
                            </button>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                </article>
              )}

              {similarServiceSuggestions.length > 0 && (
                <article className="gov-card rounded-2xl p-6">
                  <h3 className="mb-3 font-display text-2xl font-semibold text-ink">{ui.similarServiceSuggestions}</h3>
                  <p className="mb-4 text-sm text-slate-600">{ui.relevantServicesOnly}</p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {similarServiceSuggestions.map((service) => (
                      <div
                        key={`similar-${service.id}`}
                        className="rounded-2xl border border-blue-100 bg-white p-4 text-left shadow-[0_8px_20px_rgba(11,79,156,0.08)]"
                      >
                        <p className="text-sm font-bold text-ink">{tService(service.title, "serviceName")}</p>
                        <p className="mt-1 text-xs text-slate-500">{tService(service.category, "category")}</p>
                        <p className="mt-2 text-xs text-slate-600">{toSimpleText(tService(service.description), isSimpleMode)}</p>
                        <div className="mt-3 flex gap-2">
                          <button
                            type="button"
                            onClick={() => handleSelectService(service)}
                            className="rounded-xl border border-blue-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-700"
                          >
                            View
                          </button>
                          <button
                            type="button"
                            onClick={() => handleOpenServiceFlow(service)}
                            className="gov-btn-primary inline-flex items-center gap-1 rounded-xl px-3 py-1.5 text-xs"
                          >
                            <ArrowRight className="h-3.5 w-3.5" />
                            {ui.startService}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              )}

              {result.steps?.length === 0 && (
                <article className="gov-card rounded-2xl p-6 text-center">
                  <div className="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-700">
                    <Search className="h-4 w-4" />
                  </div>
                  <h4 className="text-lg font-semibold text-ink">{ui.noResultTitle}</h4>
                  <p className="mt-1 text-sm text-slate-600">{ui.noResultBody}</p>
                </article>
              )}
            </section>
          )}
        </main>
      </div>

      {toastMessage && (
        <div className="fixed bottom-5 right-5 z-50 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 shadow-lg">
          {toastMessage}
        </div>
      )}

      {serviceDetailsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-ink">{serviceDetailsModal.service_name}</h2>
              <button
                type="button"
                onClick={() => setServiceDetailsModal(null)}
                className="text-slate-500 transition hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            {/* Service Overview */}
            {serviceDetailsModal.service_overview && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.service_overview.title}</h3>
                <div className="space-y-2 rounded-xl bg-slate-50 p-4">
                  <p className="text-sm text-slate-700"><strong>Description:</strong> {serviceDetailsModal.service_overview.description}</p>
                  {serviceDetailsModal.service_overview.organization && (
                    <p className="text-sm text-slate-700"><strong>Organization:</strong> {serviceDetailsModal.service_overview.organization}</p>
                  )}
                  {serviceDetailsModal.service_overview.category && (
                    <p className="text-sm text-slate-700"><strong>Category:</strong> {serviceDetailsModal.service_overview.category}</p>
                  )}
                </div>
              </section>
            )}

            {/* Step-by-Step Process */}
            {serviceDetailsModal.steps && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.steps.title}</h3>
                <div className="space-y-2">
                  {serviceDetailsModal.steps.process?.map((step, idx) => (
                    <div key={idx} className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
                      <p className="font-semibold text-ink">{step.order}. {step.title}</p>
                      <p className="mt-1 text-sm text-slate-600">{step.description}</p>
                      <p className="mt-1 text-xs text-slate-500">{step.location} • {step.action}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Required Documents */}
            {serviceDetailsModal.documents && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.documents.title}</h3>
                <ul className="space-y-2">
                  {serviceDetailsModal.documents.list?.map((doc, idx) => (
                    <li key={idx} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm">
                      <span className="inline-block h-2 w-2 flex-shrink-0 rounded-full bg-blue-700 mt-1.5" />
                      <div>
                        <p className="font-medium text-ink">{doc.name}</p>
                        <p className="text-xs text-slate-500">{doc.type}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Time & Cost */}
            {serviceDetailsModal.time_and_cost && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.time_and_cost.title}</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-xl bg-slate-50 p-4">
                    <p className="text-xs text-slate-500">Processing Time</p>
                    <p className="mt-1 font-semibold text-ink">{serviceDetailsModal.time_and_cost.processing_time}</p>
                  </div>
                  <div className="rounded-xl bg-slate-50 p-4">
                    <p className="text-xs text-slate-500">Cost</p>
                    <p className="mt-1 font-semibold text-ink">{serviceDetailsModal.time_and_cost.cost?.description}</p>
                  </div>
                </div>
              </section>
            )}

            {/* Problems & Solutions */}
            {serviceDetailsModal.problems_and_solutions && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.problems_and_solutions.title}</h3>
                <div className="space-y-2">
                  {serviceDetailsModal.problems_and_solutions.items?.map((item, idx) => (
                    <details key={idx} className="rounded-xl border border-yellow-100 bg-yellow-50/50 p-4">
                      <summary className="cursor-pointer font-semibold text-ink hover:text-yellow-800">{item.problem}</summary>
                      <p className="mt-2 text-sm text-slate-700">✓ {item.solution}</p>
                    </details>
                  ))}
                </div>
              </section>
            )}

            {/* Recommendations */}
            {serviceDetailsModal.recommendations && (
              <section className="mb-6">
                <h3 className="mb-3 text-lg font-bold text-ink">{serviceDetailsModal.recommendations.title}</h3>
                {serviceDetailsModal.recommendations.related_services?.length > 0 && (
                  <div className="mb-4">
                    <p className="mb-2 text-sm font-medium text-slate-700">Related Services:</p>
                    <ul className="space-y-2">
                      {serviceDetailsModal.recommendations.related_services?.map((svc, idx) => (
                        <li key={idx} className="text-sm text-slate-600">• <strong>{svc.name}</strong> - {svc.reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {serviceDetailsModal.recommendations.tips?.length > 0 && (
                  <div>
                    <p className="mb-2 text-sm font-medium text-slate-700">Tips:</p>
                    <ul className="space-y-1">
                      {serviceDetailsModal.recommendations.tips?.map((tip, idx) => (
                        <li key={idx} className="text-sm text-slate-600">💡 {tip}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
            )}

            <button
              type="button"
              onClick={() => setServiceDetailsModal(null)}
              className="gov-btn-primary w-full rounded-xl px-4 py-2 text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {showExecutionFlow && currentExecution && (
        <ServiceExecutionFlow
          execution={currentExecution}
          language={uiLanguage}
          onClose={() => {
            setShowExecutionFlow(false);
            setCurrentExecution(null);
          }}
        />
      )}
    </div>
  );
}

function toSimpleText(text, enabled) {
  if (!enabled) {
    return text;
  }

  const sentence = String(text || "")
    .split(/[.!?]/)
    .find((part) => part.trim().length > 0);

  if (!sentence) {
    return text;
  }

  return `${sentence.trim()}.`;
}

export default App;
