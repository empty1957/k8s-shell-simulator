FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SESSIONS_DIR=/workspaces/sessions

WORKDIR /app

COPY scripts/install-tools.sh /tmp/install-tools.sh
RUN chmod +x /tmp/install-tools.sh && /tmp/install-tools.sh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x checks/*.sh scripts/*.sh && mkdir -p /workspaces/sessions

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
