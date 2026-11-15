from sqlalchemy import select
from .models import PaymentRow
from app.schemas.payments import Payment


class PaymentRepository:
    def __init__(self, session):
        self.session = session

    async def insert(self, payment):
        self.session.add(PaymentRow(**payment.model_dump()))
        await self.session.flush()

    async def recent(self, limit: int = 50):
        rows = await self.session.scalars(
            select(PaymentRow)
            .order_by(PaymentRow.created_at.desc(), PaymentRow.id)
            .limit(limit)
        )
        return [Payment.model_validate(row, from_attributes=True) for row in rows]

    async def get(self, id):
        row = await self.session.get(PaymentRow, id)
        return Payment.model_validate(row, from_attributes=True) if row else None
