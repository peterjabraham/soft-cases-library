"""
Import all models here so Alembic autogenerate can detect them.
"""

from app.models.base import Base  # noqa: F401
from app.models.ci_models import CICluster, CIRun, CIQueryJob, CIRawResult, CIScoredResult  # noqa: F401
