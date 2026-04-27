"""
Основной файл сборки графа LangGraph.
Определяет состояние (State), узлы (Nodes) и маршрутизацию (Edges).
"""

import logging
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, START, END

from agents.router import run_router
from agents.comparator import run_comparator
from agents.wishlist import run_wishlist

from tools.export import export_report_to_file
from tools.wishlist import add_to_wishlist

# Определяем состояние (state)
class ProductComparisonState(TypedDict):
    """
    Структура данных, которая передается между узлами графа.
    Содержит все поля, необходимые для работы всех агентов.
    """
    user_input: str
    
    # Данные от Router
    parsed_intent: Optional[str]
    product_names: Optional[List[str]]
    parsed_params: Optional[Dict[str, Any]]
    router_error: Optional[str]
    router_error_message: Optional[str]
    
    # Данные от Comparator
    comparison_data: Optional[Dict[str, Any]]
    comparator_error: Optional[str]
    comparator_error_message: Optional[str]
    
    # Данные от WishlistAgent
    wishlist_entry: Optional[Dict[str, Any]]
    wishlist_error: Optional[str]
    wishlist_error_message: Optional[str]
    
    # Итоговый ответ для пользователя
    final_output: str

# Узлы графа
def router_node(state: ProductComparisonState) -> Dict[str, Any]:
    logging.debug("router_node: executing run_router")
    result = run_router(state)
    logging.info(f"router_node: completed, intent={result.get('parsed_intent')}, error={result.get('router_error')}")
    return result


def comparator_node(state: ProductComparisonState) -> Dict[str, Any]:
    logging.debug("comparator_node: executing run_comparator")
    result = run_comparator(state)
    logging.info(f"comparator_node: completed, error={result.get('comparator_error')}")
    return result


def wishlist_agent_node(state: ProductComparisonState) -> Dict[str, Any]:
    logging.debug("wishlist_agent_node: executing run_wishlist")
    result = run_wishlist(state)
    logging.info(f"wishlist_agent_node: completed, error={result.get('wishlist_error')}")
    return result


def action_node(state: ProductComparisonState) -> Dict[str, Any]:
    """
    Узел выполнения действий (сохранение в файл).
    Вызывается ПОСЛЕ того, как агент успешно вернул данные.
    """
    intent = state.get("parsed_intent")
    logging.debug(f"action_node: executing for intent '{intent}'")
    
    # Логика экспорта отчета
    if intent == "compare_and_export":
        data = state.get("comparison_data")
        if data and data.get("comparison_table"):
            logging.info("action_node: exporting comparison report")
            # Формируем Markdown-строку из данных сравнения
            md_content = format_comparison_to_markdown(data)
            table_data = data.get("comparison_table", {})
            
            export_report_to_file(
                table_data=table_data,
                markdown_content=md_content
            )
    
    # Логика добавления в вишлист
    elif intent == "wishlist":
        entry = state.get("wishlist_entry")
        if entry and not state.get("wishlist_error"):
            logging.info("action_node: adding item to wishlist file")
            add_to_wishlist(entry)
            
    return {}


def response_node(state: ProductComparisonState) -> Dict[str, Any]:
    """
    Узел формирования финального ответа.
    Собирает все результаты и ошибки в одну строку для вывода пользователю.
    """
    # 1. Проверка ошибок 
    if state.get("router_error"):
        logging.info("response_node: returning router error message")
        return {"final_output": state.get("router_error_message", "Ошибка маршрутизации")}
        
    if state.get("comparator_error"):
        logging.info("response_node: returning comparator error message")
        return {"final_output": state.get("comparator_error_message", "Ошибка сравнения")}
        
    if state.get("wishlist_error"):
        logging.info("response_node: returning wishlist error message")
        return {"final_output": state.get("wishlist_error_message", "Ошибка вишлиста")}

    # 2. Формирование успешного ответа
    intent = state.get("parsed_intent")
    logging.debug(f"response_node: generating response for intent '{intent}'")
    
    if intent == "update_prefs":
        return {"final_output": state.get("router_error_message", "Настройки обновлены.")}
        
    elif intent in ("compare", "compare_and_export"):
        data = state.get("comparison_data")
        if data:
            response = format_comparison_to_markdown(data)
            if intent == "compare_and_export":
                response += "\n\n[Отчет успешно сохранен в файл]"
            return {"final_output": response}
        logging.warning("response_node: compare intent but no comparison data available")
        return {"final_output": "Сравнение не удалось."}
        
    elif intent == "wishlist":
        entry = state.get("wishlist_entry")
        if entry:
            return {"final_output": f"Товар '{entry.get('name')}' добавлен в вишлист."}
        logging.warning("response_node: wishlist intent but no entry data available")
        return {"final_output": "Не удалось добавить в вишлист."}
        
    logging.warning(f"response_node: unknown intent '{intent}', returning default message")
    return {"final_output": "Неизвестный сценарий."}

# Вспомогательные функции
def format_comparison_to_markdown(data: Dict[str, Any]) -> str:
    """Превращает JSON-ответ Comparator в читаемый текст."""
    logging.debug("format_comparison_to_markdown: formatting data")
    table = data.get("comparison_table", {})
    headers = table.get("headers", [])
    rows = table.get("rows", [])
    
    lines = []
    lines.append(f"### Сравнение: {data.get('winner', 'Результат')}")
    lines.append(f"**Рекомендация:** {data.get('recommendation', '')}\n")
    
    # Таблица Markdown
    if headers and rows:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join([str(x) for x in row]) + " |")
    
    warnings = data.get("warnings", [])
    if warnings:
        lines.append("\n**Предупреждения:**")
        for w in warnings:
            lines.append(f"- {w}")
            
    return "\n".join(lines)

# Маршрутизация
def route_after_router(state: ProductComparisonState) -> str:
    """Решает, куда идти после Router."""
    if state.get("router_error"):
        logging.warning("route_after_router: error detected, routing to response")
        return "response"  # Если ошибка ввода - сразу ответ
    
    intent = state.get("parsed_intent")
    logging.debug(f"route_after_router: routing for intent '{intent}'")
    if intent == "update_prefs":
        return "response"  # Настройки обновились в Router - сразу ответ
    elif intent in ("compare", "compare_and_export"):
        return "comparator"
    elif intent == "wishlist":
        return "wishlist_agent"
    else:
        return "response"  # Для прочих случаев


def route_after_comparator(state: ProductComparisonState) -> str:
    """Решает, куда идти после Comparator."""
    if state.get("comparator_error"):
        logging.warning("route_after_comparator: error detected, routing to response")
        return "response"  # Ошибка сравнения - ответ
    
    intent = state.get("parsed_intent")
    logging.debug(f"route_after_comparator: routing for intent '{intent}'")
    if intent == "compare_and_export":
        return "action"  # Успешно сравнили + нужно экспортировать
    else:
        return "response"  # Просто сравнили - ответ


def route_after_wishlist(state: ProductComparisonState) -> str:
    """Решает, куда идти после WishlistAgent."""
    logging.debug("route_after_wishlist: routing to action")
    # Всегда идем в action, чтобы попытаться сохранить в файл
    return "action"


def route_after_action(state: ProductComparisonState) -> str:
    """После действий всегда идем к ответу."""
    logging.debug("route_after_action: routing to response")
    return "response"

# Собираем граф
def build_graph() -> StateGraph:
    """Создает и компилирует граф."""
    logging.info("build_graph: initializing workflow")
    workflow = StateGraph(ProductComparisonState)

    # Добавляем узлы
    workflow.add_node("router", router_node)
    workflow.add_node("comparator", comparator_node)
    workflow.add_node("wishlist_agent", wishlist_agent_node)
    workflow.add_node("action", action_node)
    workflow.add_node("response", response_node)

    # Добавляем связи (Edges)
    workflow.add_edge(START, "router")
    
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "comparator": "comparator",
            "wishlist_agent": "wishlist_agent",
            "response": "response"
        }
    )
    
    workflow.add_conditional_edges(
        "comparator",
        route_after_comparator,
        {
            "action": "action",
            "response": "response"
        }
    )
    
    workflow.add_edge("wishlist_agent", "action")
    workflow.add_edge("action", "response")
    workflow.add_edge("response", END)

    logging.info("build_graph: workflow compiled successfully")
    return workflow.compile()

# Экспортируем готовый граф для использования в main.py
app = build_graph()