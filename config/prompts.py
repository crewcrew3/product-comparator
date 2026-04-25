import yaml
from pathlib import Path
from typing import Dict, Any

PROMPTS_FILE = Path(__file__).parent / "prompts.yaml"


def load_prompts() -> Dict[str, Any]:
    """
    Загружает промпты из prompts.yaml.
    
    Returns:
        Словарь вида {"router": {...}, "comparator": {...}, ...}
    """
    try:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: Prompts file not found: {PROMPTS_FILE}")
        return {}
    except yaml.YAMLError as e:
        print(f"Warning: YAML parse error: {e}")
        return {}