FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY proxy_server.py .

EXPOSE 8443

CMD ["uvicorn", "proxy_server:app", "--host", "0.0.0.0", "--port", "8443", "--log-level", "info"]