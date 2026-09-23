"""Consultations : rattachées à un compte treize mois au plus, comptées ensuite sans nom."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import models
from app.audience import detacher_consultations_anciennes


def test_une_consultation_ancienne_perd_son_compte_mais_reste_comptee(db_session, product, user_factory):
    client_, _ = user_factory()
    maintenant = datetime.now(timezone.utc)
    db_session.add_all([
        models.ProductView(product_id=product.id, user_id=client_.id, created_at=maintenant - timedelta(days=400)),
        models.ProductView(product_id=product.id, user_id=client_.id, created_at=maintenant - timedelta(days=30)),
    ])
    db_session.commit()

    assert detacher_consultations_anciennes(db_session, maintenant) == 1

    comptes = db_session.scalars(
        select(models.ProductView.user_id).order_by(models.ProductView.created_at)
    ).all()
    assert comptes == [None, client_.id]


def test_sans_jeton_la_vue_n_est_rattachee_a_personne(client, db_session, product, auth_header):
    """Sans accord au bandeau, la boutique n'envoie pas le jeton : la vue reste anonyme."""
    entete, connecte = auth_header()
    assert client.post(f"/products/{product.id}/view").status_code < 300
    assert client.post(f"/products/{product.id}/view", headers=entete).status_code < 300

    comptes = db_session.scalars(select(models.ProductView.user_id).order_by(models.ProductView.id)).all()
    assert comptes == [None, connecte.id]
