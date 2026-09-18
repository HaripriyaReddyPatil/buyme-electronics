from datetime import datetime

import json
import re

from extensions import db
from models import (
    Category,
    Item,
    ItemAttribute,
    Bid,
    Alert,
    AuctionResult,
    OutbidNotification,
)


def close_expired_auctions():
    """Close any active auctions whose end_time has passed."""
    now = datetime.utcnow()
    expired = Item.query.filter(Item.status == 'active', Item.end_time <= now).all()
    for item in expired:
        item.status = 'closed'
        top = item.top_bid
        winner_id = top.bidder_id if top and float(top.amount) >= float(item.min_price) else None
        final_price = top.amount if winner_id else None
        result = AuctionResult(
            item_id=item.item_id,
            winner_id=winner_id,
            final_price=final_price,
            closed_at=now
        )
        db.session.add(result)
        if winner_id:
            db.session.add(OutbidNotification(
                user_id=winner_id,
                item_id=item.item_id,
                message=(f'You won "{item.title}" for ${float(final_price):.2f}.')
            ))
    if expired:
        db.session.commit()


def notify_outbid_buyers(item, new_bid):
    """Notify previous bidders when a higher bid is placed."""
    prior_bidders = (
        db.session.query(Bid.bidder_id)
        .filter(Bid.item_id == item.item_id,
                Bid.bidder_id != new_bid.bidder_id,
                Bid.placed_at < new_bid.placed_at)
        .distinct()
        .all()
    )
    for (bidder_id,) in prior_bidders:
        db.session.add(OutbidNotification(
            user_id=bidder_id,
            item_id=item.item_id,
            message=(f'A higher bid was placed on "{item.title}". '
                     f'Current price is ${float(item.current_price):.2f}.')
        ))


def process_auto_bids(item, new_bid):
    """Run proxy bidding after a bid is placed."""
    increment = float(item.bid_increment)
    current_price = float(item.current_price)

    max_limits = {}
    for bid in Bid.query.filter(Bid.item_id == item.item_id, Bid.auto_bid_limit != None).all():
        max_limits[bid.bidder_id] = max(max_limits.get(bid.bidder_id, 0), float(bid.auto_bid_limit))

    while True:
        leader = Bid.query.filter_by(item_id=item.item_id).order_by(
            Bid.amount.desc(), Bid.placed_at.asc()
        ).first()
        if not leader:
            break

        next_amount = current_price + increment
        challengers = [
            (bidder_id, limit)
            for bidder_id, limit in max_limits.items()
            if bidder_id != leader.bidder_id and limit >= next_amount
        ]
        if not challengers:
            break

        bidder_id, limit = max(challengers, key=lambda row: (row[1], -row[0]))
        auto = Bid(
            item_id=item.item_id,
            bidder_id=bidder_id,
            amount=next_amount,
            auto_bid_limit=limit,
            is_auto=True
        )
        item.current_price = next_amount
        current_price = next_amount
        db.session.add(auto)
        db.session.flush()

    final_leader = Bid.query.filter_by(item_id=item.item_id).order_by(
        Bid.amount.desc(), Bid.placed_at.asc()
    ).first()
    notified = set()
    for bidder_id, limit in max_limits.items():
        if final_leader and bidder_id == final_leader.bidder_id:
            continue
        if limit <= float(item.current_price) and bidder_id not in notified:
            notified.add(bidder_id)
            db.session.add(OutbidNotification(
                user_id=bidder_id,
                item_id=item.item_id,
                message=(f"You've been outbid on \"{item.title}\". "
                         f"Current price ${float(item.current_price):.2f} reached your "
                         f"auto-bid limit of ${limit:.2f}.")
            ))
    db.session.commit()


def decode_alert_payload(payload):
    """Return alert JSON safely for databases migrated from plain TEXT."""
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str) and payload.strip():
        try:
            decoded = json.loads(payload)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def normalize_item_title(title):
    normalized = title.lower().replace('–', '-').replace('—', '-')
    return re.sub(r'[^a-z0-9]+', ' ', normalized).strip()


def fire_alerts(item):
    """Store alert notifications for users whose alerts match a newly listed item."""
    alerts = Alert.query.all()
    for alert in alerts:
        if alert.user_id == item.seller_id:
            continue  # Don't notify seller about their own listing
        keyword_match = True
        if alert.keywords:
            words = [w.strip().lower() for w in alert.keywords.split(',') if w.strip()]
            text = (item.title + ' ' + (item.description or '')).lower()
            keyword_match = any(w in text for w in words)
        cat_match = True
        if alert.category_id:
            cat_ids = get_descendant_ids(alert.category_id)
            cat_match = item.category_id in cat_ids
        attr_match = True
        payload = decode_alert_payload(alert.attr_filters)
        filters = payload.get('filters', {})
        if filters:
            item_attrs = {a.attr_name: (a.attr_value or '').lower() for a in item.attributes}
            for name, expected in filters.items():
                if expected and expected.lower() not in item_attrs.get(name, ''):
                    attr_match = False
                    break
        if keyword_match and cat_match and attr_match:
            # Store as a lightweight notification in the Alert's attr_filters field
            notifs = decode_alert_payload(alert.attr_filters)
            hits = notifs.get('hits', [])
            hits.append({'item_id': item.item_id, 'title': item.title,
                         'notified_at': datetime.utcnow().isoformat()})
            alert.attr_filters = {**notifs, 'hits': hits[-20:]}  # keep last 20
    db.session.commit()


def get_descendant_ids(category_id):
    ids = [category_id]
    children = Category.query.filter_by(parent_id=category_id).all()
    for c in children:
        ids.extend(get_descendant_ids(c.category_id))
    return ids
