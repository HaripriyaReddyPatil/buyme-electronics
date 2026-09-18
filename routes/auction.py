from datetime import datetime, timedelta

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth import (
    get_current_user,
    login_required,
)
from extensions import db
from models import (
    Alert,
    Bid,
    Category,
    Item,
    ItemAttribute,
    SupportQuestion,
)
from services import (
    fire_alerts,
    notify_outbid_buyers,
    process_auto_bids,
)


auction_bp = Blueprint(
    "auction",
    __name__,
)


@auction_bp.route(
    "/item/new",
    methods=["GET", "POST"],
)
@login_required
def new_item():
    categories = Category.query.all()

    if request.method == "POST":
        cat_id = int(
            request.form["category_id"]
        )

        category = db.session.get(
            Category,
            cat_id,
        )

        if (
            not category
            or not category.attributes
        ):
            flash(
                "Please choose a specific Electronics subcategory.",
                "danger",
            )

            return redirect(
                url_for(
                    "auction.new_item"
                )
            )

        end_time_text = (
            request.form
            .get(
                "end_time",
                "",
            )
            .strip()
        )

        if end_time_text:
            try:
                end_time = datetime.strptime(
                    end_time_text,
                    "%Y-%m-%dT%H:%M",
                )

            except ValueError:
                flash(
                    "Please enter a valid auction end date and time.",
                    "danger",
                )

                return redirect(
                    url_for(
                        "auction.new_item"
                    )
                )

            if end_time <= datetime.utcnow():
                flash(
                    "Auction end time must be in the future.",
                    "danger",
                )

                return redirect(
                    url_for(
                        "auction.new_item"
                    )
                )

        else:
            duration_hours = int(
                request.form.get(
                    "duration_hours",
                    24,
                )
            )

            end_time = (
                datetime.utcnow()
                + timedelta(
                    hours=duration_hours
                )
            )

        start_price = float(
            request.form["start_price"]
        )

        item = Item(
            seller_id=session["user_id"],
            category_id=cat_id,
            title=request.form[
                "title"
            ].strip(),
            description=request.form[
                "description"
            ].strip(),
            start_price=start_price,
            min_price=float(
                request.form["min_price"]
            ),
            bid_increment=float(
                request.form[
                    "bid_increment"
                ]
            ),
            current_price=start_price,
            end_time=end_time,
            image_url=(
                request.form
                .get(
                    "image_url",
                    "",
                )
                .strip()
                or None
            ),
        )

        db.session.add(item)
        db.session.flush()

        required_attrs = (
            category.attributes
            or []
        )

        missing_attrs = [
            attr_name
            for attr_name
            in required_attrs
            if not request.form.get(
                f"attr_{attr_name}",
                "",
            ).strip()
        ]

        if missing_attrs:
            db.session.rollback()

            readable = ", ".join(
                name.replace(
                    "_",
                    " ",
                )
                for name
                in missing_attrs
            )

            flash(
                f"Missing required item details: {readable}.",
                "danger",
            )

            return redirect(
                url_for(
                    "auction.new_item"
                )
            )

        for attr_name in required_attrs:
            db.session.add(
                ItemAttribute(
                    item_id=item.item_id,
                    attr_name=attr_name,
                    attr_value=(
                        request.form
                        .get(
                            f"attr_{attr_name}",
                            "",
                        )
                        .strip()
                    ),
                )
            )

        db.session.commit()

        fire_alerts(item)

        flash(
            "Auction listed!",
            "success",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item.item_id,
            )
        )

    return render_template(
        "new_item.html",
        categories=categories,
    )


@auction_bp.route(
    "/item/<int:item_id>/cancel",
    methods=["POST"],
)
@login_required
def cancel_item(item_id):
    item = db.get_or_404(
        Item,
        item_id,
    )

    current_user = (
        get_current_user()
    )

    if (
        current_user is None
        or (
            item.seller_id
            != current_user.user_id
            and current_user.role
            not in (
                "admin",
                "customer_rep",
            )
        )
    ):
        flash(
            "Not authorized.",
            "danger",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item_id,
            )
        )

    item.status = "cancelled"

    db.session.commit()

    flash(
        "Auction cancelled.",
        "info",
    )

    return redirect(
        url_for(
            "auth_routes.profile"
        )
    )


@auction_bp.route(
    "/item/<int:item_id>/bid",
    methods=["POST"],
)
@login_required
def place_bid(item_id):
    item = db.get_or_404(
        Item,
        item_id,
    )

    if item.status != "active":
        flash(
            "This auction is no longer active.",
            "danger",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item_id,
            )
        )

    if (
        item.seller_id
        == session["user_id"]
    ):
        flash(
            "You cannot bid on your own item.",
            "danger",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item_id,
            )
        )

    bid_amount = float(
        request.form["bid_amount"]
    )

    auto_bid_limit = (
        request.form.get(
            "auto_bid_limit"
        )
    )

    auto_bid_limit = (
        float(auto_bid_limit)
        if auto_bid_limit
        else None
    )

    if (
        auto_bid_limit is not None
        and auto_bid_limit
        < bid_amount
    ):
        flash(
            "Auto-bid limit must be at least your current bid.",
            "danger",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item_id,
            )
        )

    min_valid = (
        float(item.current_price)
        + float(
            item.bid_increment
        )
    )

    if bid_amount < min_valid:
        flash(
            f"Bid must be at least ${min_valid:.2f}.",
            "danger",
        )

        return redirect(
            url_for(
                "public.item_detail",
                item_id=item_id,
            )
        )

    bid = Bid(
        item_id=item_id,
        bidder_id=session["user_id"],
        amount=bid_amount,
        auto_bid_limit=auto_bid_limit,
    )

    item.current_price = (
        bid_amount
    )

    db.session.add(bid)
    db.session.commit()

    process_auto_bids(
        item,
        bid,
    )

    leading_bid = (
        Bid.query
        .filter_by(
            item_id=item.item_id
        )
        .order_by(
            Bid.amount.desc(),
            Bid.placed_at.asc(),
        )
        .first()
    )

    notify_outbid_buyers(
        item,
        leading_bid,
    )

    db.session.commit()

    flash(
        "Bid placed!",
        "success",
    )

    return redirect(
        url_for(
            "public.item_detail",
            item_id=item_id,
        )
    )


@auction_bp.route(
    "/alerts/new",
    methods=["POST"],
)
@login_required
def new_alert():
    category_id = (
        request.form.get(
            "category_id"
        )
        or None
    )

    attr_filters = {
        key[5:]: value.strip()
        for key, value
        in request.form.items()
        if key.startswith("attr_")
        and value.strip()
    }

    alert = Alert(
        user_id=session["user_id"],
        keywords=(
            request.form
            .get(
                "keywords",
                "",
            )
            .strip()
        ),
        category_id=category_id,
        attr_filters=(
            {
                "filters":
                    attr_filters
            }
            if attr_filters
            else None
        ),
    )

    db.session.add(alert)
    db.session.commit()

    flash(
        "Alert saved!",
        "success",
    )

    return redirect(
        url_for(
            "auth_routes.profile"
        )
    )


@auction_bp.route(
    "/alerts/<int:alert_id>/delete",
    methods=["POST"],
)
@login_required
def delete_alert(alert_id):
    alert = db.get_or_404(
        Alert,
        alert_id,
    )

    if (
        alert.user_id
        != session["user_id"]
    ):
        flash(
            "Not authorized.",
            "danger",
        )

        return redirect(
            url_for(
                "auth_routes.profile"
            )
        )

    db.session.delete(alert)
    db.session.commit()

    flash(
        "Alert removed.",
        "info",
    )

    return redirect(
        url_for(
            "auth_routes.profile"
        )
    )


@auction_bp.route(
    "/support/questions/new",
    methods=["POST"],
)
@login_required
def new_support_question():
    subject = (
        request.form
        .get(
            "subject",
            "",
        )
        .strip()
    )

    question = (
        request.form
        .get(
            "question",
            "",
        )
        .strip()
    )

    if not subject or not question:
        flash(
            "Please include a subject and question.",
            "danger",
        )

        return redirect(
            url_for(
                "auth_routes.profile"
            )
        )

    db.session.add(
        SupportQuestion(
            user_id=session["user_id"],
            subject=subject,
            question=question,
        )
    )

    db.session.commit()

    flash(
        "Your question was sent to customer support.",
        "success",
    )

    return redirect(
        url_for(
            "auth_routes.support"
        )
    )
