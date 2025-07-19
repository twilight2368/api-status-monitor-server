FROM python:3.11-slim

WORKDIR /app

# Add this to Dockerfile for flask_app
RUN apt-get update && apt-get install -y default-mysql-client

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir cryptography==41.0.7 
RUN pip install --no-cache-dir gunicorn

COPY . .

# Make entrypoint script executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]

# 'server' is your entrypoint file; 'app' is the Flask instance inside it (imported from app package)
# CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "server:app"]
