import json
import os

from src.api.main import app

# Generate and persist OpenAPI schema reflecting latest routers and models
schema = app.openapi()

os.makedirs("interfaces", exist_ok=True)
with open(os.path.join("interfaces", "openapi.json"), "w") as f:
    json.dump(schema, f, indent=2)
