"""
Управление предпочтениями пользователя (бюджет, бренды, приоритеты).
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from .base import USER_PREFS_FILE, load_json_file, save_json_file

VALID_PREFS_FIELDS = {
    "budget": int,
    "preferred_brands": list,
    "avoided_brands": list,
    "feature_priority": list,
    "min_rating": float,
    "reset": bool
}

VALID_FEATURE_PRIORITIES = {
    "battery", "memory", "camera", "price", "display", 
    "processor", "storage", "weight", "rating", "brand"
}

DEFAULT_PREFS = {
    "budget": None,
    "currency": "RUB",
    "preferred_brands": [],
    "avoided_brands": [],
    "feature_priority": ["battery", "memory", "camera", "price"],
    "min_rating": 4.0,
    "last_updated": None,
    "settings": {
        "language": "ru",
        "export_format": "markdown",
        "auto_save_wishlist": False
    }
}


def load_user_preferences() -> Dict[str, Any]:
    logging.debug("load_user_preferences: loading preferences from file")
    prefs = load_json_file(USER_PREFS_FILE, default={})
    # Гарантируем наличие всех полей
    for key, value in DEFAULT_PREFS.items():
        if key not in prefs:
            prefs[key] = value
    logging.debug(f"load_user_preferences: loaded and merged {len(prefs)} preference fields")
    return prefs


def normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует ключи и значения параметров от LLM.
    
    Приводит ключи к lowercase с подчёркиваниями,
    убирает лишние пробелы в значениях.
    """
    logging.debug(f"normalize_params: normalizing {len(params)} parameters")
    normalized = {}
    for key, value in params.items():
        # Нормализация ключа
        # lowercase + замена пробелов на подчёркивания + удаление лишних символов
        norm_key = key.lower().strip().replace(" ", "_").replace("-", "_")
        # Убираем двойные подчёркивания
        while "__" in norm_key:
            norm_key = norm_key.replace("__", "_")
        
        if isinstance(value, list):
            if norm_key == "feature_priority":
                # lowercase + strip для характеристик
                norm_value = [item.lower().strip() for item in value if isinstance(item, str) and item.strip()]
            elif norm_key in ("preferred_brands", "avoided_brands"):
                # Только strip для брендов (сохраняем регистр)
                norm_value = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            else:
                norm_value = value
        elif isinstance(value, str):
            norm_value = value.strip()
        else:
            norm_value = value
        
        normalized[norm_key] = norm_value
    return normalized


def update_user_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    logging.info(f"update_user_preferences: received raw params: {list(params.keys())}")
    params = normalize_params(params)
    prefs = load_user_preferences()
    
    # Сброс
    if params.get("reset") is True:
        logging.info("update_user_preferences: reset to defaults requested")
        prefs = DEFAULT_PREFS.copy()
        prefs["last_updated"] = datetime.now(timezone.utc).isoformat()
        save_json_file(USER_PREFS_FILE, prefs)
        return {"success": True, "message": "Настройки сброшены", "updated_prefs": prefs}
    
    # Обновление полей
    for key, value in params.items():
        if key == "reset":
            continue
        if key not in VALID_PREFS_FIELDS:
            logging.warning(f"update_user_preferences: invalid parameter '{key}'")
            return {"success": False, "message": f"Недопустимый параметр: {key}", "updated_prefs": prefs}
        
        expected_type = VALID_PREFS_FIELDS[key]
        if not isinstance(value, expected_type):
            logging.warning(f"update_user_preferences: invalid type for '{key}' (expected {expected_type.__name__})")
            return {"success": False, "message": f"Неверный тип для {key}", "updated_prefs": prefs}
        
        if key == "feature_priority":
            invalid = set(value) - VALID_FEATURE_PRIORITIES
            if invalid:
                logging.warning(f"update_user_preferences: invalid features requested: {invalid}")
                return {"success": False, "message": f"Недопустимые характеристики: {invalid}", "updated_prefs": prefs}
            prefs[key] = value
        elif key == "budget" and value < 0:
            logging.warning(f"update_user_preferences: negative budget value '{value}'")
            return {"success": False, "message": "Бюджет не может быть отрицательным", "updated_prefs": prefs}
        elif key == "min_rating" and not (0 <= value <= 5):
            logging.warning(f"update_user_preferences: out-of-range rating value '{value}'")
            return {"success": False, "message": "Рейтинг должен быть от 0 до 5", "updated_prefs": prefs}
        else:
            prefs[key] = value
            
    prefs["last_updated"] = datetime.now(timezone.utc).isoformat()
    logging.debug(f"update_user_preferences: saving updated preferences with keys: {list(prefs.keys())}")
    if save_json_file(USER_PREFS_FILE, prefs):
        logging.info("update_user_preferences: preferences saved successfully")
        return {"success": True, "message": "Предпочтения обновлены", "updated_prefs": prefs}
    logging.error("update_user_preferences: failed to save preferences file to disk")
    return {"success": False, "message": "Ошибка сохранения", "updated_prefs": prefs}