"""
Инструменты для мультиагентной системы Product Comparison Assistant.

Этот модуль содержит детерминированные функции для работы с файловой системой,
управления пользовательскими данными и взаимодействия с базой знаний.
Все функции возвращают либо результат, либо ошибку в виде строки.
"""

import os
import json
import shutil
import csv
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

# Базовые пути (относительно корня проекта)
BASE_DIR = Path(__file__).parent.parent  # product-comparator/
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REPORTS_DIR = DATA_DIR / "reports"

# Имена файлов
USER_PREFS_FILE = DATA_DIR / "user_prefs.json"
WISHLIST_FILE = DATA_DIR / "wishlist.md"

# Шаблоны
USER_PREFS_TEMPLATE = TEMPLATES_DIR / "user_prefs.json.example"
WISHLIST_TEMPLATE = TEMPLATES_DIR / "wishlist.md.example"

# Допустимые поля для обновления предпочтений
VALID_PREFS_FIELDS = {
    "budget": int,
    "preferred_brands": list,
    "avoided_brands": list,
    "feature_priority": list,
    "min_rating": float,
    "reset": bool
}

# Допустимые значения для feature_priority
VALID_FEATURE_PRIORITIES = {
    "battery", "memory", "camera", "price", "display", 
    "processor", "storage", "weight", "rating", "brand"
}


# Работа с файлами
def ensure_dirs_exist() -> None:
    """
    Создаёт необходимые папки, если они не существуют.
    Вызывается автоматически при импорте модуля.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def load_json_file(filepath: Path, default: Optional[Dict] = None) -> Dict:
    """
    Загружает JSON-файл. Если файл не найден или повреждён — возвращает default.
    
    Args:
        filepath: Путь к файлу
        default: Значение по умолчанию (обычно пустой словарь)
    
    Returns:
        Словарь с данными или default
    """
    if default is None:
        default = {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        print(f"Warning: JSON decode error in {filepath}: {e}")
        return default


def save_json_file(filepath: Path, data: Dict) -> bool:
    """
    Сохраняет словарь в JSON-файл с форматированием.
    
    Args:
        filepath: Путь к файлу
        data: Данные для сохранения
    
    Returns:
        True если успешно, False если ошибка
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False


def load_markdown_file(filepath: Path) -> str:
    """
    Загружает содержимое Markdown-файла.
    
    Args:
        filepath: Путь к файлу
    
    Returns:
        Строка с содержимым или пустая строка при ошибке
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""


def append_to_markdown_file(filepath: Path, content: str) -> bool:
    """
    Добавляет контент в конец Markdown-файла.
    
    Args:
        filepath: Путь к файлу
        content: Текст для добавления
    
    Returns:
        True если успешно, False если ошибка
    """
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content + "\n")
        return True
    except Exception as e:
        print(f"Error appending to {filepath}: {e}")
        return False


# Инициализация данных из шаблонов
def initialize_data_files() -> Dict[str, str]:
    """
    Проверяет наличие файлов данных. Если файл отсутствует,
    копирует его из шаблона (.example).
    
    Returns:
        Словарь с результатами: {"created": [...], "skipped": [...], "errors": [...]}
    """
    ensure_dirs_exist()
    
    results = {"created": [], "skipped": [], "errors": []}
    
    # Список файлов для инициализации: (целевой путь, шаблон)
    files_to_init = [
        (USER_PREFS_FILE, USER_PREFS_TEMPLATE),
        (WISHLIST_FILE, WISHLIST_TEMPLATE)
    ]
    
    for target_path, template_path in files_to_init:
        # Если файл уже существует — пропускаем
        if target_path.exists():
            results["skipped"].append(str(target_path.name))
            continue
        
        # Если шаблона нет — ошибка
        if not template_path.exists():
            results["errors"].append(f"Template not found: {template_path.name}")
            continue
        
        try:
            # Копируем шаблон в целевую папку
            shutil.copy2(template_path, target_path)
            results["created"].append(str(target_path.name))
            print(f"Initialized: {target_path.name}")
        except Exception as e:
            results["errors"].append(f"{target_path.name}: {str(e)}")
            print(f"Error initializing {target_path.name}: {e}")
    
    return results


# Управление пользовательскими предпочтениями
def load_user_preferences() -> Dict[str, Any]:
    """
    Загружает предпочтения пользователя из файла.    

    Returns:
        Словарь с предпочтениями или дефолтные значения
    """
    prefs = load_json_file(USER_PREFS_FILE, default={})
    
    # Гарантируем наличие всех полей
    default_prefs = {
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
    
    # Обновляем только отсутствующие поля
    for key, value in default_prefs.items():
        if key not in prefs:
            prefs[key] = value
    
    return prefs

def normalize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует ключи и значения параметров от LLM.
    
    Приводит ключи к lowercase с подчёркиваниями,
    убирает лишние пробелы в значениях.
    """
    normalized = {}
    
    for key, value in params.items():
        # Нормализация ключа
        # lowercase + замена пробелов на подчёркивания + удаление лишних символов
        norm_key = key.lower().strip().replace(" ", "_").replace("-", "_")
        # Убираем двойные подчёркивания
        while "__" in norm_key:
            norm_key = norm_key.replace("__", "_")
        
        # Нормализация значения
        if isinstance(value, list):
            if norm_key == "feature_priority":
                # lowercase + strip для характеристик
                norm_value = [
                    item.lower().strip() 
                    for item in value 
                    if isinstance(item, str) and item.strip()
                ]
            elif norm_key in ("preferred_brands", "avoided_brands"):
                # Только strip для брендов (сохраняем регистр)
                norm_value = [
                    item.strip()
                    for item in value
                    if isinstance(item, str) and item.strip()
                ]
            else:
                norm_value = value
        elif isinstance(value, str):
            norm_value = value.strip()
        else:
            # Числа, булевы значения — как есть
            norm_value = value
        
        normalized[norm_key] = norm_value
    
    return normalized


def update_user_preferences(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обновляет предпочтения пользователя на основе переданных параметров.
    
    Args:
        params: Словарь с параметрами для обновления (из Router)
    
    Returns:
        Словарь с результатом: {"success": bool, "message": str, "updated_prefs": dict}
    """

    # Нормализуем входные данные
    params = normalize_params(params)

    # Загружаем текущие предпочтения
    prefs = load_user_preferences()
    
    # Обработка флага сброса
    if params.get("reset") is True:
    # Создаём дефолтные настройки с нуля
        prefs = {
            "budget": None,
            "currency": "RUB",
            "preferred_brands": [],
            "avoided_brands": [],
            "feature_priority": ["battery", "memory", "camera", "price"],
            "min_rating": 4.0,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "settings": {
                "language": "ru",
                "export_format": "markdown",
                "auto_save_wishlist": False
            }
        }
        save_json_file(USER_PREFS_FILE, prefs)
        return {
            "success": True,
            "message": "Настройки сброшены к значениям по умолчанию",
            "updated_prefs": prefs
        }
    
    # Поочерёдно обновляем поля
    for key, value in params.items():
        # Пропускаем служебные ключи
        if key in ("reset",):
            continue
        
        # Проверяем, что поле допустимо
        if key not in VALID_PREFS_FIELDS:
            return {
                "success": False,
                "message": f"Недопустимый параметр: {key}",
                "updated_prefs": prefs
            }
        
        # Валидация типа
        expected_type = VALID_PREFS_FIELDS[key]
        if not isinstance(value, expected_type):
            return {
                "success": False,
                "message": f"Неверный тип для {key}: ожидается {expected_type.__name__}",
                "updated_prefs": prefs
            }
        
        # Специальная валидация для массивов
        if key == "feature_priority":
            # Проверяем допустимые значения приоритетов
            invalid_features = set(value) - VALID_FEATURE_PRIORITIES
            if invalid_features:
                return {
                    "success": False,
                    "message": f"Недопустимые характеристики: {invalid_features}",
                    "updated_prefs": prefs
                }
            prefs[key] = value
        
        # Валидация числовых полей
        elif key == "budget":
            if value < 0:
                return {
                    "success": False,
                    "message": "Бюджет не может быть отрицательным",
                    "updated_prefs": prefs
                }
            prefs[key] = value
        
        elif key == "min_rating":
            if not (0 <= value <= 5):
                return {
                    "success": False,
                    "message": "Рейтинг должен быть от 0 до 5",
                    "updated_prefs": prefs
                }
            prefs[key] = value
        
        else:
            prefs[key] = value
    
    # Обновляем метку времени
    prefs["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    # Сохраняем
    if save_json_file(USER_PREFS_FILE, prefs):
        return {
            "success": True,
            "message": "Предпочтения обновлены",
            "updated_prefs": prefs
        }
    else:
        return {
            "success": False,
            "message": "Ошибка сохранения предпочтений",
            "updated_prefs": prefs
        }



# Работа с базой знаний (knowledge)
def load_product_specs(product_name: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Ищет характеристики товара в базе знаний.
    
    Алгоритм поиска:
    1. Ищет точное совпадение названия в любом файле knowledge/
    2. Если category указана — ищет только в соответствующем файле
    3. Возвращает словарь с характеристиками или None
    
    Args:
        product_name: Название товара (как ввёл пользователь)
        category: Опциональная категория для сужения поиска
    
    Returns:
        Словарь с характеристиками или None если не найдено
    """
    # Нормализуем название для поиска (нижний регистр, без лишних пробелов)
    search_name = product_name.strip().lower()
    
    # Определяем, какие файлы проверять
    if category:
        files_to_check = [KNOWLEDGE_DIR / f"{category.stip().lower()}.md"]
    else:
        files_to_check = list(KNOWLEDGE_DIR.glob("*.md"))
    
    for filepath in files_to_check:
        content = load_markdown_file(filepath)
        if not content:
            continue
        
        # Парсим Markdown-файл с простой структурой:
        # ## Название товара
        # - характеристика: значение
        # - характеристика: значение
        
        sections = content.split("## ")
        for section in sections[1:]:  # Пропускаем первый пустой
            lines = section.strip().split("\n")
            title = lines[0].strip().lower()
            
            # Проверяем совпадение названия
            if search_name in title or title in search_name:
                specs = {"name": lines[0].strip(), "source_file": filepath.name}
                
                # Парсим характеристики
                for line in lines[1:]:
                    line = line.strip()
                    if line.startswith("- ") and ":" in line:
                        key, value = line[2:].split(":", 1)
                        specs[key.strip()] = value.strip()
                
                return specs
    
    return None


def list_available_products(category: Optional[str] = None) -> List[str]:
    """
    Возвращает список товаров, доступных в базе знаний.
    
    Args:
        category: Опциональная категория для фильтрации
    
    Returns:
        Список названий товаров
    """
    products = []
    
    if category:
        files_to_check = [KNOWLEDGE_DIR / f"{category.strip().lower()}.md"]
    else:
        files_to_check = list(KNOWLEDGE_DIR.glob("*.md"))
    
    for filepath in files_to_check:
        content = load_markdown_file(filepath)
        if not content:
            continue
        
        # Извлекаем заголовки второго уровня (## Название товара)
        for line in content.split("\n"):
            if line.strip().startswith("## "):
                product_name = line.strip()[3:].strip()
                products.append(product_name)
    
    return products


# Экспорт отчетов
def export_report_as_markdown(content: str, filename: Optional[str] = None) -> Dict[str, Any]:

    ensure_dirs_exist()
    
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    filepath = REPORTS_DIR / f"{filename}.md"
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "filepath": str(filepath), "message": f"Markdown сохранён: {filepath.name}"}
    except Exception as e:
        return {"success": False, "filepath": None, "message": f"Ошибка Markdown: {str(e)}"}


def export_report_as_csv(table_data: Dict[str, Any], filename: Optional[str] = None) -> Dict[str, Any]:
    
    if not table_data or "headers" not in table_data or "rows" not in table_data:
        return {"success": False, "filepath": None, "message": "Неверный формат данных для CSV (нет headers/rows)."}
    
    ensure_dirs_exist()
    
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    filepath = REPORTS_DIR / f"{filename}.csv"
    
    try:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(table_data["headers"])
            writer.writerows(table_data["rows"])
        return {"success": True, "filepath": str(filepath), "message": f"CSV сохранён: {filepath.name}"}
    except Exception as e:
        return {"success": False, "filepath": None, "message": f"Ошибка CSV: {str(e)}"}


def export_report_to_file(
    table_data: Dict[str, Any], 
    markdown_content: str, 
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Координатор экспорта: сохраняет отчёт в Markdown и CSV с одинаковым базовым именем.
    Делегирует работу специализированным функциям и агрегирует результат.
    """
    ensure_dirs_exist()
    
    # Генерируем единое имя файла один раз
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Вызываем специализированные функции
    md_result = export_report_as_markdown(markdown_content, filename=filename)
    csv_result = export_report_as_csv(table_data, filename=filename)
    
    # Агрегация результатов
    files_created = []
    if md_result["success"]: files_created.append("md")
    if csv_result["success"]: files_created.append("csv")
    
    messages = []
    if md_result["success"]: messages.append(md_result["message"])
    if csv_result["success"]: messages.append(csv_result["message"])
    if not md_result["success"]: messages.append(f"[MD] {md_result['message']}")
    if not csv_result["success"]: messages.append(f"[CSV] {csv_result['message']}")
    
    return {
        "success": len(files_created) > 0,  # Успех, если создан хотя бы один файл
        "files": {
            "markdown": md_result.get("filepath"),
            "csv": csv_result.get("filepath")
        },
        "message": "; ".join(messages)
    }


# Управление вишлистом
def load_wishlist() -> List[Dict[str, Any]]:
    """
    Загружает текущий вишлист из файла.
    
    Returns:
        Список словарей с товарами или пустой список
    """
    content = load_markdown_file(WISHLIST_FILE)
    if not content:
        return []
    
    wishlist = []
    current_entry = None
    
    for line in content.split("\n"):
        line = line.strip()
        
        # Пропускаем заголовки и пустые строки
        if not line or line.startswith("#"):
            continue
        
        # Новая запись начинается с "- "
        if line.startswith("- "):
            # Сохраняем предыдущую запись
            if current_entry:
                wishlist.append(current_entry)
            
            # Начинаем новую (пока просто сохраняем сырую строку)
            current_entry = {"raw": line[2:], "specs": {}}
        elif current_entry and ":" in line:
            # Парсим характеристики внутри записи
            key, value = line.split(":", 1)
            current_entry["specs"][key.strip()] = value.strip()
    
    # Не забываем последнюю запись
    if current_entry:
        wishlist.append(current_entry)
    
    return wishlist


def check_wishlist_duplicate(product_name: str) -> bool:
    """
    Проверяет, есть ли товар уже в вишлисте.
    
    Args:
        product_name: Название товара для проверки
    
    Returns:
        True если дубликат найден, False если нет
    """
    wishlist = load_wishlist()
    search_name = product_name.strip().lower()
    
    for entry in wishlist:
        entry_name = entry.get("name", entry.get("raw", "")).lower()
        if search_name in entry_name or entry_name in search_name:
            return True
    
    return False


def add_to_wishlist(entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Добавляет товар в вишлист.
    
    Args:
        entry_data: Словарь с данными из WishlistAgent (wishlist_entry)
    
    Returns:
        Словарь с результатом: {"success": bool, "message": str}
    """
    # Проверяем дубликаты
    if check_wishlist_duplicate(entry_data.get("name", "")):
        return {
            "success": False,
            "message": "Этот товар уже есть в вашем вишлисте"
        }
    
    # Формируем Markdown-запись
    name = entry_data.get("name", "Unknown")
    category = entry_data.get("category", "other")
    specs = entry_data.get("specs", {})
    priority = entry_data.get("priority", "medium")
    notes = entry_data.get("notes", "")
    added_at = entry_data.get("added_at", get_current_timestamp())
    
    lines = [
        f"- **{name}** ({category})",
        f"  - Приоритет: {priority}",
        f"  - Добавлено: {added_at}"
    ]
    
    # Добавляем все характеристики из specs (включая цену)
    for key, value in specs.items():
        lines.append(f"  - {key}: {value}")
    
    # Добавляем заметку, если есть
    if notes:
        lines.append(f"  - Заметка: {notes}")
    
    lines.append("")  # Пустая строка между записями
    
    # Записываем в файл
    if append_to_markdown_file(WISHLIST_FILE, "\n".join(lines)):
        return {
            "success": True,
            "message": f"{name} добавлен в вишлист"
        }
    else:
        return {
            "success": False,
            "message": "Ошибка добавления в вишлист"
        }


def remove_from_wishlist(product_name: str) -> Dict[str, Any]:
    """
    Удаляет товар из вишлиста по названию.
    
    Args:
        product_name: Название товара для удаления
    
    Returns:
        Словарь с результатом
    """
    wishlist = load_wishlist()
    search_name = product_name.strip().lower()
    
    # Ищем индекс для удаления
    for i, entry in enumerate(wishlist):
        entry_name = entry.get("name", entry.get("raw", "")).lower()
        if search_name in entry_name or entry_name in search_name:
            removed = wishlist.pop(i)
            
            # Перезаписываем файл без удалённой записи
            try:
                with open(WISHLIST_FILE, "w", encoding="utf-8") as f:
                    f.write("# Wishlist\n\n")
                    for entry in wishlist:
                        f.write(f"- **{entry.get('name', entry.get('raw'))}**\n")
                        for key, value in entry.get("specs", {}).items():
                            f.write(f"  - {key}: {value}\n")
                        f.write("\n")
                
                return {
                    "success": True,
                    "message": f"{product_name} удалён из вишлиста"
                }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"Ошибка удаления: {str(e)}"
                }
    
    return {
        "success": False,
        "message": f"Товар '{product_name}' не найден в вишлисте"
    }

# Вспомогательные функции для агентов
def format_specs_for_prompt(specs: Optional[Dict[str, Any]]) -> str:
    """
    Форматирует характеристики товара для вставки в промпт.
    
    Args:
        specs: Словарь с характеристиками
    
    Returns:
        Отформатированная строка или сообщение об отсутствии данных
    """
    if not specs:
        return "Данные о товаре отсутствуют в базе знаний."
    
    lines = [f"Товар: {specs.get('name', 'Неизвестный')}"]
    
    # Сортируем ключи для консистентности
    for key in sorted(specs.keys()):
        if key in ("name", "source_file"):
            continue
        value = specs[key]
        lines.append(f"- {key}: {value}")
    
    return "\n".join(lines)


def get_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

# Создаём папки при импорте модуля
ensure_dirs_exist()