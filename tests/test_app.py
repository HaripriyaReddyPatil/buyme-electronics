import pytest
from datetime import datetime, timedelta

from flask import url_for
from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import (
    Bid,
    Category,
    Item,
    User,
)


@pytest.fixture()
def client():
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY="test-secret-key",
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

        electronics = Category(
            name="Electronics",
            description="Electronics",
            attributes=[],
        )
        db.session.add(electronics)
        db.session.flush()

        laptops = Category(
            name="Laptops",
            description="Laptop computers",
            attributes=[
                "brand",
                "processor",
                "ram_gb",
                "storage_gb",
                "screen_size_inch",
                "condition",
            ],
            parent_id=electronics.category_id,
        )
        db.session.add(laptops)
        db.session.flush()

        admin = User(
            username="admin_test",
            email="admin@test.com",
            password=generate_password_hash(
                "admin123",
                method="pbkdf2:sha256",
            ),
            role="admin",
            is_active=True,
        )

        rep = User(
            username="rep_test",
            email="rep@test.com",
            password=generate_password_hash(
                "rep123",
                method="pbkdf2:sha256",
            ),
            role="customer_rep",
            is_active=True,
        )

        seller = User(
            username="seller_test",
            email="seller@test.com",
            password=generate_password_hash(
                "seller123",
                method="pbkdf2:sha256",
            ),
            role="buyer_seller",
            is_active=True,
        )

        buyer = User(
            username="buyer_test",
            email="buyer@test.com",
            password=generate_password_hash(
                "buyer123",
                method="pbkdf2:sha256",
            ),
            role="buyer_seller",
            is_active=True,
        )

        db.session.add_all(
            [
                admin,
                rep,
                seller,
                buyer,
            ]
        )
        db.session.flush()

        item = Item(
            seller_id=seller.user_id,
            category_id=laptops.category_id,
            title="Test Laptop",
            description="A test auction laptop",
            start_price=100.00,
            min_price=90.00,
            bid_increment=10.00,
            current_price=100.00,
            end_time=datetime.utcnow()
            + timedelta(days=1),
            status="active",
        )

        db.session.add(item)
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def route_url(endpoint, **values):
    with app.test_request_context():
        return url_for(endpoint, **values)


def login(client, username, password):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_homepage_loads(client):
    response = client.get("/")

    assert response.status_code == 200


def test_login_page_loads(client):
    response = client.get("/login")

    assert response.status_code == 200


def test_admin_dashboard_requires_login(client):
    response = client.get(route_url("admin.admin_dashboard"))

    assert response.status_code in (302, 303)
    assert "/login" in response.headers["Location"]


def test_profile_requires_login(client):
    response = client.get("/profile")

    assert response.status_code in (302, 303)
    assert "/login" in response.headers["Location"]


def test_nonexistent_item_returns_404(client):
    response = client.get("/item/99999")

    assert response.status_code == 404


def test_successful_login(client):
    response = login(
        client,
        "buyer_test",
        "buyer123",
    )

    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_failed_login(client):
    response = login(
        client,
        "buyer_test",
        "wrong-password",
    )

    assert response.status_code == 200
    assert b"Invalid credentials" in response.data


def test_admin_can_access_admin_dashboard(client):
    login(
        client,
        "admin_test",
        "admin123",
    )

    response = client.get(route_url("admin.admin_dashboard"))

    assert response.status_code == 200


def test_regular_user_cannot_access_admin_dashboard(client):
    login(
        client,
        "buyer_test",
        "buyer123",
    )

    response = client.get(
        route_url("admin.admin_dashboard"),
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)

    location = response.headers["Location"]

    assert route_url("admin.admin_dashboard") not in location


def test_rep_can_access_rep_dashboard(client):
    login(
        client,
        "rep_test",
        "rep123",
    )

    response = client.get(route_url("rep.rep_dashboard"))

    assert response.status_code == 200


def test_seller_cannot_bid_on_own_item(client):
    login(
        client,
        "seller_test",
        "seller123",
    )

    with app.app_context():
        item = Item.query.filter_by(
            title="Test Laptop"
        ).first()

        item_id = item.item_id

    response = client.post(
        f"/item/{item_id}/bid",
        data={
            "bid_amount": "120",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"cannot bid on your own item" in response.data.lower()

    with app.app_context():
        assert Bid.query.count() == 0


def test_bid_below_minimum_increment_is_rejected(client):
    login(
        client,
        "buyer_test",
        "buyer123",
    )

    with app.app_context():
        item = Item.query.filter_by(
            title="Test Laptop"
        ).first()

        item_id = item.item_id

    response = client.post(
        f"/item/{item_id}/bid",
        data={
            "bid_amount": "105",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"bid must be at least" in response.data.lower()

    with app.app_context():
        item = db.session.get(
            Item,
            item_id,
        )

        assert float(item.current_price) == 100.00
        assert Bid.query.count() == 0


def test_valid_bid_updates_current_price(client):
    login(
        client,
        "buyer_test",
        "buyer123",
    )

    with app.app_context():
        item = Item.query.filter_by(
            title="Test Laptop"
        ).first()

        item_id = item.item_id

    response = client.post(
        f"/item/{item_id}/bid",
        data={
            "bid_amount": "120",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Bid placed" in response.data

    with app.app_context():
        item = db.session.get(
            Item,
            item_id,
        )

        bid = Bid.query.filter_by(
            item_id=item_id
        ).first()

        assert float(item.current_price) == 120.00
        assert bid is not None
        assert float(bid.amount) == 120.00


def test_inactive_auction_rejects_bid(client):
    login(
        client,
        "buyer_test",
        "buyer123",
    )

    with app.app_context():
        item = Item.query.filter_by(
            title="Test Laptop"
        ).first()

        item.status = "closed"
        item_id = item.item_id

        db.session.commit()

    response = client.post(
        f"/item/{item_id}/bid",
        data={
            "bid_amount": "120",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"no longer active" in response.data.lower()

    with app.app_context():
        assert Bid.query.count() == 0


def test_search_finds_matching_listing(client):
    response = client.get(
        "/search?q=Test+Laptop"
    )

    assert response.status_code == 200
    assert b"Test Laptop" in response.data


def test_search_excludes_nonmatching_listing(client):
    response = client.get(
        "/search?q=NonexistentProduct"
    )

    assert response.status_code == 200
    assert b"Test Laptop" not in response.data
