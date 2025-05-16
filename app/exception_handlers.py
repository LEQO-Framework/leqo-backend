from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.processing.pre import PreprocessingException
import traceback
import os
DEBUG = os.getenv("APP_DEBUG", "false").lower() == "true"

app = FastAPI(debug=DEBUG)

@app.exception_handler(PreprocessingException)
async def preprocessing_exception_handler(request: Request, exc: PreprocessingException):
    return JSONResponse(
        status_code = exc.error_code,
        content = {
            "message": "The following exception occured during PREPROCESSING: " + exc.args[0],
            "error_type": exc.error_type,
            "node": exc.node.id if exc.node else None,
            "traceback": traceback.format_exc() if DEBUG else None,
        },
    )