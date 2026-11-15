FROM python:3.12-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG SERVICE_PATH
WORKDIR /srv
COPY shared /tmp/shared
COPY ${SERVICE_PATH}/requirements.txt ${SERVICE_PATH}/constraints.txt ./
RUN pip install --no-cache-dir /tmp/shared -r requirements.txt
RUN pip uninstall -y wheel setuptools pip && rm -rf /usr/local/lib/python3.12/ensurepip
COPY ${SERVICE_PATH}/app app
COPY ${SERVICE_PATH}/alembic alembic
COPY ${SERVICE_PATH}/alembic.ini .
USER 10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
