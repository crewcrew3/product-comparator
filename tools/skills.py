"""
Загрузчик скиллов (доменных правил) из Markdown-файлов.
"""

import logging
from pathlib import Path
from typing import List, Optional

SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _parse_skill_metadata(content: str) -> dict:
    """Извлекает метаданные из YAML-блока в начале файла."""
    metadata = {}
    lines = content.split("\n")
    
    if not lines or lines[0].strip() != "---":
        return metadata
    
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    
    if end_idx is None:
        return metadata
    
    for line in lines[1:end_idx]:
        if ":" in line and not line.strip().startswith("#"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
            elif value.lower() in ("true", "false"):
                value = value.lower() == "true"
            metadata[key] = value
    
    return metadata


def load_skills_context(trigger_keywords: Optional[List[str]] = None, 
                        agent_name: Optional[str] = None) -> str:
    """
    Загружает релевантные скиллы на основе триггеров и имени агента.
    
    Args:
        trigger_keywords: Список ключевых слов для фильтрации скиллов
        agent_name: Имя агента (comparator, wishlist, router) для фильтрации
    
    Returns:
        Строка с контентом подходящих скиллов или пустая строка
    """
    if not SKILLS_DIR.exists():
        logging.debug("skills directory not found")
        return ""
    
    if trigger_keywords:
        trigger_keywords = [kw.lower() for kw in trigger_keywords]
    
    skills_content = []
    
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            metadata = _parse_skill_metadata(content)
            
            if agent_name and metadata.get("agent") != agent_name:
                continue
            
            if trigger_keywords:
                skill_triggers = metadata.get("triggers", [])
                if isinstance(skill_triggers, str):
                    skill_triggers = [skill_triggers]
                if not any(trig.lower() in trigger_keywords for trig in skill_triggers):
                    continue
            
            lines = content.split("\n")
            start_idx = 0
            if lines and lines[0].strip() == "---":
                for i, line in enumerate(lines[1:], start=1):
                    if line.strip() == "---":
                        start_idx = i + 1
                        break
            
            skill_body = "\n".join(lines[start_idx:]).strip()
            if skill_body:
                skills_content.append(f"### {metadata.get('name', md_file.stem).upper()}\n{skill_body}")
                
        except Exception as e:
            logging.warning(f"Failed to load skill {md_file.name}: {e}")
    
    if skills_content:
        logging.debug(f"Loaded {len(skills_content)} skill(s) for triggers={trigger_keywords}, agent={agent_name}")
        return "\n\n".join(skills_content)
    return ""