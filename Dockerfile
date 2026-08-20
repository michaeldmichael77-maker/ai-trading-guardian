FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir --upgrade pip setuptools
RUN pip install --no-cache-dir fastapi uvicorn[standard] pandas pandas-ta alpaca-trade-api websockets==10.4 python-multipart
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["python", "trading_bot/api.py"]
