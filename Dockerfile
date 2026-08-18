# Dockerfile — the "recipe" Render uses to build and run the app.
FROM python:3.12-slim

# Don't buffer logs (so Render shows output in real time).
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install dependencies first (uses Docker's layer cache for faster rebuilds).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app.
COPY . .

# Show what actually got copied (helps diagnose path issues in the build log).
RUN echo "=== /app contents ===" && ls -la /app && \
    echo "=== /app/trading_bot contents ===" && ls -la /app/trading_bot || true

# Render provides the port via the PORT env var; main.py already honors it.
EXPOSE 8000

# Start the app. Try the module form; if the code is nested one level deeper
# (e.g. uploaded inside a TradingApp_Full/ folder), fall back to that path.
CMD ["sh", "-c", "python -m trading_bot.main || (cd TradingApp_Full && python -m trading_bot.main)"]
