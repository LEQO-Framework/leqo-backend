import os
from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


def find_files(path: Path, model: type[TModel]) -> Iterator[TModel]:
    for _, _, files in os.walk(path):
        for file_name in files:
            with open(path / file_name) as file:
                yield model.model_validate(yaml.safe_load(file))
