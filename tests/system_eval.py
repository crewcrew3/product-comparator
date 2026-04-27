"""
Оценка работы мультиагентной системы.

Запускается из корня проекта:
    python -m tests.system_eval

Результаты сохраняются в tests/system_eval_results.csv
"""

import csv
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Импортируем скомпилированный граф
from graph import app

# Пути к файлам
DATASET_PATH = Path(__file__).parent / "system_dataset.csv"
RESULTS_PATH = Path(__file__).parent / "system_eval_results.csv"


def is_expected_error(error_type: Optional[str], error_code: Optional[str]) -> bool:
    """
    Определяет, является ли ошибка ожидаемой валидацией, а не системным сбоем.
    
    Ожидаемые ошибки — это корректные ответы системы на некорректный ввод пользователя.
    Они НЕ считаются сбоями при расчёте метрик качества.
    """
    expected_codes = {
        "invalid_product_count",           # Не 2 товара для сравнения / не 1 для вишлиста
        "invalid_wishlist_product_count",  # Неверное количество для wishlist
        "product_not_found",               # Товар отсутствует в базе знаний
        "unrecognized_intent",             # Нераспознанное намерение
        "empty_input",                     # Пустой запрос
        "unrecognized_user_prefs_param",   # Недопустимый параметр настроек
        "incompatible_products",           # Попытка сравнить несовместимые категории
        "already_in_wishlist",             # Дубликат в вишлисте
        "prefs_update_failed",             # Ошибка валидации параметров предпочтений
    }
    return error_code in expected_codes if error_code else False


def load_dataset(filepath: Path) -> List[Dict[str, Any]]:
    with open(filepath, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_single_eval(test: Dict[str, Any]) -> Dict[str, Any]:
    """
    Запускает один тестовый запрос через граф и возвращает метрики.
    """
    user_input = test["user_input"]
    expected_intent = test["expected_intent"]
    expected_count = int(test.get("expected_products_count", 0))
    
    start_time = time.perf_counter()
    state = None
    
    try:
        # Запускаем граф с начальным состоянием
        state = app.invoke({"user_input": user_input})
        latency = time.perf_counter() - start_time
        
        # Извлекаем результаты
        actual_intent = state.get("parsed_intent")
        product_names = state.get("product_names", [])
        actual_count = len(product_names) if isinstance(product_names, list) else 0
        
        # Определяем наличие и тип ошибок
        router_err = state.get("router_error")
        comparator_err = state.get("comparator_error")
        wishlist_err = state.get("wishlist_error")
        
        has_any_error = bool(router_err or comparator_err or wishlist_err)
        
        # Различаем ожидаемую валидацию и системный сбой
        is_expected = (
            is_expected_error("router", router_err) or
            is_expected_error("comparator", comparator_err) or
            is_expected_error("wishlist", wishlist_err)
        )
        is_system_failure = has_any_error and not is_expected
        
        # Задача успешна, если есть финальный ответ И нет системных сбоев
        task_success = bool(state.get("final_output")) and not is_system_failure
        
        # Intent считается совпавшим, если он соответствует ожидаемому
        # (даже если при этом была ожидаемая ошибка валидации)
        intent_match = actual_intent == expected_intent
        
        return {
            "user_input": user_input,
            "expected_intent": expected_intent,
            "actual_intent": actual_intent,
            "intent_match": intent_match,
            "expected_products": expected_count,
            "actual_products": actual_count,
            "count_match": actual_count == expected_count if expected_count > 0 else True,
            "has_any_error": has_any_error,
            "is_expected_error": is_expected,
            "is_system_failure": is_system_failure,
            "error_type": "router" if router_err else "comparator" if comparator_err else "wishlist" if wishlist_err else None,
            "error_code": router_err or comparator_err or wishlist_err,
            "task_success": task_success,
            "final_output_present": bool(state.get("final_output")),
            "latency_sec": round(latency, 3),
            "status": "OK"
        }
        
    except Exception as e:
        latency = time.perf_counter() - start_time
        return {
            "user_input": user_input,
            "expected_intent": expected_intent,
            "actual_intent": "crash",
            "intent_match": False,
            "expected_products": expected_count,
            "actual_products": 0,
            "count_match": False,
            "has_any_error": True,
            "is_expected_error": False,
            "is_system_failure": True,
            "error_type": "exception",
            "error_code": str(e)[:50],
            "task_success": False,
            "final_output_present": False,
            "latency_sec": round(latency, 3),
            "status": f"EXCEPTION: {str(e)[:100]}"
        }


def calculate_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Рассчитывает агрегированные метрики."""
    total = len(results)
    if total == 0:
        return {}
    
    intent_matches = sum(1 for r in results if r["intent_match"])
    task_successes = sum(1 for r in results if r["task_success"])
    system_failures = sum(1 for r in results if r["is_system_failure"])
    valid_responses = sum(1 for r in results if r["status"] == "OK")
    
    valid_latencies = [r["latency_sec"] for r in results if r["latency_sec"] > 0]
    avg_latency = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 0
    
    return {
        "total_tests": total,
        "intent_accuracy_pct": round(intent_matches / total * 100, 1),
        "task_success_rate_pct": round(task_successes / total * 100, 1),
        "system_failure_rate_pct": round(system_failures / total * 100, 1),  # Только эта метрика!
        "valid_responses_pct": round(valid_responses / total * 100, 1),
        "avg_latency_sec": round(avg_latency, 3),
        "tests_with_output": sum(1 for r in results if r["final_output_present"])
    }


def print_summary(summary: Dict[str, Any], results: List[Dict[str, Any]]):
    """Выводит сводку в консоль."""
    print(" Результаты\n")
    print(f"Всего тестов:              {summary['total_tests']}")
    print(f"Intent Accuracy:           {summary['intent_accuracy_pct']}%")
    print(f"Task Success Rate:         {summary['task_success_rate_pct']}%")
    print(f"System Failure Rate:       {summary['system_failure_rate_pct']}%")
    print(f"Valid Responses:           {summary['valid_responses_pct']}%")
    print(f"Avg Latency:               {summary['avg_latency_sec']} с")
    print(f"С выводом ответа:          {summary['tests_with_output']}/{summary['total_tests']}")
    
    # Показываем только настоящие сбои (не валидацию)
    failures = [r for r in results if r["is_system_failure"]]
    if failures:
        print(f"\n Системные сбои ({len(failures)}):")
        for r in failures:
            print(f"  • {r['user_input'][:50]}...")
            print(f"    Ошибка: {r['error_type']} / {r['error_code']}")
            print(f"    Статус: {r['status']}")
        print()
    else:
        print("\n Системных сбоев не обнаружено")


def save_results(results: List[Dict[str, Any]], summary: Dict[str, Any], filepath: Path):
    """Сохраняет результаты и сводку в CSV."""
    # Сохраняем детальные результаты
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        fieldnames = results[0].keys() if results else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    # Дописываем сводку в конец файла
    with open(filepath, "a", encoding="utf-8", newline="") as f:
        f.write("\n# SUMMARY\n")
        for key, value in summary.items():
            f.write(f"{key},{value}\n")


def main():
    print("Запуск системных эвалов...")
    print(f"Датасет: {DATASET_PATH}")
    print(f"Результаты: {RESULTS_PATH}\n")
    
    # Загружаем датасет
    if not DATASET_PATH.exists():
        print(f" Датасет не найден: {DATASET_PATH}")
        print("Создайте файл tests/system_dataset.csv")
        return
    
    dataset = load_dataset(DATASET_PATH)
    print(f"Загружено {len(dataset)} тестовых запросов.\n")
    
    # Запускаем эвалы
    results = []
    for i, test in enumerate(dataset, 1):
        print(f"[{i}/{len(dataset)}] {test['user_input'][:40]}...", end=" ")
        result = run_single_eval(test)
        results.append(result)
        status = "[PASSED]" if result["task_success"] else "[FAILED]"
        print(f"{status} {result['latency_sec']}с")
    
    # Считаем метрики
    summary = calculate_summary(results)
    
    # Выводим и сохраняем
    print_summary(summary, results)
    save_results(results, summary, RESULTS_PATH)
    
    print(f" Результаты сохранены в {RESULTS_PATH}")


if __name__ == "__main__":
    main()