from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.model.block import BlockType
from app.model.compile_request import CompileRequest
from app.qasm_builder import QASMBuilder
from app.qasm_processor import process_block

app = FastAPI()


@app.post("/compile", response_class=PlainTextResponse)
def root(request: CompileRequest) -> str:
    builder = QASMBuilder()

    for block in request.blocks:
        if block.type == BlockType.CLASSICAL_OPERATION:
            continue

        process_block(block, builder)

    return builder.build()
