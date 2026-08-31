# Security

## Authentication

- **Password hashing**: PBKDF2-SHA256 (passlib, 12 rounds)
- **JWT tokens**: HS256, configurable expiry
- **Token validation**: On every protected route via `CurrentUser` dependency
- **Brute force**: Rate-limited login endpoint

## Authorization

- Every API route extracts `tenant_id` from JWT
- Every repository operation enforces tenant scoping
- User cannot access another tenant's resources (verified by tests)

## Input Validation

- Filenames sanitized via `sanitize_filename()` (strips path traversal, restricts charset)
- PDF magic bytes validated (`%PDF-`)
- MIME type whitelist enforced
- File size limits enforced

## Prompt Security

- System prompt uses explicit grounding instructions
- Retrieved document content treated as untrusted data
- Citations are metadata-backed (LLM does not control chunk IDs, page numbers, or filenames)
- If evidence is insufficient, the answer builder states it cannot answer

## SQL Injection

- All queries use SQLAlchemy ORM / parameterized queries
- No string interpolation in SQL

## IDOR

- All document, conversation, and chunk queries include `tenant_id` filter
- Path parameters are validated against tenant ownership

## Secrets

- Secret key loaded from environment variables only
- `SecretStr` used for sensitive values
- `.env` file is in `.gitignore`

## Rate Limiting

- Per-route sliding window limits
- Registration, login, upload, and search are protected
