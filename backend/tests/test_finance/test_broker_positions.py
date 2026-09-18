import math

from sqlmodel import Session, SQLModel, create_engine

from app.models.finance import Position
from app.services.finance.buffett.broker_positions import current_broker_weights


def test_non_finite_position_price_is_ignored(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'positions.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Position(
                ticker="CW8.PA",
                broker="Bourse Direct",
                quantite=40,
            )
        )
        session.commit()
        weights = current_broker_weights(
            session,
            prices_eur={"CW8.PA": math.nan},
            total_capital_eur=30_000,
            active_brokers=["BoursDirect2"],
        )

    assert weights == {"BoursDirect2": {}}
