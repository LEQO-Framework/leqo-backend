from fastapi import FastAPI

from app.model.HelloWorld import HelloWorld

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.post("/")
def echo(body: HelloWorld):
    return body
