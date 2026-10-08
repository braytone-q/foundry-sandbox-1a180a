"""Durable source, analysis and human-review history for one local server."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .images import MAX_IMAGES, UploadFailure
from .schemas import OrchestrationTrace, ReviewSummary


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        self.evidence_dir = path.parent / "evidence"

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection(True) as db:
            for statement in (
                """CREATE TABLE IF NOT EXISTS submissions (
                    id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                    current_revision INTEGER NOT NULL, review_status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
                """CREATE TABLE IF NOT EXISTS submission_revisions (
                    submission_id TEXT NOT NULL REFERENCES submissions(id),
                    revision INTEGER NOT NULL, description TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(submission_id, revision))""",
                """CREATE TABLE IF NOT EXISTS analysis_attempts (
                    id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    state TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
                    agent_name TEXT NOT NULL, agent_version TEXT NOT NULL, response_id TEXT,
                    analysis_json TEXT, failure_code TEXT, failure_message TEXT,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(submission_id, revision)
                        REFERENCES submission_revisions(submission_id, revision))""",
                """CREATE TABLE IF NOT EXISTS review_events (
                    id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    attempt_id TEXT NOT NULL REFERENCES analysis_attempts(id), action TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(submission_id, revision)
                        REFERENCES submission_revisions(submission_id, revision))""",
                "CREATE INDEX IF NOT EXISTS attempt_source ON analysis_attempts(submission_id, revision)",
                "CREATE INDEX IF NOT EXISTS review_source ON review_events(submission_id)",
                """CREATE TABLE IF NOT EXISTS evidence_images (
                    id TEXT PRIMARY KEY, submission_id TEXT NOT NULL REFERENCES submissions(id),
                    filename TEXT NOT NULL, media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    width INTEGER NOT NULL, height INTEGER NOT NULL, sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL, stored_name TEXT NOT NULL UNIQUE)""",
                """CREATE TABLE IF NOT EXISTS revision_images (
                    submission_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    image_id TEXT NOT NULL REFERENCES evidence_images(id), position INTEGER NOT NULL,
                    PRIMARY KEY(submission_id, revision, image_id),
                    UNIQUE(submission_id, revision, position),
                    FOREIGN KEY(submission_id, revision)
                        REFERENCES submission_revisions(submission_id, revision))""",
                """CREATE TABLE IF NOT EXISTS revision_locations (
                    submission_id TEXT NOT NULL, revision INTEGER NOT NULL, location_json TEXT NOT NULL,
                    PRIMARY KEY(submission_id, revision),
                    FOREIGN KEY(submission_id, revision) REFERENCES submission_revisions(submission_id, revision))""",
            ):
                db.execute(statement)
            if "image_assessment_json" not in {r[1] for r in db.execute("PRAGMA table_info(analysis_attempts)")}:
                db.execute("ALTER TABLE analysis_attempts ADD COLUMN image_assessment_json TEXT")
            if "orchestration_trace_json" not in {r[1] for r in db.execute("PRAGMA table_info(analysis_attempts)")}:
                db.execute("ALTER TABLE analysis_attempts ADD COLUMN orchestration_trace_json TEXT")

    def _submission(self, db, id):
        row = db.execute("SELECT * FROM submissions WHERE id=?", (id,)).fetchone()
        if row is None:
            raise NotFound("Submission not found.")
        return row

    def _latest(self, db, row):
        return db.execute("""SELECT * FROM analysis_attempts
            WHERE submission_id=? AND revision=? ORDER BY rowid DESC LIMIT 1""",
            (row["id"], row["current_revision"])).fetchone()

    def _mutable(self, db, id, version):
        row = self._submission(db, id)
        if row["version"] != version:
            raise Conflict("This submission changed. Refresh it before acting.")
        if row["review_status"] in {"APPROVED", "REJECTED"}:
            raise Conflict("This submission has a final human decision.")
        latest = self._latest(db, row)
        if latest and latest["state"] == "RUNNING":
            raise Conflict("Analysis is still running. Refresh after it completes.")
        return row, latest

    def _attempt(self, db, id, revision, description, agent_name, agent_version, timestamp):
        attempt_id = str(uuid4())
        db.execute("""INSERT INTO analysis_attempts
            (id, submission_id, revision, state, started_at, agent_name, agent_version)
            VALUES (?, ?, ?, 'RUNNING', ?, ?, ?)""",
            (attempt_id, id, revision, timestamp, agent_name, agent_version))
        return {"id": id, "attempt_id": attempt_id, "description": description,
                "images": [self._image_descriptor(r) for r in self._image_rows(db, id, revision)]}

    @contextmanager
    def source_write(self):
        created = []
        try:
            with self.connection(True) as db:
                yield db, created
        except BaseException:
            # Only this transaction's newly generated filenames may be removed.
            for path in created:
                path.unlink(missing_ok=True)
            raise

    def _image_rows(self, db, id, revision):
        return db.execute("""SELECT e.id, e.filename, e.media_type, e.size_bytes, e.width,
            e.height, e.sha256, e.created_at, e.stored_name FROM revision_images r
            JOIN evidence_images e ON e.id=r.image_id
            WHERE r.submission_id=? AND r.revision=? ORDER BY r.position""", (id, revision)).fetchall()

    def _image_descriptor(self, row):
        result = dict(row)
        result["path"] = self.evidence_dir / result.pop("stored_name")
        return result

    def image(self, id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM evidence_images WHERE id=?", (id,)).fetchone()
            if row is None:
                raise NotFound("Image not found.")
            return self._image_descriptor(row)

    def _save_images(self, db, id, revision, existing, images, created):
        if len(existing) + len(images) > MAX_IMAGES:
            raise UploadFailure(422, "An activity revision can contain at most 20 images.")
        ids = [image["id"] for image in existing]
        for image in images:
            destination = self.evidence_dir / image.stored_name
            if destination.exists():
                raise OSError("Image storage collision")
            created.append(destination)
            image.staged_path.replace(destination)
            db.execute("INSERT INTO evidence_images VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (image.id, id, image.filename, image.media_type, image.size_bytes, image.width,
                 image.height, image.sha256, image.created_at, image.stored_name))
            ids.append(image.id)
        for position, image_id in enumerate(ids):
            db.execute("INSERT INTO revision_images VALUES (?, ?, ?, ?)", (id, revision, image_id, position))

    def _save_location(self, db, id, revision, location):
        if location is not None:
            db.execute("INSERT INTO revision_locations VALUES (?, ?, ?)", (id, revision, json.dumps(location)))

    def _location(self, db, id, revision):
        row = db.execute("SELECT location_json FROM revision_locations WHERE submission_id=? AND revision=?", (id, revision)).fetchone()
        return json.loads(row[0]) if row else None

    def create(self, description, agent_name, agent_version, images=None, device_location=None):
        id, timestamp = str(uuid4()), now()
        with self.source_write() as (db, created):
            db.execute("INSERT INTO submissions VALUES (?, 1, 1, 'PENDING_REVIEW', ?, ?)",
                       (id, timestamp, timestamp))
            db.execute("INSERT INTO submission_revisions VALUES (?, 1, ?, ?)", (id, description, timestamp))
            self._save_images(db, id, 1, [], images or [], created)
            self._save_location(db, id, 1, device_location)
            return self._attempt(db, id, 1, description, agent_name, agent_version, timestamp)

    def begin_attempt(self, id, expected_version, agent_name, agent_version, description=None, images=None, device_location=None):
        with self.source_write() as (db, created):
            row, _ = self._mutable(db, id, expected_version)
            revision, status, timestamp = row["current_revision"], row["review_status"], now()
            if description is not None:
                existing = self._image_rows(db, id, revision)
                revision += 1
                status = "PENDING_REVIEW"
                db.execute("INSERT INTO submission_revisions VALUES (?, ?, ?, ?)",
                           (id, revision, description, timestamp))
                self._save_images(db, id, revision, existing, images or [], created)
                self._save_location(db, id, revision, device_location)
            else:
                description = db.execute("""SELECT description FROM submission_revisions
                    WHERE submission_id=? AND revision=?""", (id, revision)).fetchone()[0]
            db.execute("""UPDATE submissions SET version=version+1, current_revision=?,
                review_status=?, updated_at=? WHERE id=?""", (revision, status, timestamp, id))
            return self._attempt(db, id, revision, description, agent_name, agent_version, timestamp)

    def save_image_assessment(self, attempt_id, assessment):
        """Commit a completed inspection before the subsequent remote rule analysis."""
        with self.connection(True) as db:
            attempt = db.execute("SELECT state, image_assessment_json FROM analysis_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFound("Analysis attempt not found.")
            if attempt["state"] != "RUNNING" or attempt["image_assessment_json"] is not None:
                raise Conflict("This attempt cannot accept another image inspection.")
            db.execute("UPDATE analysis_attempts SET image_assessment_json=? WHERE id=?",
                       (assessment.model_dump_json(), attempt_id))

    def save_orchestration_trace(self, attempt_id: str, trace: OrchestrationTrace) -> None:
        """Persist a completed stage snapshot without a transaction across model calls."""
        with self.connection(True) as db:
            attempt = db.execute("SELECT state FROM analysis_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFound("Analysis attempt not found.")
            if attempt["state"] != "RUNNING":
                raise Conflict("This analysis attempt has already finished.")
            db.execute("UPDATE analysis_attempts SET orchestration_trace_json=? WHERE id=?",
                       (trace.model_dump_json(), attempt_id))

    def finish_attempt(self, attempt_id, result=None, failure=None):
        if (result is None) == (failure is None):
            raise ValueError("Provide one result or failure")
        with self.connection(True) as db:
            attempt = db.execute("SELECT * FROM analysis_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFound("Analysis attempt not found.")
            if attempt["state"] != "RUNNING":
                raise Conflict("This analysis attempt has already finished.")
            timestamp = now()
            db.execute("""UPDATE analysis_attempts SET state=?, finished_at=?, response_id=?,
                analysis_json=?, failure_code=?, failure_message=?, citations_json=? WHERE id=?""",
                ("SUCCEEDED" if result else "FAILED", timestamp, result.response_id if result else None,
                 result.analysis.model_dump_json() if result else None, failure.code if failure else None,
                 failure.message if failure else None,
                 json.dumps([c.model_dump() for c in result.citations]) if result else "[]", attempt_id))
            db.execute("UPDATE submissions SET version=version+1, updated_at=? WHERE id=?",
                       (timestamp, attempt["submission_id"]))
            db.execute("UPDATE analysis_attempts SET image_assessment_json=COALESCE(image_assessment_json, ?) WHERE id=?",
                (result.image_assessment.model_dump_json() if result and result.image_assessment else None, attempt_id))
            if result and result.orchestration_trace is not None:
                db.execute("UPDATE analysis_attempts SET orchestration_trace_json=? WHERE id=?",
                           (result.orchestration_trace.model_dump_json(), attempt_id))

    def review(self, id, input):
        with self.connection(True) as db:
            row, attempt = self._mutable(db, id, input.expected_version)
            if attempt is None or attempt["state"] != "SUCCEEDED":
                raise Conflict("A successful current analysis is required before human review.")
            timestamp = now()
            db.execute("INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (str(uuid4()), id, row["current_revision"], attempt["id"], input.action,
                        input.reviewer_name, input.notes, timestamp))
            status = {"APPROVE": "APPROVED", "REJECT": "REJECTED",
                      "REQUEST_CLARIFICATION": "CLARIFICATION_REQUESTED"}[input.action]
            db.execute("UPDATE submissions SET version=version+1, review_status=?, updated_at=? WHERE id=?",
                       (status, timestamp, id))
        return self.get(id)

    def recover_interrupted(self):
        with self.connection(True) as db:
            interrupted = db.execute("SELECT DISTINCT submission_id FROM analysis_attempts WHERE state='RUNNING'").fetchall()
            timestamp = now()
            db.execute("""UPDATE analysis_attempts SET state='FAILED', finished_at=?,
                failure_code='INTERRUPTED', failure_message='Analysis was interrupted by a server restart. Retry analysis.'
                WHERE state='RUNNING'""", (timestamp,))
            for row in interrupted:
                db.execute("UPDATE submissions SET version=version+1, updated_at=? WHERE id=?", (timestamp, row[0]))

    def _record(self, db, id):
        record = dict(self._submission(db, id))
        record["revisions"] = [dict(r) for r in db.execute("""SELECT revision, description, created_at
            FROM submission_revisions WHERE submission_id=? ORDER BY revision""", (id,))]
        for revision in record["revisions"]:
            revision["image_ids"] = [image["id"] for image in self._image_rows(db, id, revision["revision"])]
            revision["device_location"] = self._location(db, id, revision["revision"])
        image_ids = {r["revision"]: r["image_ids"] for r in record["revisions"]}
        locations = {r["revision"]: r["device_location"] for r in record["revisions"]}
        record["device_location"] = locations[record["current_revision"]]
        record["images"] = []
        for row in self._image_rows(db, id, record["current_revision"]):
            image = dict(row)
            image.pop("stored_name")
            image["url"] = f'/api/images/{image["id"]}'
            record["images"].append(image)
        record["description"] = record["revisions"][-1]["description"]
        attempts = []
        for r in db.execute("""SELECT id, revision, state, started_at, finished_at, agent_name,
            agent_version, response_id, analysis_json, failure_code, failure_message, citations_json,
            image_assessment_json, orchestration_trace_json
            FROM analysis_attempts WHERE submission_id=? ORDER BY rowid DESC""", (id,)):
            attempt = dict(r)
            attempt["analysis"] = json.loads(attempt.pop("analysis_json") or "null")
            attempt["image_assessment"] = json.loads(attempt.pop("image_assessment_json") or "null")
            attempt["orchestration_trace"] = json.loads(attempt.pop("orchestration_trace_json") or "null")
            attempt["citations"] = json.loads(attempt.pop("citations_json"))
            attempt["image_ids"] = image_ids[attempt["revision"]]
            attempt["device_location"] = locations[attempt["revision"]]
            attempts.append(attempt)
        record["attempts"] = attempts
        record["latest_attempt"] = next((a for a in attempts if a["revision"] == record["current_revision"]), None)
        record["reviews"] = [dict(r) for r in db.execute("""SELECT id, revision, attempt_id, action,
            reviewer_name, notes, created_at FROM review_events WHERE submission_id=? ORDER BY rowid DESC""", (id,))]
        return record

    def get(self, id):
        with self.connection() as db:
            return self._record(db, id)

    def review_summary(self):
        # One aggregate read of current human statuses, without source/evidence data.
        # Close the transaction before the question's external model calls.
        with self.connection() as db:
            counts = {row['review_status']: row['count'] for row in db.execute(
                "SELECT review_status, COUNT(*) AS count FROM submissions GROUP BY review_status")}
            captured_at = now()
        pending = counts.get('PENDING_REVIEW', 0)
        clarification = counts.get('CLARIFICATION_REQUESTED', 0)
        return ReviewSummary(captured_at=captured_at, total_submissions=sum(counts.values()),
            pending_human_review=pending, awaiting_clarification=clarification,
            approved=counts.get('APPROVED', 0), rejected=counts.get('REJECTED', 0),
            active_review_queue=pending + clarification)

    def list(self, status=None, recommendation=None, analysis_state=None, limit=25, offset=0):
        conditions, params = [], []
        if status is None:
            conditions.append("s.review_status IN ('PENDING_REVIEW', 'CLARIFICATION_REQUESTED')")
        elif status != "ALL":
            conditions.append("s.review_status=?")
            params.append(status)
        if recommendation:
            conditions.append("json_extract(a.analysis_json, '$.recommendation')=?")
            params.append(recommendation)
        if analysis_state:
            conditions.append("a.state=?")
            params.append(analysis_state)
        query = """FROM submissions s LEFT JOIN analysis_attempts a ON a.rowid=(
            SELECT rowid FROM analysis_attempts WHERE submission_id=s.id AND revision=s.current_revision
            ORDER BY rowid DESC LIMIT 1)"""
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        with self.connection() as db:
            total = db.execute("SELECT COUNT(*) " + query, params).fetchone()[0]
            ids = db.execute("SELECT s.id " + query + " ORDER BY s.rowid DESC LIMIT ? OFFSET ?",
                             [*params, limit, offset]).fetchall()
            return {"items": [self._record(db, row[0]) for row in ids], "total": total, "limit": limit, "offset": offset}
