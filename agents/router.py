"""
Агент Router (Маршрутизатор) для Product Comparison Assistant.

Отвечает за:
- Классификацию намерения пользователя (intent)
- Извлечение названий товаров из запроса
- Парсинг параметров для обновления предпочтений
- Возврат строго структурированного JSON для дальнейшей обработки

Не выполняет никаких действий с файлами или базой знаний — только анализ текста.
"""

import json
import re
import logging
from typing import Dict, Any, Optional
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage

from config.prompts import load_prompts
from tools import load_user_preferences, update_user_preferences

OLLAMA_MODEL = "qwen2.5:3b"
# OLLAMA_BASE_URL = "http://host.docker.internal:11434"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_FORMAT = "json"

def create_router_llm() -> ChatOllama:
    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=OLLAMA_TEMPERATURE,
        format=OLLAMA_FORMAT,
        num_ctx=4096,  # Размер контекстного окна
        keep_alive="0s" # Выгружаем модель сразу чтобы мой ноут не умер
    )

def create_router_prompt(system_prompt: str) -> ChatPromptTemplate:
    """
    Создаёт шаблон промпта для Router.
    
    Args:
        system_prompt: Системная инструкция из prompts.yaml
    
    Returns:
        Настроенный ChatPromptTemplate
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{user_input}"),
    ])

def run_router(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Главный входной пункт агента Router.
    
    Анализирует пользовательский запрос, определяет намерение и извлекает данные.
    
    Args:
        state: Словарь состояния с ключами:
            - user_input: str, исходный запрос пользователя
    
    Returns:
        Обновлённый state с добавленными полями:
            - parsed_intent: str, распознанное намерение
            - product_names: List[str], извлечённые названия товаров
            - parsed_params: Dict, параметры для update_prefs
            - router_error: Optional[str], код ошибки если есть
            - router_error_message: Optional[str], сообщение для пользователя если есть
    """
    user_input = state.get("user_input", "").strip()
    
    if not user_input:
        logging.warning("Router: empty input received")
        return {
            "parsed_intent": "unknown",
            "product_names": [],
            "parsed_params": {},
            "router_error": "empty_input",
            "router_error_message": "Пожалуйста, введите запрос.",
        }
    
    logging.info(f"Router: processing input '{user_input[:100]}...'")
    
    prompts = load_prompts()
    system_prompt = prompts.get("router", {}).get("system", "")
    
    if not system_prompt:
        system_prompt = "Ты — маршрутизатор. Определи намерение пользователя и верни JSON."
    
    # LangChain парсит {} как переменные. JSON-примеры в промпте ломают парсер.
    # Заменяем { на {{ и } на }}, чтобы они воспринимались как текст.
    system_prompt = system_prompt.replace("{", "{{").replace("}", "}}")
    
    llm = create_router_llm()
    prompt = create_router_prompt(system_prompt)
    
    # | - передай вывод первого компонента на вход второму
    chain = prompt | llm
    
    try:
        logging.debug(f"Router: invoking LLM with model {OLLAMA_MODEL}")
        response = chain.invoke({
            "user_input": user_input,
        })
        
        response_content = response.content.strip()
        parsed_response = parse_router_response(response_content)
        
    except Exception as e:
        logging.error(f"Router: LLM execution failed: {e}", exc_info=True)
        # Обработка ошибок подключения или выполнения LLM
        parsed_response = {
            "intent": "unknown",
            "product_names": [],
            "parsed_params": {},
            "error": "llm_error",
            "error_message": f"Ошибка обработки запроса: {str(e)}"
        }
    
    if parsed_response.get("error"):
        logging.warning(f"Router: parsed response contains error: {parsed_response['error']}")
        return {
            "parsed_intent": "unknown",
            "product_names": parsed_response.get("product_names", []),
            "parsed_params": {},
            "router_error": parsed_response["error"],
            "router_error_message": parsed_response.get("error_message", "Произошла ошибка при анализе запроса."),
        }

    if parsed_response["intent"] == "update_prefs":
        logging.debug(f"Router: intent=update_prefs, params={parsed_response.get('parsed_params')}")
        prefs_result = handle_prefs_update(parsed_response.get("parsed_params", {}))
        
        if not prefs_result["success"]:
            logging.warning(f"Router: prefs update failed: {prefs_result['message']}")
            return {
                "parsed_intent": "unknown",
                "product_names": [],
                "parsed_params": {},
                "router_error": "prefs_update_failed",
                "router_error_message": prefs_result["message"],
            }
        
        logging.info(f"Router: preferences updated successfully")
        return {
            "parsed_intent": "update_prefs",
            "product_names": [],
            "parsed_params": parsed_response.get("parsed_params", {}),
            "router_error": None,
            "router_error_message": prefs_result["message"],
        }

    if parsed_response["intent"] in ("compare", "compare_and_export"):
        product_count = len(parsed_response.get("product_names", []))
        
        if product_count != 2:
            logging.warning(f"Router: compare intent but got {product_count} products (expected 2)")
            return {
                "parsed_intent": "unknown",
                "product_names": parsed_response.get("product_names", []),
                "parsed_params": {},
                "router_error": "invalid_product_count",
                "router_error_message": "Для сравнения укажите ровно 2 товара.",
            }
        
    if parsed_response["intent"] == "wishlist":
        product_count = len(parsed_response.get("product_names", []))
        
        if product_count != 1:
            logging.warning(f"Router: wishlist intent but got {product_count} products (expected 1)")
            return {
                "parsed_intent": "unknown",
                "product_names": parsed_response.get("product_names", []),
                "parsed_params": {},
                "router_error": "invalid_wishlist_product_count",
                "router_error_message": "Для добавления в вишлист укажите ровно 1 товар.",
            }
    
    # Успешный результат
    logging.info(f"Router: success, intent={parsed_response['intent']}, products={parsed_response.get('product_names')}")
    return {
        "parsed_intent": parsed_response["intent"],
        "product_names": parsed_response.get("product_names", []),
        "parsed_params": parsed_response.get("parsed_params", {}),
        "router_error": None,
        "router_error_message": None,
    }

# Вспомогательные функции
def parse_router_response(response_text: str) -> Dict[str, Any]:
    """
    Парсит ответ LLM, которая должна была вернуть джисон с полями intent, product_names, parsed_params, error, error_message, в словарь.
    """

    cleaned = response_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    # Дефолтное значение на случай парсинг-ошибки
    default_result = {
        "intent": "unknown",
        "product_names": [],
        "parsed_params": {},
        "error": "parse_error",
        "error_message": "Не удалось распознать формат ответа."
    }
    
    try:
        parsed = json.loads(cleaned)
        
        required_fields = ["intent", "product_names", "parsed_params", "error", "error_message"]
        for field in required_fields:
            if field not in parsed:
                parsed[field] = default_result[field]
        
        if not isinstance(parsed["product_names"], list):
            parsed["product_names"] = []
        if not isinstance(parsed["parsed_params"], dict):
            parsed["parsed_params"] = {}
        
        logging.debug(f"parse_router_response: successfully parsed, intent={parsed.get('intent')}")
        return parsed
        
    except json.JSONDecodeError as e:
        logging.warning(f"parse_router_response: JSON decode failed: {e}")
        return default_result


def handle_prefs_update(params: Dict[str, Any]) -> Dict[str, Any]:
    if not params:
        logging.warning("handle_prefs_update: no parameters provided")
        return {"success": False, "message": "Не указаны параметры для обновления."}
    
    result = update_user_preferences(params) # этот метод тоже возвращает джисон с success
    logging.debug(f"handle_prefs_update: update_user_preferences returned success={result.get('success')}")
    return {
        "success": result.get("success", False),
        "message": result.get("message", "Неизвестная ошибка")
    }