FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir cryptography==41.0.7 
RUN pip install --no-cache-dir gunicorn

COPY . .

EXPOSE 5000

ENV APP_RUNNING_GUNICORN=true

# 'server' is your entrypoint file; 'app' is the Flask instance inside it (imported from app package)
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "server:app"]
