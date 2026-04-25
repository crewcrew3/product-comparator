"""
Работа с базой знаний (knowledge/). Поиск товаров и характеристик.
"""

from typing import Dict, List, Optional, Any
from .base import KNOWLEDGE_DIR, load_markdown_file

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
        files_to_check = [KNOWLEDGE_DIR / f"{category.strip().lower()}.md"]
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
        for section in sections[1:]: # Пропускаем первый пустой
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
                products.append(line.strip()[3:].strip())
    return products


def format_specs_for_prompt(specs: Optional[Dict[str, Any]]) -> str:
    """
    Форматирует характеристики для вставки в промпт.

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
        lines.append(f"- {key}: {specs[key]}")
    return "\n".join(lines)