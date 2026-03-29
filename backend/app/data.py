from __future__ import annotations

from collections import deque
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

SUPPORTED_LANGUAGES = {"uz", "ru", "en"}
REQUIRED_SCENARIO_IDS = {"birth", "house", "pension"}

BUTTONS: Dict[str, Dict[str, str]] = {
    "uz": {
        "analyze": "Xizmatlarni topish",
        "open_scenario": "Ssenariyni ochish",
        "back": "Orqaga",
    },
    "ru": {
        "analyze": "Подобрать услуги",
        "open_scenario": "Открыть сценарий",
        "back": "Назад",
    },
    "en": {
        "analyze": "Find services",
        "open_scenario": "Open scenario",
        "back": "Back",
    },
}

STEP_TITLES: Dict[str, Dict[str, Dict[int, str]]] = {
    "birth": {
        "uz": {
            1: "Tug'ilishni ro'yxatdan o'tkazish",
            2: "Oilaviy ro'yxatni yangilash",
            3: "Bolalar nafaqasiga ariza topshirish",
            4: "Oilaviy tibbiy xizmatlarni faollashtirish",
        },
        "ru": {
            1: "Регистрация рождения",
            2: "Обновление семейной регистрации",
            3: "Подача на детское пособие",
            4: "Подключение семейных медуслуг",
        },
        "en": {
            1: "Register Birth",
            2: "Update Household Record",
            3: "Apply for Child Support",
            4: "Activate Family Healthcare Services",
        },
    },
    "house": {
        "uz": {
            1: "Mulkning huquqiy holatini tekshirish",
            2: "Moliyalashtirishni tasdiqlash",
            3: "Sotuv shartnomasini imzolash",
            4: "Notarial tekshiruvdan o'tish",
            5: "Mulk huquqini o'tkazishni ro'yxatdan o'tkazish",
        },
        "ru": {
            1: "Проверка юридической чистоты объекта",
            2: "Получение финансирования",
            3: "Подписание договора купли-продажи",
            4: "Нотариальная проверка",
            5: "Регистрация перехода права собственности",
        },
        "en": {
            1: "Verify Property Legal Status",
            2: "Secure Financing",
            3: "Sign Sale Agreement",
            4: "Complete Notary Verification",
            5: "Register Ownership Transfer",
        },
    },
    "pension": {
        "uz": {
            1: "Nafaqa mezonlarini tekshirish",
            2: "Tasdiqlovchi hujjatlarni yig'ish",
            3: "Nafaqa arizasini topshirish",
            4: "Qaror va birinchi to'lovni kuzatish",
        },
        "ru": {
            1: "Проверка права на пенсию",
            2: "Сбор подтверждающих документов",
            3: "Подача заявления на пенсию",
            4: "Отслеживание решения и первой выплаты",
        },
        "en": {
            1: "Check Pension Eligibility",
            2: "Collect Supporting Records",
            3: "Submit Pension Application",
            4: "Track Decision and First Payment",
        },
    },
}

STEP_DESCRIPTIONS: Dict[str, Dict[str, Dict[int, str]]] = {
    "birth": {
        "uz": {
            1: "Yangi tug'ilgan farzandni FHDYOda ro'yxatdan o'tkazing va tug'ilganlik guvohnomasini oling.",
            2: "Farzandni manzil va oilaviy ro'yxatga kiriting.",
            3: "Bir martalik va oylik bolalar nafaqasi uchun ariza bering.",
            4: "Farzand profili bo'yicha poliklinika va oilaviy tibbiy xizmatlarni yoqing.",
        },
        "ru": {
            1: "Зарегистрируйте ребенка в ЗАГС и получите свидетельство о рождении.",
            2: "Добавьте ребенка в адресный и семейный учет.",
            3: "Подайте заявление на единовременные и ежемесячные детские выплаты.",
            4: "Подключите детские и семейные медицинские услуги.",
        },
        "en": {
            1: "Register the newborn at the civil registry and receive a birth certificate.",
            2: "Add the child to family and address records.",
            3: "Submit applications for one-time and monthly child benefits.",
            4: "Enable pediatric and family health services linked to the child profile.",
        },
    },
    "house": {
        "uz": {
            1: "Sotib olishdan oldin mulk huquqi va cheklovlarni tekshiring.",
            2: "Ipoteka yoki boshqa moliyalashtirish uchun tasdiq oling.",
            3: "Sotuvchi bilan qonuniy shartnomani imzolang.",
            4: "Bitim shartlarini notarius orqali tasdiqlang.",
            5: "Mulkni xaridor nomiga rasmiy ro'yxatdan o'tkazing.",
        },
        "ru": {
            1: "Проверьте право собственности и ограничения до покупки.",
            2: "Получите одобрение ипотеки или другого финансирования.",
            3: "Подпишите юридически корректный договор купли-продажи.",
            4: "Проведите нотариальную проверку условий сделки.",
            5: "Зарегистрируйте переход права собственности на покупателя.",
        },
        "en": {
            1: "Check ownership, cadastral records, and restrictions before purchase.",
            2: "Apply for mortgage or alternative financing and receive approval terms.",
            3: "Prepare and sign the legally compliant sale agreement.",
            4: "Validate transaction terms and identity through notary review.",
            5: "Finalize transaction and register ownership transfer.",
        },
    },
    "pension": {
        "uz": {
            1: "Yosh, ish staji va badal talablarini tekshiring.",
            2: "Ish staji va badal bo'yicha tasdiqlovchi ma'lumotlarni yig'ing.",
            3: "Nafaqa arizasini tegishli organ yoki DXMga topshiring.",
            4: "Ariza holatini kuzating va birinchi to'lov sanasini tekshiring.",
        },
        "ru": {
            1: "Проверьте возраст, стаж и требования по взносам.",
            2: "Соберите подтверждения стажа и пенсионных отчислений.",
            3: "Подайте заявление в пенсионный орган или центр госуслуг.",
            4: "Отслеживайте статус и дату первой выплаты.",
        },
        "en": {
            1: "Confirm age, work history, and contribution requirements.",
            2: "Gather contribution and employment confirmations.",
            3: "Apply at the pension authority or public service center.",
            4: "Monitor application status and first payment date.",
        },
    },
}

LOCALIZED_MESSAGES: Dict[str, Dict[str, str]] = {
    "uz": {
        "no_match": "Mos ssenariy topilmadi. Iltimos, holatingiz haqida ko'proq ma'lumot yozing.",
        "hint_1": "Hayotiy holat, oila holati yoki kerakli xizmat turini kiriting.",
        "hint_2": "Misol: 'bola tugildi', 'uy sotib olish', 'nafaqaga ariza'.",
    },
    "ru": {
        "no_match": "Подходящий сценарий не найден. Добавьте больше деталей о вашей ситуации.",
        "hint_1": "Укажите жизненную ситуацию, семейный статус или нужный тип услуги.",
        "hint_2": "Пример: 'рождение ребенка', 'покупка дома', 'оформление пенсии'.",
    },
    "en": {
        "no_match": "No matching scenario was found. Please add more details about your situation.",
        "hint_1": "Include life event, family status, or target service type.",
        "hint_2": "Example: 'child birth', 'buying a house', 'apply for pension'.",
    },
}

LOCALIZED_RECOMMENDATIONS: Dict[str, Dict[str, List[str]]] = {
    "birth": {
        "uz": [
            "Avval tug'ilishni ro'yxatdan o'tkazing, keyingi xizmatlar tezroq ochiladi.",
            "ID va tug'ilish hujjatlarining elektron nusxalarini oldindan tayyorlang.",
        ],
        "ru": [
            "Сначала зарегистрируйте рождение, чтобы открыть доступ к следующим услугам.",
            "Заранее подготовьте сканы паспортов и документов о рождении.",
        ],
        "en": [
            "Start with birth registration to unlock next services.",
            "Prepare scanned copies of IDs and birth documents in advance.",
        ],
    },
    "house": {
        "uz": [
            "Oldindan huquqiy tekshiruv o'tkazib, keyin to'lov qiling.",
            "Faqat foizga emas, kreditning umumiy qiymatiga qarang.",
        ],
        "ru": [
            "Сделайте юридическую проверку до внесения предоплаты.",
            "Сравнивайте не только ставку, но и полную стоимость кредита.",
        ],
        "en": [
            "Run legal due diligence before any deposit payment.",
            "Compare total mortgage cost, not just interest rate.",
        ],
    },
    "pension": {
        "uz": [
            "Kechikmaslik uchun badal tarixi ma'lumotlarini oldindan tekshiring.",
            "To'lov uchun o'zingiz nomidagi bank hisobidan foydalaning.",
        ],
        "ru": [
            "Проверьте историю взносов заранее, чтобы избежать задержек.",
            "Используйте личный банковский счет, оформленный на ваше имя.",
        ],
        "en": [
            "Verify contribution history early to avoid delays.",
            "Use a personal bank account registered in your name.",
        ],
    },
}


@dataclass(frozen=True)
class LocalizedText:
    en: str
    ru: str
    uz: str

    def in_lang(self, language: str) -> str:
        return getattr(self, language, self.en)


@dataclass(frozen=True)
class LocalizedDiff:
    service_a: LocalizedText
    service_b: LocalizedText
    difference: LocalizedText
    when_to_choose_a: LocalizedText
    when_to_choose_b: LocalizedText


SCENARIOS: Dict[str, dict] = {
    "newborn": {
        "keywords": [
            "newborn",
            "baby",
            "birth",
            "child benefit",
            "maternity",
            "new child",
            "родился",
            "новорожден",
            "пособие",
            "декрет",
            "tugildi",
            "chaqaloq",
            "nafaqa",
            "tug'ilgan",
        ],
        "title": LocalizedText(
            en="New child in family",
            ru="Рождение ребенка",
            uz="Oilada yangi farzand",
        ),
        "summary": LocalizedText(
            en="Register birth, update family records, and request child-related benefits.",
            ru="Оформите рождение, обновите семейные записи и подайте на детские выплаты.",
            uz="Tug'ilishni ro'yxatdan o'tkazing, oilaviy ma'lumotlarni yangilang va bolaga oid nafaqalarga murojaat qiling.",
        ),
        "service_chain": [
            {
                "service": LocalizedText(
                    en="Birth Registration",
                    ru="Регистрация рождения",
                    uz="Tug'ilishni ro'yxatdan o'tkazish",
                ),
                "purpose": LocalizedText(
                    en="Get official birth certificate and personal ID number for the child.",
                    ru="Получить свидетельство о рождении и персональный ID ребенка.",
                    uz="Farzand uchun tug'ilganlik guvohnomasi va shaxsiy ID olish.",
                ),
                "provider": LocalizedText(
                    en="Civil Registry Office",
                    ru="Орган ЗАГС",
                    uz="FHDYO bo'limi",
                ),
            },
            {
                "service": LocalizedText(
                    en="Address and Family Record Update",
                    ru="Обновление адресной и семейной регистрации",
                    uz="Manzil va oilaviy ro'yxatni yangilash",
                ),
                "purpose": LocalizedText(
                    en="Add child to household and residence records.",
                    ru="Добавить ребенка в домохозяйство и адресный учет.",
                    uz="Farzandni oila va yashash joyi ro'yxatiga kiritish.",
                ),
                "provider": LocalizedText(
                    en="Local Public Service Center",
                    ru="Центр госуслуг",
                    uz="Davlat xizmatlari markazi",
                ),
            },
            {
                "service": LocalizedText(
                    en="Child Benefit Application",
                    ru="Заявка на детское пособие",
                    uz="Bolalar nafaqasiga ariza",
                ),
                "purpose": LocalizedText(
                    en="Apply for one-time and monthly support programs.",
                    ru="Оформить единовременные и ежемесячные выплаты.",
                    uz="Bir martalik va oylik yordam dasturlariga murojaat qilish.",
                ),
                "provider": LocalizedText(
                    en="Social Protection Agency",
                    ru="Агентство социальной защиты",
                    uz="Ijtimoiy himoya agentligi",
                ),
            },
        ],
        "required_documents": {
            "en": [
                "Parent IDs",
                "Hospital birth confirmation",
                "Marriage certificate (if applicable)",
                "Bank account details",
            ],
            "ru": [
                "Паспорта родителей",
                "Справка о рождении из роддома",
                "Свидетельство о браке (если есть)",
                "Банковские реквизиты",
            ],
            "uz": [
                "Ota-onaning shaxsiy hujjatlari",
                "Tug'ruqxonadan tug'ilganlik ma'lumotnomasi",
                "Nikoh guvohnomasi (mavjud bo'lsa)",
                "Bank hisob raqami ma'lumotlari",
            ],
        },
        "similar_services": [
            LocalizedDiff(
                service_a=LocalizedText(
                    en="Child Benefit",
                    ru="Детское пособие",
                    uz="Bolalar nafaqasi",
                ),
                service_b=LocalizedText(
                    en="Maternity Payment",
                    ru="Пособие по беременности и родам",
                    uz="Homiladorlik va tug'ruq to'lovi",
                ),
                difference=LocalizedText(
                    en="Child benefit supports raising the child; maternity payment compensates parent income around childbirth.",
                    ru="Детское пособие поддерживает уход за ребенком, а пособие по беременности и родам компенсирует доход родителя в период родов.",
                    uz="Bolalar nafaqasi bolani parvarishlash uchun, homiladorlik va tug'ruq to'lovi esa tug'ruq davrida ota-ona daromadini qoplash uchun beriladi.",
                ),
                when_to_choose_a=LocalizedText(
                    en="Choose when the child is already registered and you need ongoing support.",
                    ru="Выбирайте после регистрации ребенка для дальнейшей поддержки.",
                    uz="Farzand ro'yxatdan o'tganidan keyin doimiy yordam kerak bo'lsa tanlang.",
                ),
                when_to_choose_b=LocalizedText(
                    en="Choose during late pregnancy or immediately after delivery.",
                    ru="Выбирайте на позднем сроке беременности или сразу после родов.",
                    uz="Homiladorlikning oxirgi bosqichida yoki tug'ruqdan keyin darhol tanlang.",
                ),
            )
        ],
    },
    "new-business": {
        "keywords": [
            "start business",
            "company",
            "entrepreneur",
            "register llc",
            "tax id",
            "new business",
            "бизнес",
            "ип",
            "ооо",
            "предприниматель",
            "biznes",
            "mchj",
            "yakka tartibdagi tadbirkor",
            "soliq",
        ],
        "title": LocalizedText(
            en="Starting a business",
            ru="Открытие бизнеса",
            uz="Biznes boshlash",
        ),
        "summary": LocalizedText(
            en="Register legal entity, obtain tax registration, and set up mandatory compliance.",
            ru="Зарегистрируйте юрлицо, получите налоговый учет и выполните обязательные требования.",
            uz="Yuridik shaxsni ro'yxatdan o'tkazing, soliq hisobiga turing va majburiy talablarni bajaring.",
        ),
        "service_chain": [
            {
                "service": LocalizedText(
                    en="Business Entity Registration",
                    ru="Регистрация предпринимателя/компании",
                    uz="Tadbirkorlik subyektini ro'yxatdan o'tkazish",
                ),
                "purpose": LocalizedText(
                    en="Create legal status for your business activity.",
                    ru="Оформить юридический статус для предпринимательской деятельности.",
                    uz="Biznes faoliyati uchun huquqiy maqomni rasmiylashtirish.",
                ),
                "provider": LocalizedText(
                    en="Public Service Center",
                    ru="Центр госуслуг",
                    uz="Davlat xizmatlari markazi",
                ),
            },
            {
                "service": LocalizedText(
                    en="Tax Registration",
                    ru="Постановка на налоговый учет",
                    uz="Soliq hisobiga qo'yish",
                ),
                "purpose": LocalizedText(
                    en="Obtain taxpayer status and applicable taxation regime.",
                    ru="Получить статус налогоплательщика и выбрать режим налогообложения.",
                    uz="Soliq to'lovchi maqomini olish va soliq rejimini tanlash.",
                ),
                "provider": LocalizedText(
                    en="Tax Authority",
                    ru="Налоговый орган",
                    uz="Soliq qo'mitasi",
                ),
            },
            {
                "service": LocalizedText(
                    en="Mandatory Licenses/Permits",
                    ru="Обязательные лицензии и разрешения",
                    uz="Majburiy litsenziya va ruxsatnomalar",
                ),
                "purpose": LocalizedText(
                    en="Secure sector-specific approvals before operations begin.",
                    ru="Получить отраслевые разрешения до начала деятельности.",
                    uz="Faoliyatni boshlashdan oldin soha bo'yicha ruxsatlarni olish.",
                ),
                "provider": LocalizedText(
                    en="Sector Regulators",
                    ru="Профильные регуляторы",
                    uz="Tegishli nazorat organlari",
                ),
            },
        ],
        "required_documents": {
            "en": [
                "Founder ID",
                "Legal address details",
                "Company charter/draft statute",
                "Taxpayer registration application",
            ],
            "ru": [
                "Паспорт учредителя",
                "Юридический адрес",
                "Устав компании (проект)",
                "Заявление на налоговый учет",
            ],
            "uz": [
                "Ta'sischining shaxsiy hujjati",
                "Yuridik manzil ma'lumotlari",
                "Korxona ustavi (loyiha)",
                "Soliq hisobiga qo'yish arizasi",
            ],
        },
        "similar_services": [
            LocalizedDiff(
                service_a=LocalizedText(
                    en="Individual Entrepreneur Registration",
                    ru="Регистрация ИП",
                    uz="YTT ro'yxatdan o'tkazish",
                ),
                service_b=LocalizedText(
                    en="LLC Registration",
                    ru="Регистрация ООО",
                    uz="MChJ ro'yxatdan o'tkazish",
                ),
                difference=LocalizedText(
                    en="Individual entrepreneur is simpler and tied to the person; LLC separates personal and business liability.",
                    ru="ИП проще в администрировании, но привязан к физлицу; ООО отделяет личную и бизнес-ответственность.",
                    uz="YTT yuritish osonroq, ammo jismoniy shaxsga bog'liq; MChJ shaxsiy va biznes javobgarligini ajratadi.",
                ),
                when_to_choose_a=LocalizedText(
                    en="Choose for solo low-risk services with minimal overhead.",
                    ru="Выбирайте для небольшого сольного бизнеса с низкими рисками.",
                    uz="Kichik, yakka va past xavfli faoliyat uchun tanlang.",
                ),
                when_to_choose_b=LocalizedText(
                    en="Choose when you have partners, hiring plans, or higher liability risks.",
                    ru="Выбирайте при наличии партнеров, планах найма или повышенных рисках.",
                    uz="Hamkorlar, xodim yollash rejasi yoki yuqori javobgarlik xavfi bo'lsa tanlang.",
                ),
            )
        ],
    },
    "home-purchase": {
        "keywords": [
            "buy home",
            "mortgage",
            "apartment",
            "house",
            "property",
            "real estate",
            "квартира",
            "ипотека",
            "дом",
            "покупка жилья",
            "uy",
            "ipoteka",
            "ko'chmas mulk",
        ],
        "title": LocalizedText(
            en="Buying a home",
            ru="Покупка жилья",
            uz="Uy-joy sotib olish",
        ),
        "summary": LocalizedText(
            en="Verify property status, secure financing, and register ownership transfer.",
            ru="Проверьте объект, оформите финансирование и зарегистрируйте переход права собственности.",
            uz="Ko'chmas mulk holatini tekshiring, moliyalashtirishni rasmiylashtiring va mulk huquqini o'tkazing.",
        ),
        "service_chain": [
            {
                "service": LocalizedText(
                    en="Property Due Diligence",
                    ru="Проверка юридической чистоты объекта",
                    uz="Mulkning huquqiy holatini tekshirish",
                ),
                "purpose": LocalizedText(
                    en="Confirm ownership, encumbrances, and cadastral data.",
                    ru="Проверить право собственности, обременения и кадастровые данные.",
                    uz="Mulk huquqi, cheklovlar va kadastr ma'lumotlarini tasdiqlash.",
                ),
                "provider": LocalizedText(
                    en="Cadastre and Property Registry",
                    ru="Кадастр и реестр недвижимости",
                    uz="Kadastr va ko'chmas mulk reyestri",
                ),
            },
            {
                "service": LocalizedText(
                    en="Mortgage or Financing Approval",
                    ru="Одобрение ипотеки/финансирования",
                    uz="Ipoteka yoki moliyalashtirishni tasdiqlash",
                ),
                "purpose": LocalizedText(
                    en="Obtain financing terms and pre-approval.",
                    ru="Получить условия финансирования и предварительное одобрение.",
                    uz="Moliyalashtirish shartlari va dastlabki tasdiqni olish.",
                ),
                "provider": LocalizedText(
                    en="Partner Bank",
                    ru="Банк-партнер",
                    uz="Hamkor bank",
                ),
            },
            {
                "service": LocalizedText(
                    en="Ownership Transfer Registration",
                    ru="Регистрация перехода права собственности",
                    uz="Mulk huquqini o'tkazishni ro'yxatdan o'tkazish",
                ),
                "purpose": LocalizedText(
                    en="Finalize legal ownership under buyer name.",
                    ru="Окончательно зарегистрировать право собственности на покупателя.",
                    uz="Xaridor nomiga mulk huquqini yakuniy rasmiylashtirish.",
                ),
                "provider": LocalizedText(
                    en="Public Service Center + Notary",
                    ru="Центр госуслуг + нотариус",
                    uz="Davlat xizmatlari markazi + notarius",
                ),
            },
        ],
        "required_documents": {
            "en": [
                "Buyer and seller IDs",
                "Property ownership certificate",
                "Cadastral extract",
                "Bank pre-approval letter (if mortgage)",
            ],
            "ru": [
                "Паспорта покупателя и продавца",
                "Свидетельство/выписка о праве собственности",
                "Кадастровая выписка",
                "Предодобрение банка (если ипотека)",
            ],
            "uz": [
                "Xaridor va sotuvchi shaxsiy hujjatlari",
                "Mulk huquqi guvohnomasi",
                "Kadastrdan ko'chirma",
                "Bankdan dastlabki tasdiq xati (ipoteka bo'lsa)",
            ],
        },
        "similar_services": [
            LocalizedDiff(
                service_a=LocalizedText(
                    en="Subsidized Mortgage",
                    ru="Льготная ипотека",
                    uz="Imtiyozli ipoteka",
                ),
                service_b=LocalizedText(
                    en="Standard Mortgage",
                    ru="Стандартная ипотека",
                    uz="Standart ipoteka",
                ),
                difference=LocalizedText(
                    en="Subsidized mortgage has preferential rates for eligible groups; standard mortgage has broader eligibility but market rates.",
                    ru="Льготная ипотека предлагает сниженные ставки для целевых групп; стандартная доступнее по условиям входа, но по рыночной ставке.",
                    uz="Imtiyozli ipoteka ayrim toifalar uchun past foiz beradi; standart ipoteka ko'proq odamlarga ochiq, lekin bozor stavkasida.",
                ),
                when_to_choose_a=LocalizedText(
                    en="Choose if you meet age/income/family eligibility criteria.",
                    ru="Выбирайте, если соответствуете требованиям по возрасту/доходу/составу семьи.",
                    uz="Yosh/daromad/oila mezonlariga mos kelsangiz tanlang.",
                ),
                when_to_choose_b=LocalizedText(
                    en="Choose if you need faster approval without program restrictions.",
                    ru="Выбирайте, если нужно быстрое одобрение без ограничений программы.",
                    uz="Dastur cheklovlarisiz tezroq tasdiq kerak bo'lsa tanlang.",
                ),
            )
        ],
    },
}


def detect_scenarios(user_text: str) -> List[dict]:
    lowered = user_text.lower()
    hits: List[dict] = []

    for scenario_id, scenario in SCENARIOS.items():
        matched_keywords = [kw for kw in scenario["keywords"] if kw in lowered]
        if not matched_keywords:
            continue

        ratio = len(matched_keywords) / max(len(scenario["keywords"]), 1)
        confidence = min(95, max(35, int(ratio * 100) + 30))
        hits.append(
            {
                "id": scenario_id,
                "confidence": confidence,
                "matched_keywords": matched_keywords[:3],
            }
        )

    return sorted(hits, key=lambda item: item["confidence"], reverse=True)


def to_localized_scenario_hint(scenario_id: str, confidence: int, language: str, matched_keywords: List[str]) -> dict:
    scenario = SCENARIOS[scenario_id]
    if language == "ru":
        why = f"Совпали ключевые слова: {', '.join(matched_keywords)}"
    elif language == "uz":
        why = f"Mos kelgan kalit so'zlar: {', '.join(matched_keywords)}"
    else:
        why = f"Matched keywords: {', '.join(matched_keywords)}"

    return {
        "id": scenario_id,
        "title": scenario["title"].in_lang(language),
        "confidence": confidence,
        "why": why,
    }


def to_localized_scenario_detail(scenario_id: str, language: str) -> dict:
    scenario = SCENARIOS[scenario_id]

    service_chain = []
    for idx, step in enumerate(scenario["service_chain"], start=1):
        service_chain.append(
            {
                "order": idx,
                "service": step["service"].in_lang(language),
                "purpose": step["purpose"].in_lang(language),
                "provider": step["provider"].in_lang(language),
            }
        )

    similar_services = []
    for diff in scenario["similar_services"]:
        similar_services.append(
            {
                "service_a": diff.service_a.in_lang(language),
                "service_b": diff.service_b.in_lang(language),
                "difference": diff.difference.in_lang(language),
                "when_to_choose_a": diff.when_to_choose_a.in_lang(language),
                "when_to_choose_b": diff.when_to_choose_b.in_lang(language),
            }
        )

    documents_by_language = scenario["required_documents"]
    required_documents = documents_by_language.get(language, documents_by_language["en"])

    return {
        "id": scenario_id,
        "title": scenario["title"].in_lang(language),
        "summary": scenario["summary"].in_lang(language),
        "service_chain": service_chain,
        "required_documents": required_documents,
        "similar_services": similar_services,
    }


WORKFLOW_SCENARIOS: Dict[str, dict] = {
    "birth": {
        "keywords": ["bola", "tugildi", "birth", "child", "родился", "рождение", "ребенок"],
        "steps": [
            {
                "id": 1,
                "title": "Register Birth",
                "description": "Register the newborn at the civil registry and receive a birth certificate.",
                "required_documents": ["Parent IDs", "Hospital birth notice"],
                "estimated_time": "1-2 days",
                "next_steps": [2, 3],
            },
            {
                "id": 2,
                "title": "Update Household Record",
                "description": "Add the child to family and address records.",
                "required_documents": ["Birth certificate", "Address registration form"],
                "estimated_time": "1 day",
                "next_steps": [4],
            },
            {
                "id": 3,
                "title": "Apply for Child Support",
                "description": "Submit applications for one-time and monthly child benefits.",
                "required_documents": ["Parent IDs", "Birth certificate", "Bank account details"],
                "estimated_time": "3-7 days",
                "next_steps": [4],
            },
            {
                "id": 4,
                "title": "Activate Family Healthcare Services",
                "description": "Enable pediatric and family health services linked to the child profile.",
                "required_documents": ["Birth certificate", "Household registration update"],
                "estimated_time": "1-3 days",
                "next_steps": [],
            },
        ],
        "differences": [
            {
                "service1": "Child Benefit",
                "service2": "Maternity Benefit",
                "explanation": "Child Benefit supports child care costs, while Maternity Benefit is for pregnancy and childbirth period income support.",
            }
        ],
        "recommendations": [
            "Start with birth registration first to unlock all next services.",
            "Prepare scanned copies of IDs and birth documents to speed up processing.",
        ],
    },
    "house": {
        "keywords": ["uy", "home", "house", "дом", "квартира", "жилье"],
        "steps": [
            {
                "id": 1,
                "title": "Verify Property Legal Status",
                "description": "Check ownership, cadastral records, and any restrictions before purchase.",
                "required_documents": ["Property identifier", "Seller ownership extract"],
                "estimated_time": "1-3 days",
                "next_steps": [2],
            },
            {
                "id": 2,
                "title": "Secure Financing",
                "description": "Apply for mortgage or alternative financing and receive approval terms.",
                "required_documents": ["Buyer ID", "Income statement", "Bank application"],
                "estimated_time": "3-10 days",
                "next_steps": [3, 4],
            },
            {
                "id": 3,
                "title": "Sign Sale Agreement",
                "description": "Prepare and sign the legally compliant sale agreement.",
                "required_documents": ["Draft sale agreement", "Buyer and seller IDs"],
                "estimated_time": "1 day",
                "next_steps": [5],
            },
            {
                "id": 4,
                "title": "Complete Notary Verification",
                "description": "Validate transaction terms and identity through notary review.",
                "required_documents": ["Signed agreement", "Cadastre extract"],
                "estimated_time": "1 day",
                "next_steps": [5],
            },
            {
                "id": 5,
                "title": "Register Ownership Transfer",
                "description": "Finalize transaction through notary and register ownership transfer.",
                "required_documents": ["Sale agreement", "Buyer and seller IDs", "Cadastre extract"],
                "estimated_time": "1-2 days",
                "next_steps": [],
            },
        ],
        "differences": [
            {
                "service1": "Subsidized Mortgage",
                "service2": "Standard Mortgage",
                "explanation": "Subsidized Mortgage offers better rates for eligible groups, while Standard Mortgage has broader eligibility but market rates.",
            }
        ],
        "recommendations": [
            "Run legal due diligence before paying any deposit.",
            "Compare total mortgage cost, not just the interest rate.",
        ],
    },
    "pension": {
        "keywords": ["nafaqa", "pension", "пенсия", "nafaqaga"],
        "steps": [
            {
                "id": 1,
                "title": "Check Pension Eligibility",
                "description": "Confirm age, work history, and contribution requirements.",
                "required_documents": ["ID", "Employment record"],
                "estimated_time": "1-2 days",
                "next_steps": [2, 3],
            },
            {
                "id": 2,
                "title": "Collect Supporting Records",
                "description": "Gather contribution and employment confirmations from relevant authorities.",
                "required_documents": ["Employment record", "Contribution statement"],
                "estimated_time": "2-5 days",
                "next_steps": [4],
            },
            {
                "id": 3,
                "title": "Submit Pension Application",
                "description": "Apply at the pension authority or public service center.",
                "required_documents": ["Eligibility statement", "Bank account details"],
                "estimated_time": "1 day",
                "next_steps": [4],
            },
            {
                "id": 4,
                "title": "Track Decision and First Payment",
                "description": "Monitor application status and confirm first pension payment date.",
                "required_documents": ["Application receipt"],
                "estimated_time": "5-15 days",
                "next_steps": [],
            },
        ],
        "differences": [
            {
                "service1": "Age Pension",
                "service2": "Disability Pension",
                "explanation": "Age Pension is based on retirement age and contributions, while Disability Pension depends on certified disability criteria.",
            }
        ],
        "recommendations": [
            "Verify contribution history early to avoid processing delays.",
            "Use a personal bank account registered in your name for direct payments.",
        ],
    },
}


def normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    no_punctuation = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    collapsed = re.sub(r"\s+", " ", no_punctuation)
    return collapsed.strip()


def detect_language(query: str) -> str:
    normalized = normalize_text(query)
    if not normalized:
        return "uz"

    if re.search(r"[а-яё]", normalized, flags=re.IGNORECASE):
        return "ru"

    uzbek_markers = {"o'", "g'", "nafaqa", "bola", "tugildi", "uy", "yordam", "farzand"}
    if any(marker in normalized for marker in uzbek_markers):
        return "uz"

    english_keywords = {"birth", "child", "house", "home", "pension", "driver", "license"}
    tokens = set(normalized.split())
    if any(token in english_keywords for token in tokens):
        return "en"

    return "uz"


def get_service_differences(language: str) -> List[dict]:
    differences = {
        "uz": [
            {
                "service1": "Tug'ilganlik guvohnomasi",
                "service2": "Tug'ilish qaydidan ko'chirma",
                "explanation": (
                    "Tug'ilganlik guvohnomasi asosiy huquqiy hujjat hisoblanadi. "
                    "Qayd ko'chirmasi ko'proq ma'lumotnoma bo'lib, har doim guvohnoma o'rnini bosa olmaydi."
                ),
            },
            {
                "service1": "Haydovchilik guvohnomasi",
                "service2": "Traktor haydovchisi guvohnomasi",
                "explanation": (
                    "Oddiy haydovchilik guvohnomasi avtomobil va mototsikl kabi yo'l transportlari uchun. "
                    "Traktor guvohnomasi esa qishloq xo'jaligi texnikasi va maxsus texnika uchun kerak bo'ladi."
                ),
            },
        ],
        "ru": [
            {
                "service1": "Свидетельство о рождении",
                "service2": "Выписка из записи о рождении",
                "explanation": (
                    "Свидетельство о рождении - основной юридический документ. "
                    "Выписка обычно носит справочный характер и не всегда заменяет свидетельство."
                ),
            },
            {
                "service1": "Водительское удостоверение",
                "service2": "Удостоверение тракториста-машиниста",
                "explanation": (
                    "Обычное водительское удостоверение подходит для авто и мотоциклов на дорогах общего пользования. "
                    "Удостоверение тракториста нужно для управления трактором и спецтехникой."
                ),
            },
        ],
        "en": [
            {
                "service1": "Birth certificate",
                "service2": "Birth record extract",
                "explanation": (
                    "Birth certificate is the main legal document used for official procedures. "
                    "Birth record extract is usually informational and may not always replace the certificate."
                ),
            },
            {
                "service1": "Driver license",
                "service2": "Tractor driver license",
                "explanation": (
                    "Driver license is for regular road vehicles like cars and motorcycles. "
                    "Tractor driver license is for tractors and other special machinery."
                ),
            },
        ],
    }
    return differences.get(language, differences["uz"])


def detect_primary_scenario(query: str) -> Optional[str]:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return None

    tokens = set(normalized_query.split())
    best_scenario: Optional[str] = None
    best_score = 0

    for scenario_id, payload in WORKFLOW_SCENARIOS.items():
        scenario_score = 0
        for keyword in payload["keywords"]:
            normalized_keyword = normalize_text(keyword)
            if " " in normalized_keyword:
                if normalized_keyword in normalized_query:
                    scenario_score += 2
                continue

            if normalized_keyword in tokens or normalized_keyword in normalized_query:
                scenario_score += 2
            elif any(token.startswith(normalized_keyword) for token in tokens):
                scenario_score += 1
            else:
                keyword_root = normalized_keyword[:4]
                if len(keyword_root) >= 3 and any(
                    token.startswith(keyword_root) or keyword_root.startswith(token[:4]) for token in tokens if token
                ):
                    scenario_score += 1

        if scenario_score > best_score:
            best_score = scenario_score
            best_scenario = scenario_id

    return best_scenario if best_score > 0 else None


def _localize_steps(scenario_id: str, steps: List[dict], language: str) -> List[dict]:
    localized = []
    title_dict = STEP_TITLES.get(scenario_id, {}).get(language, {})
    description_dict = STEP_DESCRIPTIONS.get(scenario_id, {}).get(language, {})

    for step in steps:
        localized.append(
            {
                "id": step["id"],
                "title": title_dict.get(step["id"], step["title"]),
                "description": description_dict.get(step["id"], step["description"]),
                "required_documents": step["required_documents"],
                "estimated_time": step["estimated_time"],
                "next_steps": step["next_steps"],
            }
        )

    return localized


def _localize_differences(scenario_id: str, payload: dict, language: str) -> List[dict]:
    localized_scenario_differences = {
        "uz": {
            "birth": {
                "service1": "Bolalar nafaqasi",
                "service2": "Homiladorlik va tug'ruq nafaqasi",
                "explanation": "Bolalar nafaqasi bola parvarishi uchun, homiladorlik va tug'ruq nafaqasi esa tug'ruq davridagi daromadni qo'llab-quvvatlash uchun beriladi.",
            },
            "house": {
                "service1": "Imtiyozli ipoteka",
                "service2": "Standart ipoteka",
                "explanation": "Imtiyozli ipotekada foiz pastroq bo'ladi, lekin alohida mezonlar mavjud. Standart ipoteka ko'proq odamlarga ochiq, ammo stavka odatda yuqoriroq.",
            },
            "pension": {
                "service1": "Yoshga doir nafaqa",
                "service2": "Nogironlik nafaqasi",
                "explanation": "Yoshga doir nafaqa yosh va mehnat stajiga bog'liq, nogironlik nafaqasi esa tibbiy tasdiqlangan nogironlik mezonlari asosida beriladi.",
            },
        },
        "ru": {
            "birth": {
                "service1": "Детское пособие",
                "service2": "Пособие по беременности и родам",
                "explanation": "Детское пособие выплачивается на уход за ребенком, а пособие по беременности и родам поддерживает доход в период беременности и родов.",
            },
            "house": {
                "service1": "Льготная ипотека",
                "service2": "Стандартная ипотека",
                "explanation": "Льготная ипотека дает пониженную ставку, но доступна не всем. Стандартная ипотека доступнее по условиям, но обычно с рыночной ставкой.",
            },
            "pension": {
                "service1": "Пенсия по возрасту",
                "service2": "Пенсия по инвалидности",
                "explanation": "Пенсия по возрасту зависит от возраста и стажа, а пенсия по инвалидности назначается при подтвержденной инвалидности.",
            },
        },
        "en": {
            "birth": payload["differences"][0],
            "house": payload["differences"][0],
            "pension": payload["differences"][0],
        },
    }

    scenario_difference = (
        localized_scenario_differences.get(language, {}).get(scenario_id, payload["differences"][0])
        if payload.get("differences")
        else None
    )
    common_differences = get_service_differences(language)
    if scenario_difference is None:
        return common_differences

    return [scenario_difference, *common_differences]


def _validate_workflow_scenario(scenario_id: str, payload: dict) -> None:
    required_payload_keys = {"keywords", "steps", "differences", "recommendations"}
    missing_payload_keys = required_payload_keys.difference(payload.keys())
    if missing_payload_keys:
        missing = ", ".join(sorted(missing_payload_keys))
        raise ValueError(f"Scenario '{scenario_id}' is missing required keys: {missing}")

    steps = payload["steps"]
    if not 3 <= len(steps) <= 5:
        raise ValueError(f"Scenario '{scenario_id}' must have between 3 and 5 steps")

    if not payload["differences"]:
        raise ValueError(f"Scenario '{scenario_id}' must include at least one service difference")

    if not payload["recommendations"]:
        raise ValueError(f"Scenario '{scenario_id}' must include at least one recommendation")

    step_ids = {step["id"] for step in steps}
    if len(step_ids) != len(steps):
        raise ValueError(f"Scenario '{scenario_id}' has duplicate step IDs")

    indegree = {step_id: 0 for step_id in step_ids}
    for step in steps:
        required_step_keys = {
            "id",
            "title",
            "description",
            "required_documents",
            "estimated_time",
            "next_steps",
        }
        missing_step_keys = required_step_keys.difference(step.keys())
        if missing_step_keys:
            missing = ", ".join(sorted(missing_step_keys))
            raise ValueError(f"Scenario '{scenario_id}' step {step.get('id', '?')} is missing keys: {missing}")

        required_documents = step.get("required_documents", [])
        if not isinstance(required_documents, list) or len(required_documents) == 0:
            raise ValueError(
                f"Scenario '{scenario_id}' step {step['id']} must include at least one required document"
            )

        next_steps = step.get("next_steps", [])
        if not isinstance(next_steps, list):
            raise ValueError(f"Scenario '{scenario_id}' step {step['id']} has invalid next_steps")
        for target in next_steps:
            if target not in step_ids:
                raise ValueError(
                    f"Scenario '{scenario_id}' step {step['id']} references unknown next step {target}"
                )
            indegree[target] += 1

    queue = deque(sorted([step_id for step_id, degree in indegree.items() if degree == 0]))
    visited_count = 0
    by_id = {step["id"]: step for step in steps}

    while queue:
        current = queue.popleft()
        visited_count += 1
        for nxt in by_id[current].get("next_steps", []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if visited_count != len(steps):
        raise ValueError(f"Scenario '{scenario_id}' has cyclic workflow dependencies")


def _ordered_workflow_steps(payload: dict) -> List[dict]:
    steps = payload["steps"]
    by_id = {step["id"]: step for step in steps}
    indegree = {step["id"]: 0 for step in steps}

    for step in steps:
        for nxt in step.get("next_steps", []):
            indegree[nxt] += 1

    queue = deque(sorted([step_id for step_id, degree in indegree.items() if degree == 0]))
    ordered_ids: List[int] = []

    while queue:
        current = queue.popleft()
        ordered_ids.append(current)
        for nxt in by_id[current].get("next_steps", []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    return [by_id[step_id] for step_id in ordered_ids]


def validate_workflow_scenarios() -> None:
    missing_required_ids = REQUIRED_SCENARIO_IDS.difference(WORKFLOW_SCENARIOS.keys())
    if missing_required_ids:
        missing = ", ".join(sorted(missing_required_ids))
        raise ValueError(f"Missing required workflow scenarios: {missing}")

    for scenario_id, payload in WORKFLOW_SCENARIOS.items():
        _validate_workflow_scenario(scenario_id, payload)


def build_analyze_response(scenario_id: Optional[str], language: str) -> dict:
    normalized_language = language if language in SUPPORTED_LANGUAGES else "uz"

    if scenario_id is None:
        messages = LOCALIZED_MESSAGES[normalized_language]
        return {
            "language": normalized_language,
            "scenario": "unknown",
            "steps": [],
            "differences": [],
            "recommendations": [messages["hint_1"], messages["hint_2"]],
            "buttons": BUTTONS[normalized_language],
            "message": messages["no_match"],
        }

    payload = WORKFLOW_SCENARIOS[scenario_id]
    ordered_steps = _ordered_workflow_steps(payload)
    steps = _localize_steps(scenario_id, ordered_steps, normalized_language)
    differences = _localize_differences(scenario_id, payload, normalized_language)
    recommendations = LOCALIZED_RECOMMENDATIONS.get(scenario_id, {}).get(
        normalized_language, payload["recommendations"]
    )

    return {
        "language": normalized_language,
        "scenario": scenario_id,
        "steps": steps,
        "differences": differences,
        "recommendations": recommendations,
        "buttons": BUTTONS[normalized_language],
        "message": "",
    }


validate_workflow_scenarios()
