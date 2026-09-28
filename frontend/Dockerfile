ARG PYTHON_VERSION=3

# ────────── Build stage ──────────
FROM python:${PYTHON_VERSION} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.0 /uv /uvx /bin/

WORKDIR /geodesic_distance

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project --no-editable --no-dev


COPY pyproject.toml uv.lock .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

COPY main.py main.py

RUN set -eux; \
    rm -f /geodesic_distance/pyproject.toml /geodesic_distance/uv.lock || true; \
    rm -rf /root/.cache/pip /root/.cache/uv /tmp/pip-* || true; \
    find /geodesic_distance/.venv -type d -name "test" -prune -exec rm -rf {} + || true; \
    find /geodesic_distance/.venv -type d -name "tests" -prune -exec rm -rf {} + || true; \
    find /geodesic_distance/.venv -type d -name "__pycache__" -prune -exec rm -rf {} + || true; \
    find /geodesic_distance/.venv -type d -name "doc" -prune -exec rm -rf {} + || true; \
    find /geodesic_distance/.venv -type f -name "*.pyc" -delete || true; \
    true

# ────────── Runtime stage ──────────
FROM python:${PYTHON_VERSION}

COPY --from=builder /geodesic_distance/.venv /geodesic_distance/.venv
COPY --from=builder /geodesic_distance/main.py /geodesic_distance/main.py

WORKDIR /geodesic_distance
ENV PATH="/geodesic_distance/.venv/bin:$PATH"

EXPOSE 8050
CMD ["python", "main.py"]
