from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class DeviationAlert(Base):
    __tablename__ = "deviation_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    target_code: Mapped[str] = mapped_column(String(20), nullable=False)
    target_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    ma50: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    deviation_ratio: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
