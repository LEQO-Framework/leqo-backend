# https://www.doctave.com/blog/python-export-fastapi-openapi-spec

# extract-openapi.py
import json

from app.main import app

if __name__ == "__main__":
    openapi = app.openapi()
    version = openapi.get("openapi", "unknown version")

    with open("./docs/openapi.json", "w") as f:
        json.dump(openapi, f, indent=2)

    print("spec written to 'openapi.json'")
