"""
Точка входа в приложение.
Инициализирует файлы данных, выводит приветствие и запускает цикл взаимодействия с графом.
"""

import os
import time
from graph import app
from tools.base import initialize_data_files
from config.prompts import load_prompts

import logging
from pathlib import Path

# Создаём папку для логов
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

_langfuse = None

def get_langfuse_client():
    """Создаёт клиент Langfuse при первом вызове."""
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    
    # Загружаем .env
    from dotenv import load_dotenv
    load_dotenv()
    
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    
    if not pk or not sk:
        return None
    
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(public_key=pk, secret_key=sk, host=host)
        logging.info("Langfuse client initialized")
        return _langfuse
    except Exception as e:
        logging.warning(f"Langfuse init failed: {e}")
        return None

def main():
    print("Инициализация системы...")
    logging.info("Initialization of the system...")
    init_result = initialize_data_files()
    for err in init_result.get("errors", []):
        print(f"Ошибка инициализации: {err}")
        logging.error(f"Initialization error: {err}")
    
    prompts = load_prompts()
    welcome_text = prompts.get("system_messages", {}).get("welcome", "Product Comparison Assistant готов к работе.")
    print(welcome_text)
    print("=" * 50)
    
    lf = get_langfuse_client()

    # Простая сессия по времени (для группировки трейсов)
    session_id = f"cli-{int(time.time())}"

    while True:
        try:
            user_input = input("\nВведите запрос (или 'exit' для выхода): ").strip()
            
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "выход"):
                print("Завершение работы.")
                logging.info("Shutdown at the user's request")
                break

            start = time.time()
            
            # Создаём трейс, если клиент подключен
            trace = None
            if lf:
                trace = lf.trace(
                    name="product-comparator-query",
                    input=user_input,
                    session_id=session_id,
                    metadata={"source": "cli", "timestamp": time.time()}
                )
                logging.debug(f"Trace created: {trace.id if trace else None}")

            # Под-спан для Router (всегда выполняется первым)
            router_gen = None
            if trace and lf:
                router_gen = trace.generation(
                    name="Router",
                    model="qwen2.5:3b",
                    input=user_input,
                    metadata={"step": "routing", "agent": "router"}
                )
            
            # Запускаем граф
            result = app.invoke({"user_input": user_input})
            latency = round(time.time() - start, 3)
            logging.info(f"Graph invoke completed, latency: {latency}s")

            if router_gen:
                intent = result.get("parsed_intent", "unknown")
                product_count = len(result.get("product_names", []))
                
                # Проверяем результат работы агента
                router_error = result.get("router_error")
                
                if router_error:
                    # Агент вызывался, но завершился с ошибкой
                    router_gen.update(
                        output={"error": router_error},
                        level="ERROR",
                        metadata={
                            "product_count": product_count,
                            "parsed_params": result.get("parsed_params", {}),
                            "has_error": True,
                            "error_type": router_error
                        }
                    )
                else:
                    router_gen.update(
                        output={"intent": intent, "products": result.get("product_names")},
                        metadata={
                            "product_count": product_count,
                            "parsed_params": result.get("parsed_params", {}),
                            "has_error": False,
                            "error_type": "none"
                        }
                    )
                router_gen.end()
                logging.debug(f"Router span closed: intent={intent}, product_count={product_count}")

            # Под-спан для Comparator (если он сработал) 
            comp_gen = None
            intent = result.get("parsed_intent", "unknown")
            if trace and lf and intent in ("compare", "compare_and_export"):
                comp_gen = trace.generation(
                    name="Comparator",
                    model="gemma4:e2b",
                    input=f"Products: {result.get('product_names')}",
                    metadata={"step": "comparison", "agent": "comparator"}
                )
                
                # Проверяем результат работы агента
                comp_error = result.get("comparator_error")
                comp_data = result.get("comparison_data")
                
                if comp_error or comp_data is None:
                    # Агент вызывался, но завершился с ошибкой
                    comp_gen.update(
                        output={"error": comp_error or "unknown_failure"},
                        level="ERROR",
                        metadata={
                            "has_error": True,
                            "error_type": comp_error or "none"
                        }
                    )
                else:
                    # Успешное выполнение
                    comp_gen.update(
                        output={
                            "winner": comp_data.get("winner"),
                            "has_table": bool(comp_data.get("comparison_table"))
                        },
                        metadata={
                            "has_error": False,
                            "error_type": "none"
                        }
                    )
                comp_gen.end()
                logging.debug(f"Comparator span closed: winner={comp_data.get('winner') if comp_data else None}")
            
            wish_gen = None
            if trace and lf and intent == "wishlist":
                wish_gen = trace.generation(
                    name="WishlistAgent",
                    model="qwen2.5:3b",
                    input=f"Product: {result.get('product_names', [None])[0]}",
                    metadata={"step": "wishlist", "agent": "wishlist"}
                )
                
                # Проверяем результат работы агента
                wish_error = result.get("wishlist_error")
                wish_entry = result.get("wishlist_entry")
                
                if wish_error or wish_entry is None:
                    # Агент вызывался, но завершился с ошибкой
                    wish_gen.update(
                        output={"error": wish_error or "unknown_failure"},
                        level="ERROR",
                        metadata={
                            "has_error": True,
                            "error_type": wish_error or "none"
                        }
                    )
                else:
                    # Успешное выполнение
                    wish_gen.update(
                        output={"entry_created": True},
                        metadata={
                            "has_error": False,
                            "error_type": "none"
                        }
                    )
                wish_gen.end()
                logging.debug(f"WishlistAgent span closed: entry_created={bool(wish_entry)}")
                
            output = result.get("final_output", "Нет ответа")
            product_count = len(result.get("product_names", []))

            # Определяем наличие и тип ошибки (любой из агентов)
            error_type = (
                result.get("router_error") or 
                result.get("comparator_error") or 
                result.get("wishlist_error")
            )
            has_error = bool(error_type)
            
            if trace:
                trace.update(
                    output=output,
                    metadata={
                        "intent": intent,
                        "latency_sec": latency,
                        "has_error": has_error,
                        "error_type": error_type or "none",
                        "product_count": product_count,
                        "agents_triggered": [a for a in ["Router", "Comparator", "WishlistAgent"] 
                                           if (a == "Router") or 
                                              (a == "Comparator" and intent in ("compare", "compare_and_export")) or
                                              (a == "WishlistAgent" and intent == "wishlist")]
                    }
                )
                
                # Добавляем метрики как Scores
                trace.score(name="latency", value=latency, comment="End-to-end latency")
                trace.score(name="has_error", value=1 if has_error else 0, comment="Error flag")
                trace.score(name="product_count", value=product_count, comment="Extracted products")
                
                # Отправляем данные в Langfuse
                lf.flush()
                logging.info(f"Trace flushed to Langfuse: latency={latency}s, has_error={has_error}")
            
            # Показываем ответ
            print(f"\n{output}")
            print("=" * 50)
            logging.info(f"Response sent to user, length: {len(output)} chars")

        except KeyboardInterrupt:
            print("\nЗавершение работы.")
            logging.info("Shutdown on the KeyboardInterrupt signal")
            break
        except Exception as e:
            print(f"Ошибка: {e}")
            logging.error(f"Unhandled exception: {e}", exc_info=True)
            if 'trace' in locals() and trace and lf:
                trace.update(output={"error": str(e)}, level="ERROR")
                lf.flush()
                logging.info("Error trace flushed to Langfuse")


if __name__ == "__main__":
    logging.info("Application entry point")
    main()