from pydantic import BaseModel


class HelloWorld(BaseModel):
    test: str
    test2: list[str]
