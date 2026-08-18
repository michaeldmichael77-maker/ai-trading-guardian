# Use Python 3.12 for latest library support
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the entire project
COPY . /app

# Upgrade pip and install all professional dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pandas \
    pandas-ta \
    alpaca-trade-api \
    websockets==10.4 \
    python-multipart

# Tell Python where the modules are
ENV PYTHONPATH=/app
EXPOSE 8000

# Start the Master AI Kernel
CMD ["python", "-m", "trading_bot.api"]
