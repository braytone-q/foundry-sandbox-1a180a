import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .foundry import FoundryGateway
from .images import MAX_UPLOAD_BODY_BYTES, UploadBodyLimitMiddleware, UploadFailure, upload_path
from .schemas import (AttemptState, Recommendation, RetryInput, ReviewInput, RevisionInput,
                      SubmissionInput, SubmissionPage, SubmissionRecord)
from .service import SubmissionService
from .settings import Settings
from .store import Conflict, NotFound, Store


def create_app(settings=None, gateway=None):
    settings = settings or Settings.from_env()
    gateway = gateway or FoundryGateway(settings)
    store = Store(settings.database_path)
    service = SubmissionService(store, gateway, settings)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize()
        store.recover_interrupted()
        try:
            yield
        finally:
            gateway.close()

    app = FastAPI(title="Re-gen local review API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(UploadBodyLimitMiddleware, limit=MAX_UPLOAD_BODY_BYTES)
    app.state.store, app.state.service = store, service

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        try:
            host = urlsplit("//" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        if host not in {"localhost", "127.0.0.1", "::1"}:
            return JSONResponse({"detail": "Use a localhost address."}, status_code=400)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if (origin and origin != f"{request.url.scheme}://{request.headers['host']}") or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Use the interface on this server."}, status_code=403)
            expected_type = "multipart/form-data" if upload_path(request.url.path) else "application/json"
            if request.headers.get("content-type", "").split(";", 1)[0].lower() != expected_type:
                return JSONResponse({"detail": f"Send {expected_type}."}, status_code=415)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' blob:; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        return response

    @app.exception_handler(NotFound)
    async def not_found(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse({"detail": "Local storage could not complete the request. Check the server and refresh."}, status_code=500)

    @app.exception_handler(OSError)
    async def file_error(request, exc):
        return JSONResponse({"detail": "Local image storage could not complete the request. Check available disk space and retry."}, status_code=500)

    @app.exception_handler(UploadFailure)
    async def invalid_upload(request, exc):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    async def validate_form(request, fields):
        form = await request.form()
        if set(form.keys()) != fields or any(len(form.getlist(key)) != 1 for key in fields - {"images"}):
            raise HTTPException(422, "Use only the required description, version and image fields.")

    @app.post("/api/submissions/with-images", response_model=SubmissionRecord, status_code=201)
    async def create_images(request: Request, description: Annotated[str, Form()], images: Annotated[list[UploadFile], File()]):
        await validate_form(request, {"description", "images"})
        try:
            input = SubmissionInput(description=description)
        except ValidationError:
            raise HTTPException(422, "Supply a meaningful description of at most 16,000 characters.")
        return await run_in_threadpool(service.upload, input, images)

    @app.post("/api/submissions/{id}/revisions/with-images", response_model=SubmissionRecord, status_code=201)
    async def revise_images(id: str, request: Request, description: Annotated[str, Form()],
                            expected_version: Annotated[int, Form(ge=1)], images: Annotated[list[UploadFile], File()]):
        await validate_form(request, {"description", "expected_version", "images"})
        try:
            input = RevisionInput(description=description, expected_version=expected_version)
        except ValidationError:
            raise HTTPException(422, "Supply a meaningful description of at most 16,000 characters and the viewed version.")
        return await run_in_threadpool(service.upload, input, images, id)

    @app.get("/api/images/{id}", include_in_schema=True)
    def original_image(id: str):
        image = store.image(id)
        return FileResponse(image["path"], media_type=image["media_type"], filename=image["filename"], content_disposition_type="inline")

    @app.get("/api/health")
    def health():
        store.list(limit=1)
        return {"status": "ready", "mode": "local", "agent_name": settings.agent_name, "agent_version": settings.agent_version}

    @app.post("/api/submissions", response_model=SubmissionRecord, status_code=201)
    def create(input: SubmissionInput):
        return service.create(input)

    @app.get("/api/submissions", response_model=SubmissionPage)
    def queue(status: Literal["ALL", "PENDING_REVIEW", "CLARIFICATION_REQUESTED", "APPROVED", "REJECTED"] | None = None,
              recommendation: Recommendation | None = None, analysis_state: AttemptState | None = None,
              limit: Annotated[int, Query(ge=1, le=100)] = 25, offset: Annotated[int, Query(ge=0)] = 0):
        return store.list(status, recommendation, analysis_state, limit, offset)

    @app.get("/api/submissions/{id}", response_model=SubmissionRecord)
    def detail(id: str):
        return store.get(id)

    @app.post("/api/submissions/{id}/revisions", response_model=SubmissionRecord, status_code=201)
    def revise(id: str, input: RevisionInput):
        return service.revise(id, input)

    @app.post("/api/submissions/{id}/analyze", response_model=SubmissionRecord)
    def retry(id: str, input: RetryInput):
        return service.retry(id, input)

    @app.post("/api/submissions/{id}/reviews", response_model=SubmissionRecord, status_code=201)
    def review(id: str, input: ReviewInput):
        return service.review(id, input)

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def interface():
        return FileResponse(static / "index.html")

    return app
