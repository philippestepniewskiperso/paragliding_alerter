# Paralert — Agent Guide

Outil d'alerte parapente: notifie via ntfy.sh quand les conditions de vent sont calmes (créneaux de 3h, par altitude) sur des sommets configurés. Données: Open-Meteo API. Déployé via Docker sur Zotac home server.

---

## Stack

- **Python 3.12**, **uv** (pas pip, pas requirements.txt)
- **FastAPI** + **Pydantic v2** + **uvicorn**
- **SQLite** (stockage config + historique checks)
- **APScheduler** (cron daily check)
- **httpx** (HTTP async: Open-Meteo + ntfy.sh)
- **Alpine.js** (front single-page, zéro build, servi par FastAPI)
- **pytest** + **respx** + **pytest-playwright** (pyramide de tests)

---

## Architecture hexagonale

Le code suit le principe de l'architecture hexagonale.
---

## Domaine clé

### Créneaux (CalmSlot)
- Fenêtre de **3h** (00h-03h, 03h-06h, …, 21h-24h UTC)
- Calme = toutes les heures du créneau, à **toutes** les altitudes configurées, vent ≤ seuil
- Chaque créneau contient par altitude: `mean_speed_kmh`, `max_speed_kmh`, `mean_direction_deg`
- Direction: moyenne circulaire (pas arithmétique)

### Altitudes → pression Open-Meteo
| Altitude | Niveau hPa |
|----------|-----------|
| 2000 m   | 800 hPa   |
| 3000 m   | 700 hPa   |
| 4000 m   | 600 hPa   |

### SQLite
- DB path: `DB_PATH` env var (défaut `/data/paralert.db`)
- `init_db()` gère migration automatique (ex: colonne `calm_hours` → `calm_slots`)
- Chaque connexion = nouvelle instance `sqlite3.connect()`, pas de pool
- **Important**: ne pas appeler `self.get()` dans un `with _connect() as conn:` séparé — la transaction n'est pas encore committée

---

## API REST

```
GET  /api/summits/            → list[SummitRead]
POST /api/summits/            → SummitRead  (201)
PUT  /api/summits/{id}        → SummitRead
DEL  /api/summits/{id}        → 204
PATCH /api/summits/{id}/toggle → SummitRead

GET  /api/settings/           → AppSettingsRead
PUT  /api/settings/           → AppSettingsRead  (reschedule cron si changé)

POST /api/checks/now          → {started: true}  (202, background task)
GET  /api/checks/last         → list[CheckResultRead]

GET  /                        → index.html (Alpine.js UI)
```

---

## Tests

```
tests/
├── unit/domain/test_services.py          # find_calm_slots(), max_wind() — 0 I/O, 0 mock
├── integration/adapters/test_sqlite.py   # tmp_path DB (pas :memory: — connexions séparées)
├── integration/adapters/test_open_meteo.py  # respx mock HTTP
├── integration/application/test_check_conditions.py  # FakeWeather + FakeNotifier
└── e2e/
    ├── test_api.py      # FastAPI TestClient, tmp_path DB
    └── test_frontend.py # Playwright Chromium headless, live uvicorn sur port 19080
```

**Règles tests:**
- Tests SQLite: toujours `tmp_path / "test.db"`, jamais `:memory:` (connexions indépendantes → table vide)
- Tests async: `@pytest.mark.anyio` (pas `@pytest.mark.asyncio`)
- `pytest.ini_options asyncio_mode = "auto"` dans `pyproject.toml`

---

## Commandes

```bash
make              # install + lance serveur :8080
make dev          # serveur seul (DB_PATH=./data/paralert.db)
make test         # tous les tests
make test-unit    # tests unitaires
make test-int     # tests intégration
make test-e2e     # tests API
make test-front   # tests Playwright
make check        # smoke test (serveur doit tourner)
make docker-up    # docker compose up
```

---

## Guidelines

- Sauvegarde les features, découvertes, bug fixes, décisions dans ta mémoire engram.
- Avant de coder, regarde si tu as pas des informations dans ta mémoire engram qui pourraient t'aider 

## Conventions

- **Pas de commentaires** sauf invariant non-obvieux
- **Pas de code défensif**: pas de try/except génériques, pas de None checks inutiles
- **Commits one-liner**, pas de Co-Authored-By
- `uv add <pkg>` pour ajouter une dépendance (pas pip)
- `uv add --dev <pkg>` pour les dépendances de dev
- Après `uv add`: relancer `uv pip install -e .` si package pas importable
- Debug l'UI en utilisant playwright

---

## Config runtime (env vars)

| Var | Défaut | Description |
|-----|--------|-------------|
| `DB_PATH` | `/data/paralert.db` | Chemin SQLite |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | Port HTTP |

Config applicative (ntfy, seuil vent, cron) stockée en DB, modifiable via UI.
