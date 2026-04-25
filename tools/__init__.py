"""
tools/__init__.py
Публичный API модуля tools.
Позволяет импортировать функции напрямую: from tools import ... не указывая конкретный файл (wishlist.py, export.py и т.д.)
"""

# Относительные импорты (точка = текущая папка tools/)
from .base import (
    ensure_dirs_exist,
    initialize_data_files,
    get_current_timestamp,
    load_json_file,
    save_json_file,
    load_markdown_file,
    append_to_markdown_file
)
from .preferences import load_user_preferences, update_user_preferences
from .knowledge import load_product_specs, list_available_products, format_specs_for_prompt
from .wishlist import add_to_wishlist, remove_from_wishlist, check_wishlist_duplicate
from .export import export_report_to_file, export_report_as_markdown, export_report_as_csv

# Явно указываем, что считается публичным API
__all__ = [
    "ensure_dirs_exist", "initialize_data_files", "get_current_timestamp",
    "load_user_preferences", "update_user_preferences",
    "load_product_specs", "list_available_products", "format_specs_for_prompt",
    "add_to_wishlist", "remove_from_wishlist", "check_wishlist_duplicate",
    "export_report_to_file", "export_report_as_markdown", "export_report_as_csv"
]