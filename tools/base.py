"""
Базовые утилиты: пути, создание директорий, чтение/запись файлов.
Используется всеми остальными модулями.
"""

import json
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
REPORTS_DIR = DATA_DIR / "reports"

USER_PREFS_FILE = DATA_DIR / "user_prefs.json"
WISHLIST_FILE = DATA_DIR / "wishlist.md"

USER_PREFS_TEMPLATE = TEMPLATES_DIR / "user_prefs.json.example"
WISHLIST_TEMPLATE = TEMPLATES_DIR / "wishlist.md.example"

SEMANTICS_DIR = KNOWLEDGE_DIR / "semantics"

def load_semantic_context() -> str:
    """Загружает семантические файлы как справочный контекст."""
    context_parts = []
    if SEMANTICS_DIR.exists():
        for md_file in SEMANTICS_DIR.glob("*.md"):
            with open(md_file, "r", encoding="utf-8") as f:
                context_parts.append(f.read())
        logging.debug(f"load_semantic_context: loaded {len(context_parts)} semantic files")
    return "\n\n".join(context_parts) if context_parts else ""


def ensure_dirs_exist() -> None:
    dirs_to_create = [DATA_DIR, REPORTS_DIR, TEMPLATES_DIR, KNOWLEDGE_DIR]
    for dir_path in dirs_to_create:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logging.debug(f"ensure_dirs_exist: created directory {dir_path}")


def load_json_file(filepath: Path, default: Optional[Dict] = None) -> Dict:
    if default is None:
        default = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            logging.debug(f"load_json_file: loaded {filepath}")
            return json.load(f)
    except FileNotFoundError:
        logging.debug(f"load_json_file: file not found {filepath}, using default")
        return default
    except json.JSONDecodeError as e:
        logging.warning(f"load_json_file: JSON decode error in {filepath}: {e}")
        return default


def save_json_file(filepath: Path, data: Dict) -> bool:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.debug(f"save_json_file: saved {filepath}")
        return True
    except Exception as e:
        logging.error(f"save_json_file: error saving {filepath}: {e}")
        return False


def load_markdown_file(filepath: Path) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            logging.debug(f"load_markdown_file: loaded {filepath}")
            return f.read()
    except FileNotFoundError:
        logging.debug(f"load_markdown_file: file not found {filepath}")
        return ""
    except Exception as e:
        logging.warning(f"load_markdown_file: error reading {filepath}: {e}")
        return ""


def append_to_markdown_file(filepath: Path, content: str) -> bool:
    """Добавляет контент в конец Markdown-файла."""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content + "\n")
        logging.debug(f"append_to_markdown_file: appended to {filepath}")
        return True
    except Exception as e:
        logging.error(f"append_to_markdown_file: error appending to {filepath}: {e}")
        return False

def initialize_data_files() -> Dict[str, str]:
    """
    Проверяет наличие файлов данных. Если файл отсутствует,
    копирует его из шаблона (.example).
    """
    ensure_dirs_exist()
    
    results = {"created": [], "skipped": [], "errors": []}
    
    files_to_init = [
        (USER_PREFS_FILE, USER_PREFS_TEMPLATE),
        (WISHLIST_FILE, WISHLIST_TEMPLATE)
    ]
    
    for target_path, template_path in files_to_init:
        if target_path.exists():
            results["skipped"].append(str(target_path.name))
            logging.debug(f"initialize_data_files: skipped {target_path.name} (already exists)")
            continue

        if not template_path.exists():
            error_msg = f"Template not found: {template_path.name}"
            results["errors"].append(error_msg)
            logging.error(f"initialize_data_files: {error_msg}")
            continue
        
        try:
            # Копируем шаблон в целевую папку
            shutil.copy2(template_path, target_path)
            results["created"].append(str(target_path.name))
            logging.info(f"initialize_data_files: initialized {target_path.name}")
        except Exception as e:
            error_msg = f"{target_path.name}: {str(e)}"
            results["errors"].append(error_msg)
            logging.error(f"initialize_data_files: error initializing {target_path.name}: {e}")
    
    return results


def get_current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

# Инициализация папок при импорте
ensure_dirs_exist()
logging.debug("tools.base: module initialized")