from pydantic import BaseModel

from app.model.block import Block
from app.model.project import Project


class CompileRequest(BaseModel):
    project: Project
    blocks: list[Block]
