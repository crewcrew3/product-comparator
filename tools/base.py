"""
tools/base.py
Базовые утилиты: пути, создание директорий, чтение/запись файлов.
Используется всеми остальными модулями.
"""

import os
import json
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

# Базовые пути (относительно корня проекта)
BASE_DIR = Path(__file__).parent.parent
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


def ensure_dirs_exist() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def load_json_file(filepath: Path, default: Optional[Dict] = None) -> Dict:
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
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False


def load_markdown_file(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""


def append_to_markdown_file(filepath: Path, content: str) -> bool:
    """Добавляет контент в конец Markdown-файла."""
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


def get_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

# Инициализация папок при импорте
ensure_dirs_exist()