from fastapi import FastAPI

from app.model.CompileRequest import CompileRequest

app = FastAPI()

results: dict[str, str] = {}


@app.post("/compile")
def compile(body: CompileRequest) -> str:
    id = body.metadata.id
    results[id] = body.model_dump_json()
    return f"GET /result/{id}"

@app.get("/result/{id}")
def result(id: str) -> str:
    return results[id]
