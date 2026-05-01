"""Background task primitives (arq worker settings; not started by the v3 FastAPI app)."""

from ai.tasks.names import BackgroundJobId
from ai.tasks.worker import REDIS_SETTINGS, WorkerSettings

__all__ = ["BackgroundJobId", "REDIS_SETTINGS", "WorkerSettings"]

from ai.tasks.worker import REDIS_SETTINGS, WorkerSettings

__all__ = ["REDIS_SETTINGS", "WorkerSettings"]
