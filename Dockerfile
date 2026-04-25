FROM python:3.11-slim

WORKDIR /app

# копирование зависимостей и их установка
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# копирование кода проекта (все по отдельности для прозрачности)
COPY agents/ ./agents/
COPY config/ ./config/
COPY knowledge/ ./knowledge/
COPY tests/ ./tests/
COPY tools/ ./tools/
COPY main.py .
COPY graph.py .

# Создание папок для пользовательских данных (страховка, будут смонтированы как volumes)
RUN mkdir -p data/reports

# Копируем шаблоны пользовательских данных в отдельную папку внутри образа
COPY data/*.example /app/templates/


ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Команда запуска приложения
CMD ["python", "main.py"]