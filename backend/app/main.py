from fastapi import FastAPI

from app.api import companies, health, users

app = FastAPI(title="Company News")
app.include_router(health.router)
app.include_router(companies.router)
app.include_router(users.router)
