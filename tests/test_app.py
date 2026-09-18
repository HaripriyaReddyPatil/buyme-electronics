import pytest

from app import app, db, User, Item


@pytest.fixture()
def client():
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(
            username="admin_test",
            email="admin@test.com",
            password="pbkdf2:sha256:1$dummy$dummy",
            role="admin",
        )

        regular = User(
            username="user_test",
            email="user@test.com",
            password="pbkdf2:sha256:1$dummy$dummy",
            role="buyer_seller",
        )

        db.session.add_all([admin, regular])
        db.session.commit()

        yield app.test_client()

        db.session.remove()
        db.drop_all()


def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"BuyMe" in response.data


def test_login_page_loads(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"Login" in response.data or b"Log in" in response.data


def test_admin_dashboard_requires_login(client):
    response = client.get(
        "/admin/dashboard",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)


def test_profile_requires_login(client):
    response = client.get(
        "/profile",
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)


def test_nonexistent_item_returns_404(client):
    response = client.get("/item/999999")

    assert response.status_code == 404
