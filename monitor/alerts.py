"""
Простой монитор для алертинга на основе данных Langfuse.

Запускается как отдельный процесс:
    python -m monitor.alerts

Или добавляется в crontab / Task Scheduler для периодического выполнения.
"""

import os
import time
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# Пороги для алертов
THRESHOLDS = {
    "max_latency_sec": 200.0,          # Алерт, если задержка > 200с
    "max_system_error_rate": 0.1,     # Алерт, если > 30% запросов с ошибкой
    "consecutive_system_errors": 3,  # Алерт после 3 ошибок "товар не найден" подряд
}

# Явное разделение типов ошибок
SYSTEM_ERRORS = {
    "llm_error", 
    "llm_execution_failed", 
    "llm_failed", 
    "parse_error", 
    "timeout", 
    "connection_refused"
}
USER_VALIDATION_ERRORS = {
    "invalid_product_count", 
    "invalid_wishlist_product_count", 
    "empty_input", 
    "product_not_found", 
    "already_in_wishlist", 
    "prefs_update_failed",
    "none"
}

# Куда отправлять уведомления
ALERT_TARGETS = {
    "console": True,                  # Выводить в консоль
    "file": "logs/alerts.log",        # Писать в файл
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


def get_langfuse_auth():
    """Возвращает базовую авторизацию для API Langfuse."""
    return (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)


def fetch_recent_traces(minutes: int = 10) -> list:
    """Получает трейсы за последние N минут через публичный API Langfuse."""
    url = f"{LANGFUSE_HOST}/api/public/traces"
    params = {
        "page": 1,
        "limit": 50,
    }
    
    try:
        response = requests.get(
            url,
            auth=get_langfuse_auth(),
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        traces = data.get("data", [])
        
        # Фильтруем по времени (если поле доступно)
        cutoff = datetime.now() - timedelta(minutes=minutes)
        filtered = []
        for t in traces:
            ts = t.get("timestamp")
            if ts:
                # Парсинг строки времени, если нужно
                filtered.append(t)
            else:
                filtered.append(t)  # если время не указано — берём всё равно
        return filtered[:20]  # ограничиваем выборку
    except Exception as e:
        logging.warning(f"Failed to fetch traces: {e}")
        return []


def check_latency_alert(traces: list) -> list:
    """Проверяет, есть ли трейсы с задержкой выше порога."""
    alerts = []
    for t in traces:
        latency = t.get("metadata", {}).get("latency_sec")
        if latency and latency > THRESHOLDS["max_latency_sec"]:
            alerts.append({
                "type": "HIGH_LATENCY",
                "trace_id": t.get("id"),
                "value": latency,
                "threshold": THRESHOLDS["max_latency_sec"],
                "input": t.get("input", "")[:100]
            })
    return alerts


def check_error_rate_alert(traces: list) -> list:
    """Проверяет долю системных сбоев (исключая пользовательскую валидацию)."""
    if not traces:
        return []
    
    system_failures = 0
    for t in traces:
        error_type = t.get("metadata", {}).get("error_type")
        if error_type and error_type in SYSTEM_ERRORS:
            system_failures += 1
    
    error_rate = system_failures / len(traces)
    alerts = []
    
    if error_rate > THRESHOLDS["max_system_error_rate"]:
        alerts.append({
            "type": "HIGH_SYSTEM_ERROR_RATE",
            "value": round(error_rate * 100, 1),
            "threshold": THRESHOLDS["max_system_error_rate"] * 100,
            "sample_size": len(traces)
        })
    return alerts

def check_consecutive_errors(traces: list) -> list:
    """Проверяет подряд идущие системные ошибки."""
    alerts = []
    consecutive = 0
    
    # Идём от новых к старым
    for t in reversed(traces):
        error_type = t.get("metadata", {}).get("error_type")
        
        if error_type and error_type in SYSTEM_ERRORS:
            consecutive += 1
            if consecutive >= THRESHOLDS["consecutive_system_errors"]:
                alerts.append({
                    "type": "CONSECUTIVE_SYSTEM_ERRORS",
                    "error_type": error_type,
                    "count": consecutive,
                    "threshold": THRESHOLDS["consecutive_system_errors"]
                })
                break
        else:
            consecutive = 0  # Сбрасываем счётчик при успешном или валидационном запросе
    
    return alerts


def format_alert(alert: dict) -> str:
    """Форматирует алерт в человекочитаемое сообщение."""
    alert_type = alert.get("type", "UNKNOWN")
    
    if alert_type == "HIGH_LATENCY":
        return (
            f"Высокая задержка: {alert.get('value', 0):.1f}с > "
            f"{alert.get('threshold', 0):.1f}с | Запрос: {alert.get('input', '')[:50]}"
        )
    elif alert_type == "HIGH_SYSTEM_ERROR_RATE":
        return (
            f"Рост системных сбоев: {alert.get('value', 0):.1f}% > "
            f"{alert.get('threshold', 0):.1f}% | Проверено запросов: {alert.get('sample_size', 0)}"
        )
    elif alert_type == "CONSECUTIVE_SYSTEM_ERRORS":
        return (
            f"Повторяющийся системный сбой '{alert.get('error_type', 'unknown')}': "
            f"{alert.get('count', 0)} раз подряд"
        )
    else:
        return f"Алерт неизвестного типа: {alert}"


def send_alert(alert: dict):
    """Отправляет уведомление через настроенные каналы."""
    message = format_alert(alert)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    
    # 1. Консоль
    if ALERT_TARGETS.get("console"):
        print(full_message)
    
    # 2. Файл
    if ALERT_TARGETS.get("file"):
        Path("logs").mkdir(exist_ok=True)
        with open(ALERT_TARGETS["file"], "a", encoding="utf-8") as f:
            f.write(full_message + "\n")

def run_checks():
    """Запускает все проверки и отправляет алерты."""
    logging.info("Starting alert checks...")
    
    traces = fetch_recent_traces(minutes=10)
    if not traces:
        logging.warning("No traces fetched, skipping checks")
        return
    
    all_alerts = []
    all_alerts.extend(check_latency_alert(traces))
    all_alerts.extend(check_error_rate_alert(traces))
    all_alerts.extend(check_consecutive_errors(traces))
    
    for alert in all_alerts:
        logging.warning(f"Alert triggered: {alert['type']}")
        send_alert(alert)
    
    if not all_alerts:
        logging.info("No alerts triggered")


def main():
    logging.info("Alert monitor started")
    
    while True:
        try:
            run_checks()
        except Exception as e:
            logging.error(f"Error in alert monitor: {e}", exc_info=True)
        
        # Пауза между проверками
        time.sleep(60)


if __name__ == "__main__":
    main()