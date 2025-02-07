FROM python:3.13.2-alpine

WORKDIR /leqo-backend

COPY ./pyproject.toml /leqo-backend/pyproject.toml

COPY ./.python-version /leqo-backend/.python-version

COPY ./uv.lock /leqo-backend/uv.lock

RUN pip install uv

RUN pip install "fastapi[standard]"

RUN uv sync

COPY ./app /leqo-backend/app

CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0", "--port", "80"]
