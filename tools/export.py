"""
tools/export.py
Генерация и сохранение отчетов (Markdown и CSV).
"""

import csv
from datetime import datetime
from typing import Dict, Any, Optional
from .base import REPORTS_DIR, ensure_dirs_exist


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
        return {"success": False, "filepath": None, "message": "Неверный формат данных для CSV."}
    
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


def export_report_to_file(table_data: Dict[str, Any], markdown_content: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Координатор экспорта: сохраняет отчёт в Markdown и CSV с одинаковым базовым именем.
    Делегирует работу специализированным функциям и агрегирует результат.
    """
    ensure_dirs_exist()
    if filename is None:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    md_result = export_report_as_markdown(markdown_content, filename=filename)
    csv_result = export_report_as_csv(table_data, filename=filename)
    
    files_created = []
    if md_result["success"]: files_created.append("md")
    if csv_result["success"]: files_created.append("csv")
    
    messages = []
    if md_result["success"]: messages.append(md_result["message"])
    if csv_result["success"]: messages.append(csv_result["message"])
    if not md_result["success"]: messages.append(f"[MD] {md_result['message']}")
    if not csv_result["success"]: messages.append(f"[CSV] {csv_result['message']}")
    
    return {
        "success": len(files_created) > 0, # Успех, если создан хотя бы один файл
        "files": {"markdown": md_result.get("filepath"), "csv": csv_result.get("filepath")},
        "message": "; ".join(messages)
    }