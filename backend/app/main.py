from fastapi import FastAPI

from app.api import health

app = FastAPI(title="Company News")
app.include_router(health.router)
