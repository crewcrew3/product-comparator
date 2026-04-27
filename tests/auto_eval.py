import ollama
import json
import re
import pandas as pd
import time
import requests

MODELS = ["gemma4:e2b", "qwen2.5:3b", "qwen3.5:2b", "gemma3:4b"] #"gemma4:e2b", "qwen2.5:3b", "qwen3.5:2b", "gemma3:4b"
RUNS_PER_PROMPT = 2
TEMPERATURE = 0.2
MAX_TOKENS = 10

TESTS = [
    # FORMAT
    {"id": "F1", "criterion": "Format", 
     "prompt": "Верни СТРОГО JSON без пояснений и без форматирования: {\"intent\": \"compare\", \"products\": [\"A\", \"B\"]}. Запрос: сравни iPhone и Pixel",
     "check": "json", "strict": True},
     
    {"id": "F2", "criterion": "Format", 
     "prompt": "Верни СТРОГО JSON без пояснений и без форматирования: {\"status\": \"success\", \"count\": 2}. Запрос: найдено два ноутбука",
     "check": "json", "strict": True},

    # HALLUCINATION 
    {"id": "H1", "criterion": "Hallucination", 
     "prompt": "Используй ТОЛЬКО данные ниже. Если параметра нет — пиши 'нет данных'. Данные: Экран 14 дюймов. Вопрос: какая частота процессора?",
     "check": "keyword", "keywords": ["нет данных", "не указано", "неизвестно"]},
     
    {"id": "H2", "criterion": "Hallucination", 
     "prompt": "Используй ТОЛЬКО данные ниже. Если параметра нет — пиши 'нет данных'. Данные: ОЗУ 16 ГБ, SSD 512 ГБ. Вопрос: какая видеокарта установлена?",
     "check": "keyword", "keywords": ["нет данных", "не указано", "неизвестно"]},

    # INSTRUCTION
    {"id": "I1", "criterion": "Instruction", 
     "prompt": "Ты не должен объяснять, рассуждать или добавлять вводные слова. Верни только число. Сколько будет 12 умножить на 4?",
     "check": "keyword", "keywords": ["48"], "strict": True, "max_words": 1},
     
    {"id": "I2", "criterion": "Instruction", 
     "prompt": "Ты не должен добавлять пояснений. Верни только название бренда. Данные: Samsung Galaxy S24 Ultra. Бренд:",
     "check": "keyword", "keywords": ["Samsung"], "strict": True, "max_words": 1},

    # LOGIC
    {"id": "L1", "criterion": "Logic", 
     "prompt": "Примени правило: если цена < 50000 -> 'Выгодно', иначе 'Дорого'. Товар: 48500 руб. Верни только одно слово.",
     "check": "keyword", "keywords": ["Выгодно"], "strict": True, "max_words": 1},
     
    {"id": "L2", "criterion": "Logic", 
     "prompt": "Примени правило: если рейтинг >= 4.5 -> 'Рекомендуем', иначе 'Нежелательно'. Рейтинг товара: 4.8. Верни только одно слово.",
     "check": "keyword", "keywords": ["Рекомендуем"], "strict": True, "max_words": 1},

    # CLASSIFICATION 
    {"id": "C1", "criterion": "Classification", 
     "prompt": "Определи намерение: compare, wishlist, none. Запрос: 'Сохрани этот монитор в список желаний'. Ответ: одно слово.",
     "check": "keyword", "keywords": ["wishlist"], "strict": True, "max_words": 1},
     
    {"id": "C2", "criterion": "Classification", 
     "prompt": "Определи намерение: compare, wishlist, none. Запрос: 'Какой сегодня прогноз погоды в Москве?'. Ответ: одно слово.",
     "check": "keyword", "keywords": ["none"], "strict": True, "max_words": 1},

    # EXPLAINABILITY
    {"id": "E1", "criterion": "Explainability", 
     "prompt": "Данные: А: 60к, 40Wh. Б: 45к, 35Wh. Пользователь хочет сэкономить. Верни СТРОГО JSON без форматирования: {\"choice\": \"A\" или \"B\", \"reason\": \"1 предложение\"}",
     "check": "structured_logic", "expected_choice": "B", "strict": True},
     
    {"id": "E2", "criterion": "Explainability", 
     "prompt": "Данные: Ноутбук X: 16ГБ ОЗУ, цена 70к. Ноутбук Y: 8ГБ ОЗУ, цена 40к. Пользователю нужна максимальная производительность для игр. Верни СТРОГО JSON без форматирования: {\"choice\": \"X\" или \"Y\", \"reason\": \"1 предложение\"}",
     "check": "structured_logic", "expected_choice": "X", "strict": True},
]

# Извлекает первый валидный JSON-объект из ответа
def clean_json(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    return match.group(0) if match else text

def check_response(text, test):
    is_strict = test.get("strict", False)
    # text.strip() удаляет все пробелы, табуляции и переносы строк ТОЛЬКО в начале и в конце строки. 
    stripped = text.strip()
    if test["check"] == "json":
        try:
            json.loads(clean_json(text))
            if is_strict:
                # тест прошел если ответ это строго джисон без воды
                return stripped.startswith('{') and stripped.endswith('}')
            return True
        except: return False
    elif test["check"] == "keyword":
        has_kw = any(kw.lower() in stripped.lower() for kw in test["keywords"])
        if is_strict:
            # тест прошел если ответ состоит из ровно max_words штук слов
            max_w = test.get("max_words", 3)
            return has_kw and len(stripped.split()) <= max_w
        return has_kw
    elif test["check"] == "structured_logic":
        try:
            data = json.loads(clean_json(text))
            model_choice = data.get("choice", "").strip().upper()
            expected = test["expected_choice"].upper()
            is_correct = model_choice == expected
            has_reason = len(data.get("reason", "").strip()) > 9
            
            if is_strict:
                return stripped.startswith('{') and stripped.endswith('}') and is_correct and has_reason
            return is_correct and has_reason
        except:
            return False
    return False


results = []

for model in MODELS:
    print(f"\n Тестируем модель: {model}")

    # 1 запрос, который не идёт в статистику, загружает модель в RAM
    try:
        print("\n Прогрев модели...")
        ollama.chat(
            model=model,
            messages=[{"role": "user", "content": "ok"}],
            options={"temperature": TEMPERATURE, "num_predict": MAX_TOKENS}, # ставим ограничение в колво токенов чтобы запрос быстро прошел и не грузил
            stream=False
        )
        print("\n Закончили прогрев")
    except: pass # игнорируем ошибку

    for test in TESTS:
        for run in range(1, RUNS_PER_PROMPT + 1):
            print(f"   {test['criterion']} ({test['id']}) | Запуск {run}/{RUNS_PER_PROMPT}...", end="")
            try:
                start = time.time()
                
                # Прямой запрос к Ollama API. timeout=30 работает железобетонно.
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": test["prompt"]}],
                    "options": {"temperature": TEMPERATURE},
                    "stream": False
                }
                response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=30)
                response.raise_for_status()
                ollama_data = response.json()
                
                duration = time.time() - start
                raw_text = ollama_data["message"]["content"].strip()
                print("\nОтвет LLM: " + raw_text)
                passed = check_response(raw_text, test)
                
                results.append({
                    "Model": model,
                    "Criterion": test["criterion"],
                    "Test_ID": test["id"],
                    "Run": run,
                    "Passed": passed,
                    "Duration_sec": round(duration, 2),
                    "Response": raw_text.replace("\n", " | ")
                })
                print("[PASSED]" if passed else "[FAILED]")
                
            except requests.exceptions.Timeout:
                print(f" ⏱️ (модель не ответила за 30 сек)")
                results.append({
                    "Model": model, "Criterion": test["criterion"], "Test_ID": test["id"],
                    "Run": run, "Passed": False, "Duration_sec": 30.0, "Response": "TimeoutError"
                })
            except Exception as e:
                print(f" Ошибка: {e}")
                results.append({
                    "Model": model, "Criterion": test["criterion"], "Test_ID": test["id"],
                    "Run": run, "Passed": False, "Duration_sec": 0.0, "Response": f"Error: {e}"
                })
            time.sleep(0.5) # на всякий случай чтобы компуктер отдохнул
    # Принудительно выгружаем модель перед переходом к следующей
    print(f" Выгружаем {model} из памяти...")
    try:
        ollama.chat(
            model=model, messages=[{"role": "user", "num_predict": MAX_TOKENS, "content": "_"}],
            keep_alive="0", 
            stream=False
        )
    except: pass
    time.sleep(2)  # Даём ОС время корректно освободить RAM/VRAM
    print(f" Выгрузили {model} из памяти")


df = pd.DataFrame(results)
# Сохраняем результаты (1 строка = 1 запуск)
df.to_csv("eval_results.csv", index=False, encoding="utf-8-sig")

# Рассчитываем агрегированные метрики по каждой модели
avg_success = (df.groupby("Model")["Passed"].mean() * 100).round(1)
avg_time = df[df["Passed"] == True].groupby("Model")["Duration_sec"].mean().round(2)

# Объединяем в одну таблицу для консоли и CSV
summary = pd.DataFrame({
    "Model": avg_success.index,
    "Avg_Success_%": avg_success.values,
    "Avg_Time_sec": avg_time.reindex(avg_success.index).fillna(0.0).values
})

# Выводим единую таблицу в консоль
print("\n" + "="*55)
print(" СВОДНАЯ СТАТИСТИКА (Модель | Успех % | Время с)")
print("="*55)
print(summary.to_string(index=False))
print("="*55)

# Дописываем усредненные строки в тот же eval_results.csv
summary_rows = pd.DataFrame({
    "Model": summary["Model"],
    "Criterion": ["SUMMARY"] * len(summary),
    "Test_ID": ["AVG"] * len(summary),
    "Run": ["ALL"] * len(summary),
    "Passed": summary["Avg_Success_%"] / 100,
    "Duration_sec": summary["Avg_Time_sec"],
    "Response": [f"Success:{s}%, Time:{t}s" for s, t in zip(summary["Avg_Success_%"], summary["Avg_Time_sec"])]
})
summary_rows = summary_rows[df.columns]
summary_rows.to_csv("eval_results.csv", mode='a', header=False, index=False, encoding="utf-8-sig")