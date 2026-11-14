from sqlalchemy import text
from .schemas import Payment


class PaymentRepository:
    def __init__(self, engine):
        self.engine = engine

    def insert(self, payment):
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO payments(id,created_at,amount,currency,status,reason) VALUES (:id,:created_at,:amount,:currency,:status,:reason)"
                ),
                payment.model_dump(),
            )

    def recent(self):
        with self.engine.connect() as conn:
            return [
                Payment.model_validate(row)
                for row in conn.execute(
                    text("SELECT * FROM payments ORDER BY created_at DESC,id")
                ).mappings()
            ]

    def get(self, id):
        with self.engine.connect() as conn:
            row = (
                conn.execute(text("SELECT * FROM payments WHERE id=:id"), dict(id=id))
                .mappings()
                .first()
            )
            return Payment.model_validate(row) if row else None
