from fastapi import FastAPI

from app.model.CompileRequest import CompileRequest

app = FastAPI()


@app.post("/compile")
def compile(body: CompileRequest) -> CompileRequest:
    return body
