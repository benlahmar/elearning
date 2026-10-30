# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
ARG INSTALL_SEMANTIC=true
ENV HF_HOME=/app/model-cache
COPY requirements*.txt ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    if [ "$INSTALL_SEMANTIC" = "true" ]; then \
      pip install --no-cache-dir torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir -r requirements-semantic.txt; fi
COPY app ./app
COPY migrations ./migrations
RUN useradd --create-home learner && mkdir -p /app/model-cache && chown -R learner:learner /app
USER learner
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
