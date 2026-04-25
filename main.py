"""
main.py
Точка входа в приложение.
Инициализирует файлы данных, выводит приветствие и запускает цикл взаимодействия с графом.
"""

import sys
from graph import app
from tools.base import initialize_data_files
from config.prompts import load_prompts


def main():
    # 1. Инициализация файлов данных из шаблонов
    print("Инициализация системы...")
    init_result = initialize_data_files()
    for err in init_result.get("errors", []):
        print(f"Ошибка инициализации: {err}")
    
    # 2. Загрузка и вывод приветственного сообщения
    prompts = load_prompts()
    welcome_text = prompts.get("system_messages", {}).get("welcome", "Product Comparison Assistant готов к работе.")
    print(welcome_text)
    print("=" * 50)

    # 3. Основной цикл обработки запросов
    while True:
        try:
            user_input = input("\nВведите запрос (или 'exit' для выхода): ").strip()
            
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "выход"):
                print("Завершение работы.")
                break

            # 4. Формирование начального состояния и запуск графа
            initial_state = {"user_input": user_input}
            
            # app.invoke() последовательно проходит все узлы графа и возвращает финальное состояние
            final_state = app.invoke(initial_state)
            
            # 5. Вывод результата пользователю
            output = final_state.get("final_output", "Система не вернула ответ.")
            print("\n" + output)
            print("=" * 50)

        except KeyboardInterrupt:
            print("\nЗавершение работы.")
            break
        except Exception as e:
            # В production здесь должен быть logger.error(e)
            print(f"Критическая ошибка выполнения: {e}")


if __name__ == "__main__":
    main()