# Campaory: Architecture

Version 1.1, 16 Oct 2026. Diagrams are Mermaid. In VS Code install "Markdown Preview Mermaid Support". Diagrams were not rendered or syntax-checked offline; fix any that fail to render.

## 1. System context

```mermaid
flowchart LR
    subgraph Visitor["Visitor (guest or signed in)"]
        B["Browser<br/>React SPA + localStorage"]
    end

    subgraph Render["Render (single web service, Docker)"]
        API["FastAPI app<br/>/api/*  +  static SPA"]
    end

    DB[("PostgreSQL<br/>users, campaigns, facts,<br/>plan items, posts, versions")]
    LLM["Gemma<br/>(Google AI Studio API)"]
    OAUTH["Google OAuth<br/>(GitHub optional)"]
    WEB["Public event web pages"]
    SENTRY["Sentry (optional)"]
    SOCIAL["LinkedIn / Instagram / WhatsApp / X<br/>(opened by the user's browser)"]

    B -- "HTTPS JSON" --> API
    API -- "SQL (signed-in users only)" --> DB
    API -- "generate JSON" --> LLM
    API -- "OIDC code flow" --> OAUTH
    API -- "guarded fetch (SSRF-safe)" --> WEB
    API -. "traces, errors" .-> SENTRY
    B -- "share intent / copy text" --> SOCIAL
```

Key points:
- Guests never touch the database. The guest campaign lives in the browser; the API is stateless for guests.
- The user's browser opens the social platforms. Campaory never posts on the user's behalf.
- One deployable unit: FastAPI serves both `/api/*` and the built React app.

## 2. Containers and modules

```mermaid
flowchart TB
    subgraph SPA["frontend/ (React 18, Vite, TypeScript)"]
        R["Routes<br/>Start, Facts, Plan, Posts, Changes, Campaigns"]
        ST["Store (Zustand)<br/>campaign doc + persist to localStorage"]
        AC["API client<br/>fetch wrapper, error mapping"]
        UI["Components + tokens.css"]
        R --> ST --> AC
        R --> UI
    end

    subgraph APIAPP["backend/app (FastAPI)"]
        RT["api/ routers"]
        DOM["domain/<br/>facts, planning, platforms,<br/>guard, impact"]
        LLMX["llm/<br/>base, gemma, ollama, mock, prompts"]
        FET["fetch/<br/>safe_fetch, extract_text"]
        CORE["core/<br/>rate_limit, security, sentry, config"]
        REPO["db/<br/>models, session, repo"]
        RT --> DOM
        RT --> LLMX
        RT --> FET
        RT --> CORE
        RT --> REPO
        DOM -. "pure functions, no I/O" .- DOM
    end

    AC -- "/api" --> RT
```

Rules of the road:
- `domain/` has no I/O and no framework imports. Everything deterministic and testable lives there.
- `llm/` is the only place that knows a model exists. The rest of the code calls `LLMProvider.generate_json`.
- The LLM never decides dates, limits, links or statuses. See ADR-005.

## 3. Guest workflow (no account)

```mermaid
sequenceDiagram
    actor U as Visitor
    participant SPA as React SPA
    participant API as FastAPI
    participant WEB as Event page
    participant LLM as Gemma

    U->>SPA: Paste URL / text, or "Try a sample event"
    SPA->>API: POST /api/brief/extract
    API->>WEB: guarded fetch (SSRF + robots checks)
    API->>LLM: extract_facts (JSON)
    LLM-->>API: candidate facts with snippets
    API-->>SPA: facts (needs_review) + source meta
    U->>SPA: Confirm / edit facts (BR01 gate)
    SPA->>API: POST /api/plan/propose (confirmed facts)
    API-->>SPA: plan items (dates computed in code)
    U->>SPA: Adjust plan
    SPA->>API: POST /api/posts/generate
    API->>LLM: generate_posts (confirmed facts only)
    API->>API: guard + platform validators
    API-->>SPA: posts (draft or needs_review)
    U->>SPA: Edit, approve, copy, open platform
    Note over SPA: Every change is written to localStorage
```

## 4. Sign in and save

```mermaid
sequenceDiagram
    actor U as Visitor
    participant SPA as React SPA
    participant API as FastAPI
    participant G as Google OAuth
    participant DB as PostgreSQL

    U->>SPA: Click "Save"
    SPA->>SPA: Keep guest campaign in localStorage
    SPA->>API: GET /api/auth/login/google
    API-->>U: 302 to Google
    U->>G: Consent
    G-->>API: GET /api/auth/callback/google?code=...
    API->>DB: upsert user (provider, sub)
    API-->>U: Set session cookie, 302 to /?saved=pending
    SPA->>API: GET /api/me
    SPA->>API: POST /api/campaigns (guest doc + client_id)
    API->>DB: insert campaign tree (idempotent on user_id + client_id)
    API-->>SPA: campaign id, version 1
    SPA->>SPA: Clear guest copy, route to /c/{id}/...
```

## 5. Change impact

```mermaid
sequenceDiagram
    actor U as Organizer
    participant SPA as React SPA
    participant API as FastAPI
    participant LLM as Gemma

    U->>SPA: Edit confirmed fact (start_at 10:00 to 09:30)
    SPA->>API: POST /api/impact/analyze (posts, changed key, old value)
    API-->>SPA: affected unpublished posts, protected published posts
    SPA->>SPA: Mark affected posts needs_review
    loop each affected post (max 3 in parallel)
        SPA->>API: POST /api/impact/redraft
        API->>LLM: redraft_post (changed fact only)
        API->>API: guard
        API-->>SPA: proposal (text, reason)
    end
    U->>SPA: Accept update or keep current text
```

## 6. Post status machine

```mermaid
stateDiagram-v2
    [*] --> draft: generated and guard passed
    [*] --> needs_review: generated with placeholder or guard failure
    draft --> approved: user approves (all preconditions met)
    needs_review --> approved: user fixes and approves
    approved --> needs_review: a fact it uses changes
    draft --> needs_review: a fact it uses changes
    scheduled --> needs_review: a fact it uses changes
    approved --> scheduled: reminder set (future time)
    scheduled --> approved: reminder cleared
    approved --> published: user marks published
    scheduled --> published: user marks published
    published --> published: never rewritten
```

## 7. Deployment

```mermaid
flowchart LR
    GH["GitHub repo"] -- "push" --> R["Render<br/>Docker web service"]
    R --> P[("Render Postgres")]
    R --> DOM["your-name.tech<br/>custom domain"]
    DEV["Developer machine<br/>uvicorn + vite dev"] -. "same code" .- GH
```

The Dockerfile builds the frontend in a Node stage and copies `frontend/dist` into the Python image. See `render.yaml`.

## 8. Quality attributes

| Attribute | How the architecture delivers it |
|---|---|
| Trust in facts | Confirmed-facts-only prompts, deterministic guard, BR01/BR02 gates |
| Privacy | Guest data never stored server-side; saved data only after sign-in; delete account |
| Cost control | Rate limits per IP and user, daily cap, mock fallback |
| Replaceable model | `LLMProvider` adapter, provider chosen by env |
| Simplicity | One service, one database, no queue, no worker |
| Testability | Pure domain functions, mock provider, stateless guest endpoints |

Known limits: the rate limiter is in memory, so it assumes one instance. Scaling to several instances needs a shared store (see HLD section 9).
