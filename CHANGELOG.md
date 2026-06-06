# CHANGELOG

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-06

### Added

- **Phase C: API v1 & Documentation Improvements**
   - **C1 — API Versioning**: All API routes prefixed with `/api/v1` (sources, topics, schedules, collection, items, tags, stats). Frontend `BASE_URL` updated to `/api/v1`.
   - **C2 — OpenAPI / Swagger Docs**: Added Swagger UI (`/docs`), ReDoc (`/redoc`), and raw OpenAPI schema (`/openapi.json`). Added logging middleware with request ID tracking. Added validation exception handler for consistent error responses. Enhanced `/health` endpoint with version info.
   - **C3 — Frontend Error Boundary**: Created `ErrorBoundary` React component with retry button and error logging. Integrated into `App.tsx` to wrap all page components, preventing full-page crashes on component errors.
   - **C4 — Global API Rate Limiting**: Sliding-window rate limiter middleware (120 requests per 60 seconds per IP). Returns `429 Too Many Requests` with `Retry-After` header when exceeded. Adds `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` response headers.

### Changed

- Updated FastAPI app structure in `backend/app/main.py` with lifespan manager, middleware stack, and custom exception handlers.
- Updated frontend `BASE_URL` from `/api` to `/api/v1`.
- Added `.gitignore` for Python virtual environments, node_modules, build artifacts, and IDE files.

### Fixed

- Resolved API path mismatches between frontend and backend after versioning migration.
- All 31 existing tests pass without modification (paths updated in test suite).

### Technical Details

- **Backend**: Python 3.12 + FastAPI 0.115.6 + SQLAlchemy + SQLite (WAL mode) + APScheduler
- **Frontend**: React + TypeScript + Vite with ECharts visualizations
- **Rate Limiting**: Sliding window algorithm using `time.monotonic()` with per-IP tracking
- **Error Handling**: Standardized 422 responses with structured error details

---

## [0.2.0] - Previous Release

### Added

- Core collection engine with multi-source data gathering
- Topic-driven tagging and structured storage
- Dashboard with real-time statistics
- Source configuration management
- Scheduled collection tasks via APScheduler
- ECharts-based data visualizations

### Technical Stack


---

## [0.1.0] - Initial Release

- Project scaffolding and initial architecture
- Basic API endpoints for data management
- Simple frontend shell with navigation
