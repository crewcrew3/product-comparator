"""
Навык: Сравнение товаров.
Агент загружает характеристики, учитывает предпочтения,
вызывает LLM для генерации сравнительной таблицы и рекомендации.
"""
from tools.knowledge import load_product_specs, format_specs_for_prompt
from tools.preferences import load_user_preferences
from config.prompts import load_prompts

PRODUCT_COMPARISON_SKILL = {
    "name": "ProductComparison",
    "description": "Сравнивает два товара по характеристикам, учитывает пользовательские предпочтения и возвращает структурированный отчёт.",
    "required_tools": [
        "load_product_specs",
        "format_specs_for_prompt",
        "load_user_preferences"
    ],
    "prompt_source": "comparator",
    "input_schema": {
        "product_names": ["str", "str"],
        "category": "str | None"
    },
    "output_schema": {
        "comparison_data": "dict",
        "error": "str | None"
    },
    "usage_notes": "Требует ровно 2 названия товара. Возвращает ошибку, если товар не найден в knowledge/."
}