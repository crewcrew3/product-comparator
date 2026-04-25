"""
tools/wishlist.py
Управление списком желаний (wishlist.md).
"""

from typing import Dict, List, Any
from .base import WISHLIST_FILE, load_markdown_file, append_to_markdown_file, get_current_timestamp


def load_wishlist() -> List[Dict[str, Any]]:
    """Загружает вишлист из файла."""
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
    """
    if check_wishlist_duplicate(entry_data.get("name", "")):
        return {"success": False, "message": "Товар уже в вишлисте"}
    
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
    for key, value in specs.items():
        lines.append(f"  - {key}: {value}")
    if notes:
        lines.append(f"  - Заметка: {notes}")
    lines.append("")
    
    if append_to_markdown_file(WISHLIST_FILE, "\n".join(lines)):
        return {"success": True, "message": f"{name} добавлен в вишлист"}
    return {"success": False, "message": "Ошибка добавления"}


def remove_from_wishlist(product_name: str) -> Dict[str, Any]:
    wishlist = load_wishlist()
    search_name = product_name.strip().lower()
    
    # Ищем индекс для удаления
    for i, entry in enumerate(wishlist):
        entry_name = entry.get("name", entry.get("raw", "")).lower()
        if search_name in entry_name or entry_name in search_name:
            wishlist.pop(i)
            # Перезаписываем файл без удалённой записи
            try:
                with open(WISHLIST_FILE, "w", encoding="utf-8") as f:
                    f.write("# Wishlist\n\n")
                    for entry in wishlist:
                        f.write(f"- **{entry.get('name', entry.get('raw'))}**\n")
                        for k, v in entry.get("specs", {}).items():
                            f.write(f"  - {k}: {v}\n")
                        f.write("\n")
                return {"success": True, "message": f"{product_name} удалён"}
            except Exception as e:
                return {"success": False, "message": f"Ошибка удаления: {e}"}
    
    return {"success": False, "message": "Товар не найден"}