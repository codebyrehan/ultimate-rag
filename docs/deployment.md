# Deployment

## Quick Start (Docker Compose)

```bash
./start.sh        # Linux/macOS
.\start.ps1       # Windows
```

Or manually:

```bash
cp .env.example .env
docker compose up --build
```

## Default Ports

| Service  | Port  |
|----------|-------|
| Frontend | 3000  |
| API      | 8000  |
| PostgreSQL | 5432 |
| Redis    | 6379  |
| Ollama   | 11434 |

## Environment Variables

Key settings (see `.env.example` for full list):

```env
# Database
DATABASE_URL=postgresql+psycopg://rag_user:rag_pass@postgres:5432/ultimate_rag

# Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5

# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
LLM_MODEL=qwen3:4b

# Vector Store
VECTOR_STORE_PROVIDER=pgvector

# Worker
INLINE_WORKER=0  # Use RQ worker instead of inline processing
```

## Production Notes

- Set `SECRET_KEY` to a long random string
- Use PostgreSQL + pgvector for production-scale vector search
- Use Redis + RQ for background ingestion jobs
- Set `CACHE_ENABLED=true` and `CACHE_TTL_SECONDS=300` to cache embeddings
- Use Ollama locally for free LLM inference
- Configure appropriate rate limits
- Set `LOG_FORMAT=json` for structured logs
- JWT access tokens expire in 1 hour; refresh tokens last 24 hours. The `/auth/refresh` endpoint rotates refresh tokens on each use.
- Always terminate TLS at the load balancer; set `X-Forwarded-Proto: https` so the app emits HSTS headers.
- The API container runs as a non-root user for defense in depth.

---

## Koyeb + Supabase Free Deployment

Deploy Ultimate RAG on **Koyeb Free Web Service** + **Supabase Free PostgreSQL** for **$0/month**.

### Prerequisites

- [Koyeb](https://www.koyeb.com/) account (free tier)
- [Supabase](https://supabase.com/) account (free tier)

### Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard/projects
2. Click **New Project**
3. Choose organization, enter project name (e.g., `ultimate-rag-db`), set a strong database password, and select **Free** plan
4. Wait for provisioning (~2 minutes)
5. Go to **Project Settings** → **Database** → **Connection string**
6. Copy the **URI** format connection string (port 5432)
   - Example: `postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres`
7. Save this connection string — you will need it for Koyeb

### Step 2: Prepare Koyeb

1. Go to https://app.koyeb.com/
2. Click **Create** → **Web Service**
3. Select **Dockerfile** as the builder
4. Connect your GitHub repository: `codebyrehan/ultimate-rag`
5. Set **Branch**: `main`
6. Set **Dockerfile path**: `./Dockerfile`
7. Set **Docker context**: `.`

### Step 3: Configure Environment Variables

In the **Environment variables** section, add:

| Key | Value | Notes |
|-----|-------|-------|
| `DATABASE_URL` | `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres` | From Supabase dashboard |
| `SECRET_KEY` | `generateValue: true` | Let Koyeb generate a secure random value |
| `LLM_PROVIDER` | `stub` | Free, no external API needed |
| `EMBEDDING_PROVIDER` | `local` | Runs in-container |
| `VECTOR_STORE_PROVIDER` | `in_memory` | No external vector DB needed |
| `RERANKER_PROVIDER` | `stub` | Free |
| `INLINE_WORKER` | `1` | No Redis needed |
| `CACHE_ENABLED` | `false` | Save memory on free tier |
| `CLAIM_EXTRACTION_ENABLED` | `false` | Reduce CPU on free tier |
| `FAITHFULNESS_CHECK_ENABLED` | `false` | Reduce CPU on free tier |
| `CORS_ORIGINS` | `*` | Same-origin deployment |
| `LOG_LEVEL` | `info` | |
| `LOG_FORMAT` | `json` | |

### Step 4: Configure Instance

- **Instance**: **Free** ( Nano )
- **Regions**: Choose the region closest to you
- **Horizontal scaling**: 1 instance
- **Vertical scaling**: Free tier (shared CPU, 256 MB RAM)

### Step 5: Deploy

1. Click **Deploy**
2. Koyeb will build the Docker image (~3-5 minutes first build)
3. Once deployed, your app will be available at: `https://<your-service-name>-<your-username>.koyeb.app`

### Step 6: Verify Deployment

```bash
# Health check
curl https://<your-service-name>-<your-username>.koyeb.app/health

# Expected response:
# {"status":"ok","version":"0.1.0","components":{...}}
```

Then open the URL in a browser and verify:
- [ ] Frontend loads
- [ ] Registration works
- [ ] Login works
- [ ] PDF upload works
- [ ] Search returns results
- [ ] Chat returns responses with citations

### Important Notes

- **Scale-to-zero**: Koyeb free tier scales to zero after inactivity. Cold starts may take 5-10 seconds.
- **In-memory vector store**: Data is lost on scale-to-zero. For persistent storage, use a vector database (not configured in this free setup).
- **Local embeddings**: The `local` embedding provider runs on CPU. On free tier with 256 MB RAM, keep document counts small.
- **No Redis**: `INLINE_WORKER=1` runs background jobs in-process. This is fine for low traffic.
- **No pgvector required**: `VECTOR_STORE_PROVIDER=in_memory` preserves the existing architecture. If you want persistent vector search, switch to `pgvector` and ensure your Supabase database has the extension enabled.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails on `npm ci` | The Dockerfile falls back to `npm install` automatically |
| Database connection fails | Verify Supabase connection string format is `postgresql://...` |
| Health check fails | Check logs for database migration errors |
| Frontend returns 404 | Ensure `/health` works — if it does, nginx is running |
| 502 errors on API | Check backend logs for OOM or import errors |

### Cost Estimate

| Resource | Provider | Plan | Cost |
|----------|----------|------|------|
| Web Service | Koyeb | Free | $0 |
| PostgreSQL | Supabase | Free | $0 |
| **Total** | | | **$0/month** |

