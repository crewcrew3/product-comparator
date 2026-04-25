"""
Агент WishlistAgent (Управление вишлистом).
Форматирует информацию о товаре для добавления в список желаемого,
учитывает предпочтения пользователя и возвращает структурированную запись.
"""

import json
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from config.prompts import load_prompts
from tools.knowledge import load_product_specs, format_specs_for_prompt
from tools.wishlist import load_wishlist, check_wishlist_duplicate
from tools.preferences import load_user_preferences

OLLAMA_MODEL = "qwen2.5:3b"
# OLLAMA_BASE_URL = "http://host.docker.internal:11434"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_FORMAT = "json"


def create_wishlist_llm() -> ChatOllama:
    """Создает экземпляр LLM для WishlistAgent."""
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=OLLAMA_TEMPERATURE,
        format=OLLAMA_FORMAT,
        num_ctx=4096,
        keep_alive="0s"
    )


def run_wishlist(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Основная функция агента.
    Читает product_names из state, проверяет дубликат, загружает данные,
    вызывает LLM для форматирования записи и возвращает результат.
    """
    product_names = state.get("product_names", [])
    
    if len(product_names) != 1:
        return {
            "wishlist_entry": None,
            "wishlist_error": "invalid_input",
            "wishlist_error_message": "Агенту передано неверное количество товаров."
        }

    product_name = product_names[0]

    if check_wishlist_duplicate(product_name):
        return {
            "wishlist_entry": None,
            "wishlist_error": "already_in_wishlist",
            "wishlist_error_message": f"Товар '{product_name}' уже есть в вишлисте."
        }

    # Загрузка характеристик и предпочтений
    specs = load_product_specs(product_name)
    user_prefs = load_user_preferences()
    current_wishlist = load_wishlist()

    # Подготовка текста характеристик для промпта
    specs_text = format_specs_for_prompt(specs) if specs else "Характеристики не найдены в базе."

    # Загрузка системного промпта
    prompts = load_prompts()
    system_prompt = prompts.get("wishlist", {}).get("system", "")
    if not system_prompt:
        system_prompt = "Ты менеджер вишлиста. Верни строго JSON."
    
    # Экранирование фигурных скобок для LangChain
    system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")

    # Шаблон промпта с точными переменными из prompts.yaml
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Название товара: {product_name}\n\nХарактеристики из базы: {specs}\n\nТекущий вишлист: {current_wishlist}\n\nПредпочтения пользователя: {user_prefs}")
    ])

    # Выполнение запроса
    llm = create_wishlist_llm()
    chain = prompt | llm

    try:
        response = chain.invoke({
            "product_name": product_name,
            "specs": specs_text,
            "current_wishlist": json.dumps(current_wishlist, ensure_ascii=False, default=str),
            "user_prefs": json.dumps(user_prefs, ensure_ascii=False)
        })
        parsed = parse_json_response(response.content)
    except Exception as e:
        return {
            "wishlist_entry": None,
            "wishlist_error": "llm_failed",
            "wishlist_error_message": str(e)
        }

    # Если модель вернула ошибку в поле error
    if parsed.get("error"):
        return {
            "wishlist_entry": None,
            "wishlist_error": parsed["error"],
            "wishlist_error_message": parsed.get("error_message", "Ошибка генерации записи")
        }

    # Успешный результат
    return {
        "wishlist_entry": parsed.get("wishlist_entry"),
        "wishlist_error": None,
        "wishlist_error_message": None
    }


def parse_json_response(text: str) -> Dict[str, Any]:
    """Парсит ответ LLM, удаляет markdown-обёртки, возвращает словарь."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    default = {
        "wishlist_entry": None,
        "error": "parse_error",
        "error_message": "Не удалось распарсить ответ модели"
    }

    try:
        parsed = json.loads(cleaned)
        for key in default:
            if key not in parsed:
                parsed[key] = default[key]
        return parsed
    except json.JSONDecodeError:
        return default