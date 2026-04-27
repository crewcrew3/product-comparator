"""
Агент Comparator (Сравниватель товаров).
Загружает характеристики двух товаров, учитывает предпочтения пользователя,
вызывает LLM для генерации сравнительной таблицы и рекомендации.
"""

import json
import logging
from typing import Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from config.prompts import load_prompts
from tools.knowledge import load_product_specs, format_specs_for_prompt
from tools.preferences import load_user_preferences
from tools.base import load_semantic_context

OLLAMA_MODEL = "gemma4:e2b"
# OLLAMA_BASE_URL = "http://host.docker.internal:11434"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_FORMAT = "json"

def create_comparator_llm() -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=OLLAMA_TEMPERATURE,
        format=OLLAMA_FORMAT,
        num_ctx=4096,
        keep_alive="0s"
    )


def run_comparator(state: Dict[str, Any]) -> Dict[str, Any]:

    product_names = state.get("product_names", [])
    
    if len(product_names) != 2:
        logging.warning(f"Comparator: invalid input, expected 2 products, got {len(product_names)}")
        return {
            "comparison_data": None,
            "comparator_error": "invalid_input",
            "comparator_error_message": "Агенту передано неверное количество товаров."
        }
    
    logging.info(f"Comparator: loading specs for {product_names}")
    specs_a = load_product_specs(product_names[0])
    specs_b = load_product_specs(product_names[1])

    if not specs_a or not specs_b:
        missing = [name for name, spec in zip(product_names, [specs_a, specs_b]) if not spec]
        logging.warning(f"Comparator: products not found in knowledge base: {missing}")
        return {
            "comparison_data": None,
            "comparator_error": "product_not_found",
            "comparator_error_message": f"Товары не найдены в базе: {', '.join(missing)}"
        }

    # Загрузка предпочтений и подготовка текста для промпта
    user_prefs = load_user_preferences()
    specs_text_a = format_specs_for_prompt(specs_a)
    specs_text_b = format_specs_for_prompt(specs_b)

    prompts = load_prompts()
    system_prompt = prompts.get("comparator", {}).get("system", "")
    if not system_prompt:
        system_prompt = "Ты аналитик. Сравни два товара и верни строго JSON."
    
    semantic_context = load_semantic_context()
    if semantic_context:
        system_prompt += "\n\n## СПРАВОЧНЫЙ КОНТЕКСТ (ДОМЕННЫЕ ЗНАНИЯ)\n" + semantic_context
    
    # Экранирование фигурных скобок для LangChain (JSON-примеры в промпте ломают парсер шаблонов)
    system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")

    # Шаблон промпта с переменными, которые подставит LangChain
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Товар 1:\n{specs_a}\n\nТовар 2:\n{specs_b}\n\nПредпочтения пользователя:\n{user_prefs}")
    ])

    llm = create_comparator_llm()
    chain = prompt | llm

    try:
        logging.debug(f"Comparator: invoking LLM with model {OLLAMA_MODEL}")
        response = chain.invoke({
            "specs_a": specs_text_a,
            "specs_b": specs_text_b,
            "user_prefs": json.dumps(user_prefs, ensure_ascii=False)
        })
        parsed = parse_json_response(response.content)
    except Exception as e:
        logging.error(f"Comparator: LLM execution failed: {e}", exc_info=True)
        return {
            "comparison_data": None,
            "comparator_error": "llm_execution_failed",
            "comparator_error_message": str(e)
        }
    
    if parsed.get("error"):
        logging.warning(f"Comparator: parsed response contains error: {parsed['error']}")
        return {
            "comparison_data": None,
            "comparator_error": parsed["error"],
            "comparator_error_message": parsed.get("error_message", "Ошибка генерации сравнения")
        }

    logging.info(f"Comparator: successfully generated comparison, winner={parsed.get('winner')}")
    return {
        "comparison_data": parsed,
        "comparator_error": None,
        "comparator_error_message": None
    }


def parse_json_response(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    default = {
        "comparison_table": None,
        "winner": None,
        "winner_reason": None,
        "recommendation": None,
        "warnings": [],
        "error": "parse_error",
        "error_message": "Не удалось распарсить ответ модели"
    }

    try:
        parsed = json.loads(cleaned)
        for key in default:
            if key not in parsed:
                parsed[key] = default[key]
        logging.debug(f"parse_json_response: successfully parsed, keys={list(parsed.keys())}")
        return parsed
    except json.JSONDecodeError as e:
        logging.warning(f"parse_json_response: JSON decode failed: {e}")
        return default