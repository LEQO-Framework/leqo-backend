from fastapi import FastAPI

from app.enricher.operations import demo
from app.model.HelloWorld import HelloWorld

app = FastAPI()

@app.get("/")
def root() -> dict[str, str]:
    print(demo())
    return {"message": "Hello World"}

@app.post("/")
def echo(body: HelloWorld) -> HelloWorld:
    return body
