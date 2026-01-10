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
- `lib/sentinel.py` - Sentinel types (`NotSet`) for update operations

**Core Functions:**

Each entity module provides three core functions: `get()`, `create()`, and `update()`.

**get() - Unified Lookup with Overloads:**

Use `@t.overload` decorators to provide type-safe return values based on parameters. All `typing` members must be accessed through the `t` alias:

```python
import typing as t
import sqlalchemy as sqla

@t.overload
def get(*, user_id: UserID, with_memberships: t.Literal[False] = ..., session: Session = ...) -> User | None: ...
@t.overload
def get(*, user_id: UserID, with_memberships: t.Literal[True], session: Session = ...) -> UserWithMemberships | None: ...
@t.overload
def get(*, email: str, with_memberships: t.Literal[False] = ..., session: Session = ...) -> User | None: ...
@t.overload
def get(*, email: str, with_memberships: t.Literal[True], session: Session = ...) -> UserWithMemberships | None: ...

def get(
    *,
    user_id: UserID | None = None,
    email: str | None = None,
    with_memberships: bool = False,
    session: Session = di.Provide["storage.persistent.session"],
) -> User | UserWithMemberships | None:
    """Get a user by ID or email. Exactly one lookup key must be provided."""
    stmt = sqla.select(users.__table__).where(users.user_id == user_id)
    # ...
```

**create() - Explicit Keyword Arguments:**

Use explicit keyword arguments instead of TypedDict params. Handle any internal transformations (like password hashing):

```python
def create(
    *,
    email: str,
    name: str,
    password: p.Secret[str] | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> User:
    """Create a new user. Password is hashed internally using bcrypt."""
    password_hash = None
    if password is not None:
        password_hash = bcrypt.hashpw(
            password.get_secret_value().encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    row = users(user_id=UserID(), email=email, name=name, password_hash=password_hash)
    session.add(row)
    session.flush()
    return User.model_validate(row)
```

**update() - NotSet Sentinel Pattern:**

Use `NotSet` sentinel to distinguish "not provided" from `None`. Raise `KeyError` if entity not found. Use `isinstance()` for type narrowing (not `is not NotSet()`):

```python
from socratic.lib import NotSet

def update(
    user_id: UserID,
    *,
    email: str | NotSet = NotSet(),
    name: str | NotSet = NotSet(),
    password: p.Secret[str] | None | NotSet = NotSet(),
    add_memberships: set[MembershipParams] | None = None,
    remove_memberships: set[OrganizationID] | None = None,
    with_memberships: bool | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> User | UserWithMemberships:
    """Update a user. Raises KeyError if user_id not found."""
    # Build update dict only for non-NotSet values (use isinstance for type narrowing)
    update_values: dict[str, t.Any] = {}
    if not isinstance(email, NotSet):
        update_values["email"] = email
    if not isinstance(name, NotSet):
        update_values["name"] = name
    # ... handle password hashing ...

    # Always issue SQL UPDATE (even if empty) to verify entity exists
    result = session.execute(
        sqla.update(users).where(users.user_id == user_id).values(**update_values)
    )
    if result.rowcount == 0:
        raise KeyError(user_id)

    # Handle relation changes (add_memberships, remove_memberships)
    # ...

    # Return with optional relation loading based on with_memberships
```

**Conventions:**

- Repository functions are pure functions, not methods on a class
- Use keyword-only arguments (`*,`) for clarity
- Session is a keyword argument with DI default (last parameter)
- `get()` returns `None` for missing entities
- `update()` raises `KeyError` for missing entities (must exist to update)
- Use `*With{Relation}` suffix for joined return models (e.g., `UserWithMemberships`)
- Use `p.BaseModel` with `frozen=True` and explicit `__hash__` for hashable parameter types used in sets:

  ```python
  class MembershipCreateParams(p.BaseModel):
      """For adding memberships - both fields required."""
      model_config = p.ConfigDict(frozen=True)
      organization_id: OrganizationID
      role: UserRole

      def __hash__(self) -> int:
          return hash((self.organization_id, self.role))

  class MembershipRemoveParams(p.BaseModel):
      """For removing memberships - role is optional.

      If role is None, removes all memberships for the organization.
      If role is specified, only removes the membership with that role.
      """
      model_config = p.ConfigDict(frozen=True)
      organization_id: OrganizationID
      role: UserRole | None = None

      def __hash__(self) -> int:
          return hash((self.organization_id, self.role))
  ```

- Access all `typing` members through the `t` alias (e.g., `t.Literal`, `t.overload`)
- Import sqlalchemy as `sqla` (e.g., `sqla.select()`, `sqla.update()`)
- Flush after writes to get generated values (IDs, timestamps)

**Design Rationale:**

1. **Functional over OOP** - Pure functions with explicit dependencies are cleaner than repository classes. No instance state to manage, easier to test, and the dependency is explicit at the call site.

2. **Clear data boundaries** - SQLAlchemy models stay internal to the storage layer while Pydantic models define the API contract. This prevents ORM implementation details from leaking into the rest of the application.

3. **Explicit loading** - The `with_memberships` parameter and `*WithRelation` return types make it obvious when you're doing a joined query vs. a simple fetch. No magic lazy loading that triggers N+1 queries.

4. **NotSet over None** - The sentinel pattern allows distinguishing "set this field to None" from "don't change this field", which is essential for nullable fields in update operations.

5. **KeyError for updates** - Updates should fail explicitly if the entity doesn't exist. This catches bugs where code assumes an entity exists but it was deleted.

6. **Overloads for type safety** - Using `@overload` with `Literal` types lets pyright infer the correct return type based on how the function is called.

## Code Style Guide

### Python

- **Python 3.13+** required
- **Type hints**: Strict pyright mode, annotate everything
- **Formatting**: `nix fmt` runs ruff format + isort
- **Imports**: isort with black profile, deterministic ordering (`--dt`)
- **Docstrings**: Only where logic isn't self-evident
- **Explicit inheritance**: Class inheritance must be explicit, even when ancestor is `object`:

```python
# Good: Explicit inheritance
class TestGet(object):
    ...

# Bad: Implicit inheritance
class TestGet:
    ...
```

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

| Service        | Purpose              | Default  |
| -------------- | -------------------- | -------- |
| `postgres`     | PostgreSQL database  | disabled |
| `memcached`    | Cache server         | disabled |
| `rabbitmq`     | Message queue        | disabled |
| `example-api`  | Production backend   | disabled |
| `example-dev`  | Dev backend (reload) | enabled  |
| `example-vite` | Vite frontend        | enabled  |

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

## Testing

### Running Tests

```bash
# Ensure PostgreSQL is running and test database exists
pg_isready
createdb socratic_test 2>/dev/null || true
socratic-cli -E test schema upgrade

# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_organization_api.py -v
```

### Test Database

Tests use a separate `socratic_test` database configured in `config/env.d/test/storage.yaml`. The test environment uses `DeploymentEnvironment.Test` which loads file-based secrets (no AWS).

### Transaction Rollback Pattern

API integration tests use transaction rollback for isolation. Each test runs within a transaction that is rolled back after the test completes, ensuring:

- Tests don't pollute the database
- Tests are isolated from each other
- No manual cleanup required

**How it works:**

1. `db_session` fixture creates a connection with an outer transaction
2. Session uses `join_transaction_mode="create_savepoint"` so `session.begin()` creates savepoints instead of failing
3. `client` fixture overrides the DI container's session provider
4. After test completion, the outer transaction is rolled back

```python
# tests/conftest.py pattern
@pytest.fixture
def db_session(container: SocraticContainer) -> t.Generator[Session]:
    engine = container.storage().persistent().engine()
    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autobegin=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### Factory Fixtures

Use factory fixtures to create test data with sensible defaults:

```python
@pytest.fixture
def org_factory(db_session: Session) -> t.Callable[..., Organization]:
    def create_organization(
        name: str = "Test Organization",
        slug: str | None = None,
    ) -> Organization:
        # Generate unique slug if not provided
        org_id = OrganizationID()
        if slug is None:
            slug = f"test-org-{org_id.key[:8]}"

        with db_session.begin():
            org = organizations(organization_id=org_id, name=name, slug=slug)
            db_session.add(org)
            db_session.flush()

            stmt = select(organizations.__table__).where(...)
            row = db_session.execute(stmt).mappings().one()
            return Organization(**row)

    return create_organization

# Usage in tests
def test_something(org_factory):
    org = org_factory(name="My Org", slug="my-org")
```

### Writing API Tests

```python
class TestGetOrganizationBySlug:
    def test_returns_organization_for_valid_slug(
        self,
        client: TestClient,
        test_org: Organization,
    ) -> None:
        response = client.get(f"/api/organizations/by-slug/{test_org.slug}")

        assert response.status_code == 200
        data = response.json()
        assert data["organization_id"] == str(test_org.organization_id)

    def test_returns_404_for_nonexistent_slug(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/api/organizations/by-slug/nonexistent")

        assert response.status_code == 404
```

**Conventions:**

- Group related tests in classes named `Test{Endpoint}`
- Use descriptive test names: `test_{expected_behavior}_for_{condition}`
- Use `test_org` fixture for simple cases, `org_factory` for multiple entities
- Assert both status codes and response body content

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

| Type             | Convention      | Example            |
| ---------------- | --------------- | ------------------ |
| Python modules   | snake_case      | `user_service.py`  |
| Config files     | snake_case.yaml | `storage.yaml`     |
| React components | PascalCase.tsx  | `UserProfile.tsx`  |
| CSS              | kebab-case.css  | `user-profile.css` |
| TypeScript       | camelCase.ts    | `apiClient.ts`     |

## Environment Variables

Set by devshell (`flake.nix`):

| Variable           | Purpose                      |
| ------------------ | ---------------------------- |
| `XDG_STATE_HOME`   | State directory (`.state/`)  |
| `PGDATA`           | PostgreSQL data directory    |
| `PGHOST`           | PostgreSQL socket directory  |
| `RABBITMQ_*`       | RabbitMQ configuration       |
| `PYTHONBREAKPOINT` | Debugger (`jdbpp.set_trace`) |
| `PRE_COMMIT_HOME`  | Pre-commit cache             |

Runtime (set by CLI):

| Variable          | Purpose                                |
| ----------------- | -------------------------------------- |
| `__Socratic_BOOT` | Serialized boot config for web workers |
