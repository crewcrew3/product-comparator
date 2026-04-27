"""
Навык: Управление вишлистом.
Агент проверяет дубликаты, форматирует данные и добавляет товар в файл.
"""
from tools.wishlist import load_wishlist, check_wishlist_duplicate, add_to_wishlist
from config.prompts import load_prompts

WISHLIST_MANAGEMENT_SKILL = {
    "name": "WishlistManagement",
    "description": "Добавляет товар в список желаемого, проверяет дубликаты и сохраняет запись в формате Markdown.",
    "required_tools": [
        "load_wishlist",
        "check_wishlist_duplicate",
        "add_to_wishlist"
    ],
    "prompt_source": "wishlist",
    "input_schema": {
        "product_names": ["str"]
    },
    "output_schema": {
        "wishlist_entry": "dict | None",
        "error": "str | None"
    },
    "usage_notes": "Принимает ровно 1 товар. Если товар уже в вишлисте, возвращает ошибку без изменения файла."
}