FROM python:3.13.2-alpine

WORKDIR /leqo-backend

COPY ./.env /.env

COPY ./pyproject.toml /leqo-backend/pyproject.toml

COPY ./.python-version /leqo-backend/.python-version

COPY ./uv.lock /leqo-backend/uv.lock

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv sync --frozen --no-cache

COPY ./app /leqo-backend/app

CMD ["/leqo-backend/.venv/bin/fastapi", "run", "app/main.py", "--port", "80"]
