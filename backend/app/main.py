from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, findings, health, reports, scans
from app.core.config import settings
from app.core.errors import AppError

app = FastAPI(title="code-quality-intelligence-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"success": False, "error_code": exc.error_code, "message": exc.message},
    )


app.include_router(health.router)
app.include_router(scans.router)
app.include_router(reports.router)
app.include_router(findings.router)
app.include_router(chat.router)
