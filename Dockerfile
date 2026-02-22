FROM python:3.11-slim

WORKDIR /app

# Встановлення залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду
COPY . .

# Не запускати від root
RUN adduser --disabled-password --gecos '' botuser
RUN chown -R botuser:botuser /app
USER botuser

# Порт для вебхука
EXPOSE 8080

CMD ["python", "main.py"]
