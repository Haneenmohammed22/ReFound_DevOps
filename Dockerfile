FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt requirements-nlp.txt ./
RUN pip install -r requirements.txt gunicorn

ARG WITH_NLP=0
RUN if [ "$WITH_NLP" = "1" ]; then pip install -r requirements-nlp.txt; fi

COPY . .

RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/instance/uploads \
    && chown -R appuser:appuser /app
USER 10001

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import socket; socket.create_connection(('127.0.0.1',5000),3)" || exit 1

CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "--threads", "4", "--timeout", "60", "app:app"]