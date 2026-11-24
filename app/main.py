# FastAPI entry point: app instance and routes.
from fastapi import FastAPI

app = FastAPI(title="Rental Agent Prototype")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
