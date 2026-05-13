---
name: wishlist_priority
description: Формальные правила расчёта приоритета (high/medium/low) для записи в вишлист
triggers: ["приоритет", "важность", "добавить в вишлист", "сохранить на потом"]
agent: wishlist
---

# Навык: Расчёт приоритета вишлиста

## Входные данные
- user_prefs: budget, preferred_brands, avoided_brands, feature_priority, min_rating
- specs товара: price, brand, rating, характеристики

## Алгоритм расчёта

### Шаг 1: Проверка на "low"
Присвоить priority="low", если выполняется **хотя бы одно**:
- Товар из avoided_brands
- price > budget * 1.2 (превышение бюджета >20%) И budget указан
- rating < min_rating И min_rating указан

### Шаг 2: Проверка на "high"
Присвоить priority="high", если выполняются **все**:
- Товар из preferred_brands ИЛИ brand совпадает с топ-1 в feature_priority
- price <= budget ИЛИ budget не указан
- rating >= min_rating ИЛИ min_rating не указан

### Шаг 3: По умолчанию
Во всех остальных случаях: priority="medium"

## Генерация notes
- Для high: "Соответствует вашим предпочтениям: {конкретная причина}"
- Для medium: "Сбалансированный вариант по соотношению цена/качество"
- Для low: "Требует дополнительного рассмотрения: {причина}"

## Примеры
| Условия | priority | notes |
|---------|----------|-------|
| preferred_brands=["Apple"], товар=iPhone, budget=80000, price=79990 | high | "Соответствует предпочитаемому бренду и бюджету" |
| avoided_brands=["Huawei"], товар=Huawei P50 | low | "Относится к избегаемому бренду" |
| budget=30000, price=45000 (превышение 50%) | low | "Превышает бюджет на 50%" |
| Нет предпочтений, товар с рейтингом 4.5 | medium | "Сбалансированный вариант по соотношению цена/качество" |