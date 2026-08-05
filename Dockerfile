FROM public.ecr.aws/docker/library/python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN groupadd --system --gid 10001 docsmind \
    && useradd --system --uid 10001 --gid docsmind --home-dir /app docsmind

COPY requirements-serving.txt pyproject.toml ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-serving.txt

COPY docsmind ./docsmind
RUN python -m pip install --no-deps . \
    && chown -R docsmind:docsmind /app

USER docsmind
EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn docsmind.serving.app:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers"]
