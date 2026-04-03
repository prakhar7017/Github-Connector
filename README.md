# GitHub Cloud Connector

Production-oriented FastAPI service that talks to the [GitHub REST API](https://docs.github.com/en/rest) using either a **Personal Access Token (PAT)** or **GitHub OAuth 2.0** (`AUTH_METHOD`). It exposes endpoints to list repositories, issues, and commits, and to create issues and pull requests.

## Features

- Async HTTP via **httpx**
- Configuration via **python-dotenv** / environment variables (no secrets in code)
- **Auth strategies**: PAT from env or OAuth (login → callback → in-memory token); `get_auth_strategy()` selects implementation
- GitHub headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json` (from the active strategy)
- **Pydantic** models for write endpoints and **DTO-style** JSON responses (commits, PRs, issues)
- Structured **logging** for GitHub API failures
- **Retries** (with exponential backoff) on rate limits and transient 5xx / network errors via **tenacity**
- Errors from GitHub are surfaced with appropriate HTTP status codes and message bodies

## Project layout

```
app/
  main.py                 # FastAPI app, router registration
  auth/
    strategies.py         # GitHubAuthStrategy, PAT / OAuth implementations
    factory.py            # get_auth_strategy()
    oauth_store.py        # In-memory OAuth token + CSRF state
  core/
    config.py             # Settings (AUTH_METHOD, PAT + OAuth vars)
    exceptions.py         # GitHubAPIError
  models/
    schemas.py            # Request/response models
  routes/
    auth.py               # GET /auth/login, /auth/callback
    github.py             # APIRouter for GitHub endpoints
  services/
    github_service.py     # All GitHub REST calls
.env.example
requirements.txt
README.md
```

## Prerequisites

- Python 3.10+
- **PAT mode (`AUTH_METHOD=PAT`, default):** a [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with scopes appropriate for your use (`repo` for private repos, issue/PR operations, etc.).
- **OAuth mode (`AUTH_METHOD=OAUTH`):** a [GitHub OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app) with `repo` scope via `/auth/login`, and the callback URL matching `GITHUB_REDIRECT_URI`.

Token expiry: classic OAuth user tokens from GitHub generally do not expire until revoked; this app stores the token in process memory only (lost on restart).

## Setup

1. Clone or copy this project and create a virtual environment (recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure secrets:

   ```bash
   copy .env.example .env
   ```

   Edit `.env`: choose `AUTH_METHOD=PAT` (default) and set `GITHUB_TOKEN`, **or** `AUTH_METHOD=OAUTH` with `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, and `GITHUB_REDIRECT_URI`. See **Authentication** below. Optionally override `GITHUB_API_BASE_URL` (default `https://api.github.com`).

## Run the server

From the project root (`Github_Connector`):

```bash
uvicorn app.main:app --reload
```

The app listens on `http://127.0.0.1:8000` by default. Open `http://127.0.0.1:8000/docs` for interactive Swagger UI.

## Authentication

| Variable | PAT mode | OAuth mode |
|----------|----------|------------|
| `AUTH_METHOD` | `PAT` (default) | `OAUTH` |
| `GITHUB_TOKEN` | Required | Omit or unused |
| `GITHUB_CLIENT_ID` | — | Required |
| `GITHUB_CLIENT_SECRET` | — | Required |
| `GITHUB_REDIRECT_URI` | — | Required (must match OAuth App & callback URL) |

`GitHubService` calls `get_auth_strategy()` and uses `strategy.get_headers()` for every GitHub API request.

### OAuth usage flow (local demo)

1. Set `AUTH_METHOD=OAUTH` and the three OAuth variables in `.env`; restart the app.
2. Open a browser to `http://127.0.0.1:8000/auth/login` — you are redirected to GitHub to authorize (`scope=repo`).
3. After approval, GitHub redirects to `http://127.0.0.1:8000/auth/callback?code=...&state=...`.
4. The app exchanges the code, stores the access token **in memory**, and returns JSON (including `access_token` for local debugging only).
5. Call `/repos/...`, `/issues/...`, etc.; they use the stored OAuth bearer token automatically.

If you hit GitHub routes before completing OAuth, you get **401** with a message to complete `/auth/login` first.  
**PAT mode** ignores `/auth/*` for API usage; those routes return **400** explaining PAT is active.

## API endpoints

### OAuth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Redirect to GitHub (`AUTH_METHOD=OAUTH` only) |
| GET | `/auth/callback` | Exchange `code` for token; stores token in memory |

### Health

| Method | Path     | Description |
|--------|----------|-------------|
| GET    | `/health` | Liveness check |

**Example**

```bash
curl http://127.0.0.1:8000/health
```

### List repositories for a user

| Method | Path              | Description |
|--------|-------------------|-------------|
| GET    | `/repos/{username}` | Public repos for `username` (and more if the token allows) |

**Example**

```bash
curl http://127.0.0.1:8000/repos/octocat
```

### List issues in a repository

| Method | Path                       | Description |
|--------|----------------------------|-------------|
| GET    | `/issues/{owner}/{repo}`   | Issues only (pull requests are excluded) |

**Example**

```bash
curl http://127.0.0.1:8000/issues/microsoft/vscode
```

### Create an issue

| Method | Path             | Description |
|--------|------------------|-------------|
| POST   | `/create-issue`  | JSON body: `owner`, `repo`, `title`, optional `body` |

**Example**

```bash
curl -X POST http://127.0.0.1:8000/create-issue ^
  -H "Content-Type: application/json" ^
  -d "{\"owner\":\"your-user\",\"repo\":\"your-repo\",\"title\":\"Hello from connector\",\"body\":\"Created via API\"}"
```

On success you get `201 Created` with a normalized issue payload (`id`, `number`, `title`, `state`, `html_url`, `body`).

### List commits

| Method | Path                       | Description |
|--------|----------------------------|-------------|
| GET    | `/commits/{owner}/{repo}`  | Recent commits as a simplified list |

Query parameters:

| Param       | Default | Description |
|-------------|---------|-------------|
| `sha`       | _(omit)_ | Branch name or commit SHA to start from (passed through to GitHub). |
| `per_page` | `10`    | How many commits (1–100). |

Each item includes `sha`, `author_name`, `message`, and `date` (ISO timestamp from commit metadata, when present).

**Example**

```bash
curl "http://127.0.0.1:8000/commits/microsoft/vscode?per_page=5"
```

```bash
curl "http://127.0.0.1:8000/commits/octocat/Hello-World?sha=master&per_page=10"
```

### Create a pull request

| Method | Path                    | Description |
|--------|-------------------------|-------------|
| POST   | `/create-pull-request`  | JSON: `owner`, `repo`, `title`, `head`, `base`, optional `body` |

**Example**

```bash
curl -X POST http://127.0.0.1:8000/create-pull-request ^
  -H "Content-Type: application/json" ^
  -d "{\"owner\":\"your-user\",\"repo\":\"your-repo\",\"title\":\"Add feature\",\"head\":\"feature-branch\",\"base\":\"main\",\"body\":\"Optional description\"}"
```

On success you get `201 Created` with `id`, `title`, `state`, and `url` (browser URL for the PR).

## Error handling

- Missing or invalid JSON fields on `POST /create-issue` or `POST /create-pull-request` → **422** with validation detail from FastAPI.
- Invalid `per_page` on `GET /commits/...` (outside 1–100) → **422**.
- Unknown user / repo / insufficient permissions → GitHub status (e.g. **404**, **403**) with GitHub’s `message` in `detail`.
- Invalid or expired token → typically **401** with `Bad credentials` (or similar) from GitHub.
- **OAuth mode:** GitHub API calls before `/auth/callback` completes → **401** with instructions to open `/auth/login`. Invalid or expired `state` on callback → **400**. GitHub rejects the authorization code → **400** with `error_description` when present.

## Security notes

- Never commit `.env` or embed tokens in code.
- Prefer fine-grained tokens scoped to the minimum repositories and permissions required.
- OAuth: the callback returns `access_token` in JSON for **local demos only**; in production prefer server-side sessions and avoid exposing tokens to the browser when possible.

## License

Use and modify as needed for your organization.
