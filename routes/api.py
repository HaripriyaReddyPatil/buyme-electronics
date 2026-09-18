import json
import re
from datetime import datetime

from flask import (
    Blueprint,
    jsonify,
    request,
)

from extensions import db
from models import (
    Alert,
    AuctionResult,
    Bid,
    Category,
    Item,
    ItemAttribute,
    OutbidNotification,
    SupportQuestion,
    User,
)
from services import (
    get_descendant_ids,
    normalize_item_title,
)


api_bp = Blueprint(
    "api",
    __name__,
)


@api_bp.route('/api/categories/<int:cat_id>/attributes')
def api_category_attributes(cat_id):
    cat = db.get_or_404(Category, cat_id)
    return jsonify({'attributes': cat.attributes or []})


@api_bp.route('/api/chatbot', methods=['POST'])
def api_chatbot():
    """Simple rule-based Q&A assistant for BuyMe."""
    data = request.get_json(force=True)
    user_msg = (data.get('message') or '').strip().lower()
    if not user_msg:
        return jsonify({'reply': 'Please type a message.'})

    rules = [
        (['how do i bid', 'how to bid', 'place a bid', 'placing a bid'],
         "To bid, open an item page and enter an amount at least equal to the current price plus the minimum increment, then click Place Bid."),

        (['auto bid', 'automatic bid', 'proxy bid', 'auto-bid'],
         "Auto-bidding lets you set a maximum limit. The system automatically raises your bid by the minimum increment whenever someone outbids you, up to your limit. Your maximum stays secret."),

        (['reserve', 'min price', 'minimum price', 'reserve price'],
         "Each auction has a secret reserve price. If the highest bid doesn't reach it, the auction closes with no winner."),

        (['outbid', 'notification', 'notify', 'alert'],
         "You'll receive an outbid notification in your profile whenever someone places a higher bid on an item you've bid on."),

        (['who wins', 'auction end', 'auction close', 'how does it end', 'winner'],
         "When an auction ends, the highest bidder above the reserve price wins. If no bid meets the reserve, the item goes unsold."),

        (['sell', 'list an item', 'list item', 'create auction', 'new listing'],
         "To list an item, log in and click 'New Auction'. Fill in the title, category, starting price, reserve price, bid increment, and end time."),

        (['cancel auction', 'cancel listing', 'remove my listing'],
         "You can cancel your own active auction from the item page. Customer reps can also cancel listings if needed."),

        (['categor', 'what can i buy', 'what items'],
         "BuyMe currently lists Electronics: Laptops, Desktops, Smartphones, Mirrorless Cameras, and DSLR Cameras."),

        (['register', 'sign up', 'create account'],
         "Click 'Register' in the top navigation, enter a username, email, and password, then log in to start buying or selling."),

        (['forgot password', 'reset password', 'cant log in', "can't log in"],
         "If you can't log in, contact customer support via the Support page and a rep will help reset your credentials."),

        (['anonymous', 'hide my name', 'hide username'],
         "You can enable anonymous bidding in your profile settings. Your username will be hidden in bid history when this is on."),

        (['support', 'contact', 'customer service'],
         "Visit the Support page to submit a question. A customer rep will answer it, and answered questions appear in the public Q&A."),

        (['how long', 'duration', 'end time', 'when does it end'],
         "Sellers choose the auction duration. You can see the exact end date and time on each item's page."),

        (['hello', 'hi', 'hey', 'howdy'],
         "Hi there! I'm the BuyMe Assistant. Ask me anything about bidding, listings, or how the platform works."),

        (['thank', 'thanks', 'ty', 'thx'],
         "You're welcome! Let me know if you have any other questions."),
    ]

    for keywords, reply in rules:
        if any(kw in user_msg for kw in keywords):
            return jsonify({'reply': reply})

    if any(kw in user_msg for kw in ['item', 'listing', 'available', 'auction', 'buy', 'browse']):
        active_items = Item.query.filter_by(status='active').order_by(Item.end_time.asc()).limit(5).all()
        if active_items:
            titles = ', '.join(f'"{it.title}" (${float(it.display_price):.2f})' for it in active_items)
            return jsonify({'reply': f"Here are some active auctions: {titles}. Browse more on the Search page!"})
        return jsonify({'reply': "There are no active listings right now. Check back soon!"})

    return jsonify({'reply': (
        "I'm not sure about that. I can help with: bidding, auto-bids, reserve prices, "
        "listing items, account issues, and how auctions work. What would you like to know?"
    )})
