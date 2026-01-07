# Socratic

Learning evalaution and reinforcement system.

## Quick Reference

### Commands
```bash
dev                              # Start all dev services (process-compose)
generate-api-clients             # Generate TypeScript API clients from OpenAPI
install-hooks                    # Install pre-commit hooks

socratic-cli web develop <app>   # Dev server with live-reload
socratic-cli web serve <app>     # Production server
socratic-cli schema upgrade      # Run database migrations
```

## Project Structure

```
socratic/
├── config/                     # YAML configuration files
│   ├── env.d/{env}/           # Environment-specific overrides
│   ├── logging.yaml
│   ├── storage.yaml
│   ├── web.yaml
│   └── vendor.yaml
├── migrations/                 # Alembic database migrations
├── socratic/
│   ├── cli/                   # Click CLI commands
│   │   ├── __main__.py       # Entry point (socratic-cli)
│   │   ├── web.py            # Web server commands
│   │   └── schema.py         # Database schema commands
│   ├── core/                  # Framework core
│   │   ├── config/           # Settings & configuration sources
│   │   ├── container/        # DI containers
│   │   ├── di.py             # Dependency injection wrapper
│   │   ├── logging.py        # Logging setup
│   │   └── provider.py       # Service providers
│   ├── lib/                   # Utility libraries
│   │   ├── cli.py            # Click extensions
│   │   ├── sql/              # SQLAlchemy helpers
│   │   ├── logging/          # Log formatters
│   │   └── debug.py          # Remote debugging
│   ├── model/                 # Pydantic models
│   │   ├── base.py           # BaseModel, timestamps
│   │   ├── id.py             # ShortUUIDKey types
│   │   └── {entity}.py       # Domain models
│   ├── storage/               # Database layer
│   │   ├── table.py          # SQLAlchemy table definitions
│   │   ├── type.py           # Custom column types
│   │   └── {entity}.py       # Repository functions
│   ├── typings/               # Type stubs for untyped deps
│   └── web/{app}/             # Web applications
│       ├── main.py           # FastAPI app factory
│       ├── route/            # API routes
│       ├── view/             # View models
│       └── frontend/         # React/Vite app
├── flake.nix                  # Nix devshell + formatter config
├── pyproject.toml             # Poetry project config
└── process-compose.yaml       # Dev service orchestration
```

## Architecture Patterns

### Dependency Injection

The project uses `dependency-injector` with custom extensions in `core/di.py`:

```python
from socratic.core import di

@di.inject
def handler(
    service: MyService = di.Provide["container.path"],
    # With type casting:
    config: Settings = di.Provide["config.web", di.as_(Settings)],
):
    pass

# Resource management (auto-closing)
Manage[DatabaseSession]  # Equivalent to Closing[Provide[...]]
```

**AutoLoader**: Automatic module wiring on import for specified packages.

### Configuration System

The configuration system uses Pydantic Settings with custom sources to load typed configuration from YAML files, with environment-specific overrides and encrypted secrets.

**Core Concepts:**

1. **Field-to-file mapping** - Each field on the root `Settings` class corresponds to a YAML file:

```python
# core/config/settings.py
class Settings(BaseSettings):
    root: FileUrl              # Passed at init
    env: DeploymentEnvironment # Passed at init
    override: tuple[str, ...]  # Passed at init

    logging: LoggingSettings   # Loads from config/logging.yaml
    storage: StorageSettings   # Loads from config/storage.yaml
    web: WebSettings           # Loads from config/web.yaml
```

2. **Source priority** (highest to lowest):
   - **Init settings**: `root`, `env`, `override` passed directly to container
   - **YAML cascading**: Base config + environment-specific overrides
   - **CLI overrides**: `-o key.path=value` flags parsed into nested structure

3. **Environment cascading** - Base config in `config/`, environment overrides in `config/env.d/{env}/`:

```
config/
├── logging.yaml              # Base config (always loaded)
├── storage.yaml
├── web.yaml
└── env.d/
    ├── development/
    │   └── storage.yaml      # Overrides for development
    ├── staging/
    │   └── storage.yaml
    └── production/
        └── storage.yaml
```

For `DeploymentEnvironment.Local`, only base config is loaded. For other environments, the env-specific file takes precedence if it exists.

**CLI Overrides:**

Override any nested config value via dot-notation:

```bash
socratic-cli -o storage.postgresql.port=5433 schema upgrade
socratic-cli -o "web.example.backend.host=0.0.0.0" web serve example
socratic-cli -o debug=true -o storage.postgresql.database=test cmd
```

Values are parsed as YAML, so `true`/`false`, numbers, and quoted strings work as expected.

**Secrets (Ansible Vault):**

Secrets are handled separately via `Secrets` class with `AnsibleVaultSecretsSource`. The vault password is prompted once and cached in the kernel keyring via `keyctl` for the session.

```bash
# Create vault file
ansible-vault create config/secrets.vault.yaml

# Edit vault
ansible-vault edit config/secrets.vault.yaml
```

**Accessing Configuration:**

Via dependency injection:

```python
from socratic.core import di
from socratic.core.config import StorageSettings

@di.inject
def handler(
    storage_cf: StorageSettings = di.Provide["config.storage", di.as_(StorageSettings)],
):
    port = storage_cf.persistent.postgresql.port
```

**Design Rationale:**

- **File-per-concern** - Each settings class gets its own YAML file, making configuration modular and easier to manage in version control
- **Type safety** - Pydantic validates all config at boot time, catching errors early
- **Environment layering** - Base config with environment overrides avoids duplication while allowing environment-specific tuning
- **CLI overrides** - Development flexibility without editing files; useful for testing and debugging
- **Vault integration** - Secrets stay encrypted at rest, decrypted only in memory, with password caching for developer convenience

### Container Boot Sequence

```python
SocraticContainer.boot(
    env=DeploymentEnvironment.Local,
    root=Path("/app"),
    config_root="file:///app/config",
    override=("-o", "debug=true"),
)
```

1. Load settings from YAML sources
2. Apply CLI overrides
3. Wire DI container to packages
4. Initialize logging
5. Load secrets (vault or AWS)
6. Register AutoLoader for web modules

### Model ID Pattern

Custom `ShortUUIDKey` for prefixed, readable IDs:

```python
class UserID(ShortUUIDKey, prefix="user"):
    pass

# Creates IDs like: user$7Bj3KpVxMnQwRtYz2sLa
user_id = UserID()           # Generate new
user_id = UserID(key="...")  # From existing key
```

- 22-character base57 encoded UUID
- Prefix for type safety and debugging
- SQLAlchemy TypeDecorator for storage

### Storage/Repository Pattern

The storage layer uses a functional repository pattern with SQLAlchemy for queries and Pydantic models for typed inputs/outputs.

**Structure:**
- `storage/table.py` - SQLAlchemy table definitions
- `storage/{entity}.py` - Repository functions for each entity

**Repository Functions:**

Functions take either direct attributes or structured Pydantic parameter models, and return Pydantic models:

```python
# storage/user.py
from socratic.model.user import User, UserCreateParams, UserWithOrg

def create_user(session: Session, params: UserCreateParams) -> User:
    """Create a new user from structured params."""
    row = users(
        user_id=UserID(),
        email=params.email,
        name=params.name,
    )
    session.add(row)
    session.flush()
    return User.model_validate(row)

def get_user(session: Session, user_id: UserID) -> User | None:
    """Get user by ID with direct attribute."""
    row = session.get(users, user_id)
    return User.model_validate(row) if row else None
```

**Conventions:**
- Repository functions are pure functions, not methods on a class
- Session is always the first parameter
- Return `None` for missing entities, not exceptions
- Use `*Params` suffix for input models (e.g., `UserCreateParams`)
- Use `*With{Relation}` suffix for joined return models (e.g., `UserWithOrg`)
- Flush after writes to get generated values (IDs, timestamps)

**Design Rationale:**

1. **Functional over OOP** - Pure functions with session as the first parameter is cleaner than repository classes with injected sessions. No instance state to manage, easier to test, and the dependency is explicit at the call site.

2. **Clear data boundaries** - SQLAlchemy models stay internal to the storage layer while Pydantic models define the API contract. This prevents ORM implementation details from leaking into the rest of the application.

3. **Explicit loading** - The `*WithRelation` variants make it obvious when you're doing a joined query vs. a simple fetch. No magic lazy loading that triggers N+1 queries unexpectedly.

4. **None over exceptions** - Returning `None` for missing entities is more Pythonic for expected "not found" cases and composes better with Optional handling.

## Code Style Guide

### Python

- **Python 3.13+** required
- **Type hints**: Strict pyright mode, annotate everything
- **Formatting**: `nix fmt` runs ruff format + isort
- **Imports**: isort with black profile, deterministic ordering (`--dt`)
- **Docstrings**: Only where logic isn't self-evident

```bash
# Format all files
nix fmt

# Check formatting without modifying (CI)
nix flake check
```

```python
# Good: Type hints, descriptive names
def get_user_by_id(user_id: UserID, session: Session) -> User | None:
    return session.get(User, user_id)

# Avoid: Unnecessary comments, overly defensive code
def get_user_by_id(user_id: UserID, session: Session) -> User | None:
    # Get user from database  <- unnecessary
    if user_id is None:       # <- can't happen with type hints
        return None
    return session.get(User, user_id)
```

### Pydantic Models

```python
class User(BaseModel):
    user_id: UserID
    email: EmailStr
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Use Field for validation, not comments
    age: int = Field(ge=0, le=150)
```

### SQLAlchemy Tables

```python
class users(base):
    __tablename__ = "users"

    user_id: Mapped[UserID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

### FastAPI Routes

```python
@router.get("/users/{user_id}")
@di.inject
def get_user(
    user_id: UserID,
    session: Manage[Session] = di.Provide["storage.persistent.session"],
) -> UserResponse:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return UserResponse.model_validate(user)
```

### TypeScript/React

- **React 19** with TypeScript strict mode
- **Tailwind CSS 4** for styling
- **ESLint** with React plugins
- Generated API clients via `openapi-ts`

```typescript
// Use generated API client
import { client } from './api/sdk.gen';
import { User } from './api/types.gen';

const user = await client.getUser({ userId: 'user$...' });
```

## Development Workflow

### Starting Development

```bash
# Enter nix shell (automatic with direnv)
cd socratic/

# Install hooks
install-hooks

# Start services
dev  # or: process-compose up
```

### Process Compose Services

| Service | Purpose | Default |
|---------|---------|---------|
| `postgres` | PostgreSQL database | disabled |
| `memcached` | Cache server | disabled |
| `rabbitmq` | Message queue | disabled |
| `example-api` | Production backend | disabled |
| `example-dev` | Dev backend (reload) | enabled |
| `example-vite` | Vite frontend | enabled |

Enable services: `process-compose up --enable postgres`

### CLI Usage

```bash
# Global options (before subcommand)
socratic-cli -E production web serve example  # Set environment
socratic-cli -c /etc/socratic/config web serve  # Custom config root
socratic-cli -D web develop example           # Debug mode
socratic-cli -o key=value -o other=val cmd    # Override config values

# Web commands
socratic-cli web serve example                # Production server
socratic-cli web serve example -w 4           # With 4 workers
socratic-cli web develop example              # Dev server with reload

# Schema commands
socratic-cli schema upgrade                   # Apply migrations
socratic-cli schema revision -m "add users"   # Create migration
```

### API Client Generation

```bash
generate-api-clients
# Starts API servers, generates TypeScript clients, stops servers
```

Or manually:
```bash
socratic-cli web serve example &
cd socratic/web/example/frontend
npx openapi-ts
```

### Database Migrations

```bash
# Create migration
socratic-cli schema revision -m "add users table"

# Apply migrations
socratic-cli schema upgrade

# Rollback
socratic-cli schema downgrade -1
```

## Secrets Management

### Vault File Structure

```yaml
# config/secrets.vault.yaml (encrypted)
postgresql:
  username: app_user
  password: secret123

google:
  service_account:
    private_key: |
      -----BEGIN PRIVATE KEY-----
      ...
```

### Environment-Specific Secrets

```
config/
├── secrets.vault.yaml           # Local/shared secrets
└── env.d/
    ├── development/
    │   └── secrets.vault.yaml   # Dev-specific
    ├── staging/
    │   └── secrets.vault.yaml
    └── production/
        └── secrets.vault.yaml
```

## Commit Convention

Commits must follow conventional commit format:

```
{type}({scope}): {description}

{body}

{footer}
```

**Types**: `feat`, `fix`, `docs`, `chore`, `revise`, `wip`

```bash
# Good
feat(api): add user registration endpoint
fix(storage): handle null timestamps in migration
chore(deps): update fastapi to 0.115

# Bad
refactor(api): ...  # 'refactor' not allowed, use 'revise'
Add feature         # missing type
```

## Debugging

### Python Debugger

```python
# Configured via PYTHONBREAKPOINT=jdbpp.set_trace
breakpoint()  # Drops into jdbpp debugger
```

### Remote Debugging

The `develop` command wraps the server in a remote debugger context:
```python
with debug.remote_debugger():
    uvicorn.run(...)
```

### SQL Query Logging

Debug mode (`-D` flag) enables SQL logging with formatted output via `sql_formatter`.

## Common Issues

### "Module not found" after adding dependency

```bash
poetry install
# Then restart dev server
```

### Type errors with injected dependencies

Ensure `di.as_(Type)` is used when the provider returns a different type:
```python
config: Settings = di.Provide["config", di.as_(Settings)]
```

### Vault password prompt hanging

The vault file doesn't exist - create it first:
```bash
ansible-vault create config/secrets.vault.yaml
```

### Frontend API types outdated

Regenerate the client:
```bash
generate-api-clients
```

## File Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Python modules | snake_case | `user_service.py` |
| Config files | snake_case.yaml | `storage.yaml` |
| React components | PascalCase.tsx | `UserProfile.tsx` |
| CSS | kebab-case.css | `user-profile.css` |
| TypeScript | camelCase.ts | `apiClient.ts` |

## Environment Variables

Set by devshell (`flake.nix`):

| Variable | Purpose |
|----------|---------|
| `XDG_STATE_HOME` | State directory (`.state/`) |
| `PGDATA` | PostgreSQL data directory |
| `PGHOST` | PostgreSQL socket directory |
| `RABBITMQ_*` | RabbitMQ configuration |
| `PYTHONBREAKPOINT` | Debugger (`jdbpp.set_trace`) |
| `PRE_COMMIT_HOME` | Pre-commit cache |

Runtime (set by CLI):

| Variable | Purpose |
|----------|---------|
| `__Socratic_BOOT` | Serialized boot config for web workers |
