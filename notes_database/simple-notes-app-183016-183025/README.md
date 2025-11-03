# simple-notes-app-183016-183025

Notes backend (SQLite + Flask)

- Server binds to 0.0.0.0 on port 5001
- All endpoints are under /api
- CORS is enabled for /api/*

Health check
- GET /api/health -> 200 {"status": "ok"}

Run locally
- cd notes_database
- python3 api_server.py

If using a frontend proxy, ensure it forwards /api/* to http://localhost:5001.
