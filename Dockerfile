FROM python:3.11-slim AS base
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip

FROM base AS deps
RUN pip install --no-cache-dir -r /app/requirements.txt

FROM base AS final
COPY . /app
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "dv_admin_automator.ui.web.server:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
