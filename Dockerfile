# Use Python 3.12
FROM python:3.12-slim

# Set the working directory to /app
WORKDIR /app

# Copy all files from the current directory into /app in the container
COPY . /app

# Upgrade pip and install all required libraries
RUN pip install --no-cache-dir --upgrade pip setuptools
RUN pip install --no-cache-dir fastapi uvicorn[standard] pandas pandas-ta alpaca-trade-api websockets==10.4 python-multipart

# Crucial: Ensure Python knows where to find the 'trading_bot' module
ENV PYTHONPATH=/app

# Port configuration
EXPOSE 8000

# Start the application using the module path
CMD ["python", "-m", "trading_bot.api"]
