from fastapi import FastAPI

from app.model.HelloWorld import HelloWorld

app = FastAPI()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/")
def echo(body: HelloWorld) -> HelloWorld:
    return body
