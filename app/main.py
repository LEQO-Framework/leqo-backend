from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.model.CompileRequest import CompileRequest

app = FastAPI()

origins: list[str] = [ # ToDo: wich origins do we need?
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:4242",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

results: dict[str, str] = {}


@app.post("/compile")
def compile(body: CompileRequest) -> str:
    id = body.metadata.id
    results[id] = body.model_dump_json()
    return f"GET /result/{id}"

@app.get("/result/{id}")
def result(id: str) -> str:
    return results[id]
