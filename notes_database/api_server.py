#!/usr/bin/env python3
"""
Flask REST API for Notes.

This service provides CRUD endpoints backed by a local SQLite database.
- Binds to 0.0.0.0:5001
- CORS enabled (allow all origins)
- Uses notes table with schema:
    id INTEGER PK AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Endpoints:
- GET    /notes             -> List all notes (ordered by created_at DESC)
- GET    /notes/<int:id>    -> Get a single note by id
- POST   /notes             -> Create a new note (expects JSON: {title, content})
- PUT    /notes/<int:id>    -> Update an existing note (expects JSON: {title, content})
- DELETE /notes/<int:id>    -> Delete a note by id
"""

from flask import Flask, jsonify, request, Blueprint
from flask_cors import CORS
import sqlite3
import os
from typing import Dict, Any, Optional

DB_NAME = "myapp.db"

app = Flask(__name__)
# Enable CORS for all domains and routes (development-friendly)
# Keep CORS enabled for all /api/* endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Create API blueprint to mount all routes under /api
api = Blueprint("api", __name__)

# PUBLIC_INTERFACE
@api.get("/health")
def health():
    """
    Lightweight health check endpoint for availability monitoring.

    Returns:
        200 OK with JSON {"status": "ok"} to indicate the API is reachable and responsive.
    """
    return jsonify({"status": "ok"}), 200


def get_db_connection() -> sqlite3.Connection:
    """
    Returns a SQLite connection to the database with row_factory for dict-like access.
    """
    conn = sqlite3.connect(DB_NAME)
    # Return rows as tuples; we'll map explicitly for clarity and stability
    conn.row_factory = sqlite3.Row
    # Ensure foreign keys enabled and consistent behavior
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """
    Convert sqlite3.Row to a plain dict.
    """
    return {k: row[k] for k in row.keys()}


def ensure_notes_table() -> None:
    """
    Ensures the notes table exists. Idempotent.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def validate_payload(payload: Optional[Dict[str, Any]], require_both: bool = True):
    """
    Validates incoming JSON payload for notes.
    require_both=True: both title and content must be present and non-empty strings.
    """
    if payload is None:
        return False, "Request body must be JSON"
    title = payload.get("title")
    content = payload.get("content")
    if require_both:
        if not isinstance(title, str) or not title.strip():
            return False, "Field 'title' is required and must be a non-empty string"
        if not isinstance(content, str) or not content.strip():
            return False, "Field 'content' is required and must be a non-empty string"
    return True, ""


# PUBLIC_INTERFACE
@api.get("/notes")
def list_notes():
    """
    List all notes ordered by created_at DESC.

    Returns:
        200 OK with JSON array of notes:
        [
          { "id": int, "title": str, "content": str, "created_at": str, "updated_at": str },
          ...
        ]
    """
    ensure_notes_table()
    conn = get_db_connection()
    try:
        cur = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        return jsonify([row_to_dict(r) for r in rows]), 200
    finally:
        conn.close()


# PUBLIC_INTERFACE
@api.get("/notes/<int:note_id>")
def get_note(note_id: int):
    """
    Get a single note by id.

    Path params:
        note_id: int - ID of the note

    Returns:
        200 OK with note JSON when found
        404 Not Found when note doesn't exist
    """
    ensure_notes_table()
    conn = get_db_connection()
    try:
        cur = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (note_id,),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Note not found"}), 404
        return jsonify(row_to_dict(row)), 200
    finally:
        conn.close()


# PUBLIC_INTERFACE
@api.post("/notes")
def create_note():
    """
    Create a new note.

    Request JSON:
        { "title": str, "content": str }

    Returns:
        201 Created with created note JSON
        400 Bad Request on validation errors
    """
    ensure_notes_table()
    payload = request.get_json(silent=True)
    ok, err = validate_payload(payload, require_both=True)
    if not ok:
        return jsonify({"error": err}), 400

    title = payload["title"].strip()
    content = payload["content"].strip()

    conn = get_db_connection()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?)",
            (title, content),
        )
        conn.commit()
        new_id = cur.lastrowid

        cur = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (new_id,),
        )
        row = cur.fetchone()
        return jsonify(row_to_dict(row)), 201
    finally:
        conn.close()


# PUBLIC_INTERFACE
@api.put("/notes/<int:note_id>")
def update_note(note_id: int):
    """
    Update an existing note. Both title and content must be provided.

    Path params:
        note_id: int - ID of the note to update

    Request JSON:
        { "title": str, "content": str }

    Returns:
        200 OK with updated note JSON
        400 Bad Request on validation errors
        404 Not Found when note doesn't exist
    """
    ensure_notes_table()
    payload = request.get_json(silent=True)
    ok, err = validate_payload(payload, require_both=True)
    if not ok:
        return jsonify({"error": err}), 400

    title = payload["title"].strip()
    content = payload["content"].strip()

    conn = get_db_connection()
    try:
        # Ensure exists
        cur = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,))
        if not cur.fetchone():
            return jsonify({"error": "Note not found"}), 404

        # Update with updated_at set to CURRENT_TIMESTAMP
        conn.execute(
            """
            UPDATE notes
            SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, content, note_id),
        )
        conn.commit()

        cur = conn.execute(
            "SELECT id, title, content, created_at, updated_at FROM notes WHERE id = ?",
            (note_id,),
        )
        row = cur.fetchone()
        return jsonify(row_to_dict(row)), 200
    finally:
        conn.close()


# PUBLIC_INTERFACE
@api.delete("/notes/<int:note_id>")
def delete_note(note_id: int):
    """
    Delete a note by id.

    Path params:
        note_id: int - ID of the note to delete

    Returns:
        204 No Content when deleted
        404 Not Found when note doesn't exist
    """
    ensure_notes_table()
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,))
        if not cur.fetchone():
            return jsonify({"error": "Note not found"}), 404

        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return ("", 204)
    finally:
        conn.close()


def main():
    """
    Entry point to run the Flask app.

    Notes:
        - The server binds to 0.0.0.0:5001 so it is reachable by the reverse proxy.
        - All routes are mounted under /api (e.g., /api/notes, /api/health).
        - CORS is enabled for /api/* endpoints to facilitate frontend development.
        - If the process is not auto-started in your environment, run:
              python3 api_server.py
    """
    # Ensure DB file exists (it will be created automatically by sqlite when connecting)
    if not os.path.exists(DB_NAME):
        # Touch file by establishing connection (and also ensure table)
        ensure_notes_table()
    else:
        ensure_notes_table()

    # Register API blueprint under /api
    app.register_blueprint(api, url_prefix="/api")

    # Bind to 0.0.0.0:5001 (required for external access)
    app.run(host="0.0.0.0", port=5001, debug=False)


if __name__ == "__main__":
    main()
