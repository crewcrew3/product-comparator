"""
Навык: Настройка предпочтений.
Агент обновляет бюджет, бренды, приоритеты характеристик.
"""
from tools.preferences import load_user_preferences, update_user_preferences

PREFERENCE_SETUP_SKILL = {
    "name": "PreferenceSetup",
    "description": "Обновляет пользовательские предпочтения: бюджет, бренды, приоритеты характеристик, рейтинг.",
    "required_tools": [
        "load_user_preferences",
        "update_user_preferences"
    ],
    "prompt_source": "router",
    "input_schema": {
        "params": {
            "budget": "int | None",
            "preferred_brands": "list[str] | None",
            "avoided_brands": "list[str] | None",
            "feature_priority": "list[str] | None",
            "min_rating": "float | None",
            "reset": "bool"
        }
    },
    "output_schema": {
        "success": "bool",
        "message": "str",
        "updated_prefs": "dict"
    },
    "usage_notes": "Поддерживает частичное обновление. Параметр `reset: true` сбрасывает настройки к дефолтным."
}