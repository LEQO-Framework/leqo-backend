# https://www.doctave.com/blog/python-export-fastapi-openapi-spec

# extract-openapi.py
import sys
import yaml

sys.path.insert(0, "../")

from app.main import app

if __name__ == "__main__":
    openapi = app.openapi()
    version = openapi.get("openapi", "unknown version")

    with open("./docs/openapi.yaml", "w") as f:
        yaml.dump(openapi, f, sort_keys=False)

    print(f"spec written to 'openapi.yaml'")