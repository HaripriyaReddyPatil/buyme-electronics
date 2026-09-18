from datetime import datetime, timedelta

from flask import Blueprint, render_template, request

from extensions import db
from models import (
    User,
    Category,
    Item,
    ItemAttribute,
    Bid,
)
from services import (
    close_expired_auctions,
    get_descendant_ids,
)
from sqlalchemy.orm import aliased


public_bp = Blueprint(
    "public",
    __name__,
)


@public_bp.route("/")
def index():
    close_expired_auctions()

    items = (
        Item.query
        .filter_by(status="active")
        .order_by(Item.end_time.asc())
        .limit(12)
        .all()
    )

    categories = (
        Category.query
        .filter_by(parent_id=None)
        .all()
    )

    return render_template(
        "index.html",
        items=items,
        categories=categories,
    )


@public_bp.route("/search")
def search():
    close_expired_auctions()

    q = request.args.get(
        "q",
        "",
    )

    cat_id = request.args.get(
        "category",
        type=int,
    )

    min_price = request.args.get(
        "min_price",
        type=float,
    )

    max_price = request.args.get(
        "max_price",
        type=float,
    )

    sort = request.args.get(
        "sort",
        "end_asc",
    )

    attr_filters = {
        key[5:]: value.strip()
        for key, value in request.args.items()
        if key.startswith("attr_")
        and value.strip()
    }

    query = Item.query.filter_by(
        status="active"
    )

    if q:
        query = query.filter(
            Item.title.ilike(
                f"%{q}%"
            )
            | Item.description.ilike(
                f"%{q}%"
            )
        )

    if cat_id:
        cat_ids = get_descendant_ids(
            cat_id
        )

        query = query.filter(
            Item.category_id.in_(
                cat_ids
            )
        )

    if min_price is not None:
        query = query.filter(
            Item.current_price
            >= min_price
        )

    if max_price is not None:
        query = query.filter(
            Item.current_price
            <= max_price
        )

    for attr_name, attr_value in attr_filters.items():

        attr_alias = aliased(
            ItemAttribute
        )

        query = (
            query
            .join(
                attr_alias,
                attr_alias.item_id
                == Item.item_id,
            )
            .filter(
                attr_alias.attr_name
                == attr_name,

                attr_alias.attr_value.ilike(
                    f"%{attr_value}%"
                ),
            )
        )

    if sort == "end_asc":
        query = query.order_by(
            Item.end_time.asc()
        )

    elif sort == "price_asc":
        query = query.order_by(
            Item.current_price.asc()
        )

    elif sort == "price_desc":
        query = query.order_by(
            Item.current_price.desc()
        )

    elif sort == "newest":
        query = query.order_by(
            Item.created_at.desc()
        )

    items = query.all()

    categories = (
        Category.query
        .filter_by(parent_id=None)
        .all()
    )

    selected_category = (
        db.session.get(
            Category,
            cat_id,
        )
        if cat_id
        else None
    )

    search_attributes = (
        selected_category.attributes
        if (
            selected_category
            and selected_category.attributes
        )
        else []
    )

    return render_template(
        "search.html",
        items=items,
        categories=categories,
        q=q,
        cat_id=cat_id,
        sort=sort,
        search_attributes=search_attributes,
        attr_filters=attr_filters,
    )


@public_bp.route(
    "/item/<int:item_id>"
)
def item_detail(item_id):
    close_expired_auctions()

    item = db.get_or_404(
        Item,
        item_id,
    )

    bids = (
        Bid.query
        .filter_by(
            item_id=item_id
        )
        .order_by(
            Bid.placed_at.desc()
        )
        .all()
    )

    one_month_ago = (
        datetime.utcnow()
        - timedelta(days=30)
    )

    similar = (
        Item.query
        .filter(
            Item.category_id
            == item.category_id,

            Item.status
            == "active",

            Item.item_id
            != item_id,

            Item.created_at
            >= one_month_ago,
        )
        .limit(4)
        .all()
    )

    return render_template(
        "item_detail.html",
        item=item,
        bids=bids,
        similar=similar,
    )


@public_bp.route(
    "/user/<int:user_id>"
)
def user_history(user_id):
    close_expired_auctions()

    user = db.get_or_404(
        User,
        user_id,
    )

    selling_items = (
        Item.query
        .filter_by(
            seller_id=user.user_id
        )
        .order_by(
            Item.created_at.desc()
        )
        .all()
    )

    bid_item_ids = (
        db.session
        .query(
            Bid.item_id
        )
        .filter(
            Bid.bidder_id
            == user.user_id
        )
        .distinct()
        .subquery()
    )

    bidding_items = (
        Item.query
        .join(
            bid_item_ids,
            Item.item_id
            == bid_item_ids.c.item_id,
        )
        .order_by(
            Item.created_at.desc()
        )
        .all()
    )

    return render_template(
        "user_history.html",
        viewed_user=user,
        selling_items=selling_items,
        bidding_items=bidding_items,
    )
