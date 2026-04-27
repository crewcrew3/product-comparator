"""
Реестр навыков агента.
Позволяет загружать и документировать способности системы.
"""
from .product_comparison import PRODUCT_COMPARISON_SKILL
from .wishlist_management import WISHLIST_MANAGEMENT_SKILL
from .preference_setup import PREFERENCE_SETUP_SKILL

SKILL_REGISTRY = [
    PRODUCT_COMPARISON_SKILL,
    WISHLIST_MANAGEMENT_SKILL,
    PREFERENCE_SETUP_SKILL,
]

def list_skills() -> list:
    return SKILL_REGISTRY