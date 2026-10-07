"""Validate original image bytes before associating them with a source revision."""
import hashlib
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

MAX_IMAGES = 20
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = MAX_IMAGES * MAX_IMAGE_BYTES + 1024 * 1024
FORMATS = {"JPEG": ("image/jpeg", "jpg"), "PNG": ("image/png", "png"), "WEBP": ("image/webp", "webp")}


class UploadFailure(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


@dataclass(frozen=True)
class PreparedImage:
    id: str
    filename: str
    media_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    created_at: str
    staged_path: Path
    stored_name: str

    def metadata(self):
        result = asdict(self)
        result.pop("staged_path")
        return result


def cleanup_images(images):
    for directory in {image.staged_path.parent for image in images}:
        shutil.rmtree(directory, ignore_errors=True)


def prepare_images(files, directory):
    if not 1 <= len(files) <= MAX_IMAGES:
        raise UploadFailure(422, "Supply between 1 and 20 images.")
    directory.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".upload-", dir=directory))
    prepared = []
    try:
        for number, upload in enumerate(files, 1):
            id, size, digest = str(uuid4()), 0, hashlib.sha256()
            path = staging / (id + ".part")
            upload.file.seek(0)
            with path.open("wb") as target:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise UploadFailure(413, "Each image must be at most 8 MB.")
                    digest.update(chunk)
                    target.write(chunk)
            try:
                with Image.open(path) as image:
                    if image.format not in FORMATS or getattr(image, "is_animated", False):
                        raise UploadFailure(415, "Use non-animated JPEG, PNG or WebP images.")
                    media_type, extension = FORMATS[image.format]
                    width, height = image.size
                    if width * height > 32_000_000 or max(width, height) > 16000:
                        raise UploadFailure(422, "Images must be at most 32 million pixels and 16,000 pixels per side.")
                    image.verify()
                with Image.open(path) as image:
                    image.load()
            except UnidentifiedImageError as exc:
                raise UploadFailure(415, "Use valid JPEG, PNG or WebP images.") from exc
            except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
                raise UploadFailure(422, "An image is damaged or cannot be decoded. Replace it and try again.") from exc
            name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
            name = "".join(c for c in name if ord(c) >= 32 and ord(c) != 127).strip()[:200]
            name = name or f"image-{number}.{extension}"
            prepared.append(PreparedImage(id, name, media_type, size, width, height, digest.hexdigest(),
                datetime.now(timezone.utc).isoformat(), path, f"{id}.{extension}"))
        return prepared
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def upload_path(path):
    return path == "/api/submissions/with-images" or (
        path.startswith("/api/submissions/") and path.endswith("/revisions/with-images"))


class UploadBodyLimitMiddleware:
    def __init__(self, app, limit=MAX_UPLOAD_BODY_BYTES):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not upload_path(scope["path"]):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = self.limit + 1
        if length < 0 or length > self.limit:
            return await JSONResponse({"detail": "The image upload is too large."}, status_code=413)(scope, receive, send)
        received = 0
        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.limit:
                raise HTTPException(413, "The image upload is too large.")
            return message
        await self.app(scope, limited_receive, send)
