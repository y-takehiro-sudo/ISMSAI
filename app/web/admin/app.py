from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.web.admin.routes import router as admin_router

def create_admin_app() -> FastAPI:
    app = FastAPI(title="ISMS管理システム")
    app.include_router(admin_router)
    return app
