# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development

```bash
# Start PostgreSQL
docker compose up -d

# Install dependencies (first time)
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# Run the backend (serves frontend too)
cd backend
uvicorn main:app --reload --port 8000
```

The app is then available at `http://localhost:8000`. The frontend is served as static files by FastAPI itself — there is no separate frontend dev server.

**Environment variable:** `DATABASE_URL` defaults to `postgresql://poc:poc@localhost:5432/authenticity_poc` (matches docker-compose).

**System dependency:** `python-gnupg` wraps the system `gpg` binary — `gpg` must be installed (`brew install gnupg` on macOS, `apt install gnupg` on Debian/Ubuntu).

**Import path:** `backend/` uses bare imports (`from crypto import ...`, not `from backend.crypto import ...`). `uvicorn` must be launched from inside `backend/` or the imports will fail.

## Architecture

This is a **content authenticity proof-of-concept** with a FastAPI backend and vanilla HTML/JS frontend. There is no build step and no test suite.

### Request flow

1. **Register** (`POST /api/register`) — generates an Ed25519 keypair via `gnupg`, stores both keys and the PGP fingerprint in the `creators` table.
2. **Login** (`POST /api/login`) — user uploads their private key `.asc`; server extracts the fingerprint and looks up the matching creator.
3. **Register content** (`POST /api/register-content`) — fingerprints the file (for images: 64-bit pHash + 256-bit pHash + exact SHA-256 of the raw bytes; for PDFs: SHA-256 of normalized text), builds a JSON assertion that **includes** the hashes, signs it with the creator's private key using OpenPGP clearsign, stores the result in `content_registrations`.
4. **Verify** (`POST /api/verify`) — re-fingerprints the file and returns the strongest match: for images, exact `sha256` (`match_type:"exact"`, status `verified`) first, then lowest Hamming distance on the 64-bit pHash; for PDFs, exact text hash. Verifies the stored OpenPGP signature.
5. **DB export** (`GET /api/db/export`) — returns all image registrations as JSON (schema 2: includes `phash256`, `sha256`, `signed_assertion`, `creator_public_key`) for the Firefox extension, which does its own tiered match + offline signature verification. `GET /api/db/version` returns just the count and latest timestamp for cheap polling.

### Module responsibilities

| File | Responsibility |
|------|---------------|
| `backend/main.py` | FastAPI app, all route handlers, serves frontend static files |
| `backend/fingerprint.py` | `phash_image` (64-bit pHash), `phash256_image` (256-bit pHash, `hash_size=16`), `sha256_bytes` (exact raw-bytes hash), `sha256_pdf` (PyMuPDF text + SHA-256), Hamming distance helpers |
| `backend/crypto.py` | GPG keypair generation, signing, verification — each call creates an isolated temp gnupghome and cleans it up |
| `backend/models.py` | SQLAlchemy ORM: `Creator` and `ContentRegistration` tables |
| `backend/database.py` | Engine + session factory |
| `frontend/index.html` | Public verifier UI |
| `frontend/creator.html` | Creator dashboard (register identity, upload content) |

### Image matching thresholds (fingerprint.py)

Server `/api/verify` (64-bit pHash, after the exact-`sha256` tier):
- Hamming distance = 0 → `authentic`
- 1–20 (`MODIFIED_THRESHOLD`) → `possibly_modified`
- > 20 → `not_found`

The extension uses tighter, tiered thresholds against the export: exact `sha256` → `verified`; else 256-bit pHash ≤ 24/256 (`PHASH256_MODIFIED_THRESHOLD`); else legacy 64-bit ≤ 9/64. Keep `phash.js` in sync with `imagehash` parameters here.

Supported image formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.tiff`.

### Key design notes

- The server retains the private key (noted as a POC simplification in `models.py` — production would move signing client-side).
- `crypto.py` never touches `~/.gnupg`; every GPG operation runs in a fresh temp directory that is always cleaned up.
- Database tables are auto-created on startup via `Base.metadata.create_all` (convenient for fresh installs/tests), but schema *changes* are managed with **Alembic** (see below). Pre-existing rows keep `sha256`/`phash256` NULL (originals aren't stored) and only do 64-bit perceptual matching until re-registered.
- The clearsign JSON body is sorted and indented (`json.dumps(sort_keys=True)`) so the plaintext is deterministic and independently verifiable with `gpg --verify assertion.asc`.

## Migrations (Alembic)

Config is `alembic.ini` (repo root); revisions live in `backend/alembic/versions/`. `env.py` pulls the DB URL and `Base.metadata` from the app, so migrations always target the same database as the service. Run from the repo root:

```bash
alembic upgrade head          # apply all pending migrations
alembic current               # show the current revision
alembic revision -m "msg"     # create a new (empty) revision; --autogenerate to diff models
alembic downgrade -1          # roll back one revision
```

`0001` is the baseline (idempotent `create_all`, a no-op on the existing DB); `0002` adds `sha256` + `phash256` + index, guarded by the inspector so it's safe whether or not the columns already exist. Adopting Alembic on the existing production DB needs no manual `stamp` — the first `alembic upgrade head` records the version table and the guarded steps skip what's already there.

## Deployment

Push to `main` triggers a GitHub Actions workflow (`.github/workflows/deploy.yml`) that SSHs into `77.90.40.64`, pulls, installs deps, runs `alembic upgrade head`, then restarts the `signing-poc-backend` systemd service. The server uses its own `.venv` at `/home/anish/.venv/signing-poc/`.

If the service uses a non-default `DATABASE_URL`, set it as a repository secret named `DATABASE_URL` so the deploy's migration step targets the same database; otherwise it falls back to `database.py`'s default (the same default the service uses).
