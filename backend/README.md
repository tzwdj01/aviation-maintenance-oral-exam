# Backend

Sprint 1A implements a model-independent, auditable backend foundation.  It deliberately contains no
exam UI or production worker deployment; state changes, score computation, provider selection and audit
records are all server-owned.

Run locally after installing dependencies:

```bash
python -m pip install -e .
python -m pip install pytest ruff
cd backend && alembic upgrade head
uvicorn app.main:app --reload
```
