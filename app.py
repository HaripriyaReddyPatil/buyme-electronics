from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import json
import re
from sqlalchemy.orm import aliased
from config import Config
from extensions import db

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────

from models import (
    User,
    Category,
    Item,
    ItemAttribute,
    Bid,
    Alert,
    AuctionResult,
    OutbidNotification,
    SupportQuestion,
)


# ─────────────────────────────────────────
# AUTH DECORATORS
# ─────────────────────────────────────────

from auth import (
    get_current_user,
    login_required,
    role_required,
)


@app.context_processor
def inject_current_user():
    """Expose the authenticated user safely to Jinja templates."""
    return {
        "current_user": get_current_user()
    }


# ─────────────────────────────────────────
# HELPERS / SERVICES
# ─────────────────────────────────────────

from services import (
    close_expired_auctions,
    notify_outbid_buyers,
    process_auto_bids,
    decode_alert_payload,
    normalize_item_title,
    fire_alerts,
    get_descendant_ids,
)


# ─────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────

from routes.public import public_bp

app.register_blueprint(public_bp)


# ─────────────────────────────────────────
# AUTH / USER ROUTES
# ─────────────────────────────────────────

from routes.auth_routes import auth_bp

app.register_blueprint(auth_bp)


# ─────────────────────────────────────────
# AUCTION ROUTES
# ─────────────────────────────────────────

from routes.auction import auction_bp

app.register_blueprint(auction_bp)


# ─────────────────────────────────────────
# CUSTOMER REP ROUTES
# ─────────────────────────────────────────

from routes.rep import rep_bp

app.register_blueprint(rep_bp)


# ─────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────

from routes.admin import admin_bp

app.register_blueprint(admin_bp)


# ─────────────────────────────────────────
# API ENDPOINTS (for JS)
# ─────────────────────────────────────────
@app.route('/api/categories/<int:cat_id>/attributes')
def api_category_attributes(cat_id):
    cat = db.get_or_404(Category, cat_id)
    return jsonify({'attributes': cat.attributes or []})


@app.route('/api/chatbot', methods=['POST'])
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
# ─────────────────────────────────────────
# DB INIT + SEED
# ─────────────────────────────────────────

def seed_data():
    # If completely empty, seed everything fresh
    fresh = not Category.query.first()

    # ── Top-level categories (add only if missing) ─────────────────
    def get_or_create_cat(name, description, attributes, parent_id=None):
        cat = Category.query.filter_by(name=name, parent_id=parent_id).first()
        if not cat:
            cat = Category(name=name, description=description,
                           attributes=attributes, parent_id=parent_id)
            db.session.add(cat)
            db.session.flush()
        else:
            cat.description = description
            cat.attributes = attributes
            cat.parent_id = parent_id
        return cat

    electronics = get_or_create_cat('Electronics', 'Team category: consumer electronics only', [])
    computers = get_or_create_cat('Computers', 'Computer equipment', [], electronics.category_id)
    phones = get_or_create_cat('Phones', 'Mobile phones', [], electronics.category_id)
    cameras = get_or_create_cat('Cameras', 'Digital cameras', [], electronics.category_id)
    laptops = get_or_create_cat('Laptops', 'Portable computers', ['brand','processor','ram_gb','storage_gb','screen_size_inch','condition'], computers.category_id)
    desktops = get_or_create_cat('Desktops', 'Desktop computers', ['brand','processor','ram_gb','storage_gb','gpu','condition'], computers.category_id)
    smartphones = get_or_create_cat('Smartphones', 'Smartphones', ['brand','model','storage_gb','color','carrier','condition'], phones.category_id)
    mirrorless = get_or_create_cat('Mirrorless Cameras', 'Mirrorless digital cameras', ['brand','model','megapixels','lens_mount','condition'], cameras.category_id)
    dslr = get_or_create_cat('DSLR Cameras', 'DSLR digital cameras', ['brand','model','megapixels','lens_mount','condition'], cameras.category_id)
    db.session.flush()

    Item.query.filter_by(category_id=phones.category_id).update({'category_id': smartphones.category_id})
    Item.query.filter_by(category_id=cameras.category_id).update({'category_id': mirrorless.category_id})

    def delete_item_tree(item):
        Bid.query.filter_by(item_id=item.item_id).delete()
        ItemAttribute.query.filter_by(item_id=item.item_id).delete()
        AuctionResult.query.filter_by(item_id=item.item_id).delete()
        OutbidNotification.query.filter_by(item_id=item.item_id).delete()
        db.session.delete(item)

    allowed_category_ids = set(get_descendant_ids(electronics.category_id))
    for old_item in Item.query.filter(~Item.category_id.in_(allowed_category_ids)).all():
        delete_item_tree(old_item)

    def category_depth(cat):
        depth = 0
        parent = cat.parent
        while parent:
            depth += 1
            parent = parent.parent
        return depth

    old_categories = Category.query.filter(Category.category_id.notin_(allowed_category_ids)).all()
    for old_cat in sorted(old_categories, key=category_depth, reverse=True):
        db.session.delete(old_cat)
    db.session.flush()

    # ── Seed users only if fresh ─────────────────────────────────
    if fresh:
        admin = User(username='admin', email='admin@buyme.com',
                     password=generate_password_hash("admin123", method="pbkdf2:sha256"), role='admin')
        rep1 = User(username='support_rep', email='rep@buyme.com',
                    password=generate_password_hash("rep123", method="pbkdf2:sha256"), role='customer_rep')
        seller1 = User(username='techseller', email='tech@buyme.com',
                       password=generate_password_hash("pass123", method="pbkdf2:sha256"), role='buyer_seller')
        seller2 = User(username='gadgetguru', email='gadget@buyme.com',
                       password=generate_password_hash("pass123", method="pbkdf2:sha256"), role='buyer_seller')
        seller3 = User(username='vintagefinds', email='vintage@buyme.com',
                       password=generate_password_hash("pass123", method="pbkdf2:sha256"), role='buyer_seller')
        seller4 = User(username='sportsgear', email='sports@buyme.com',
                       password=generate_password_hash("pass123", method="pbkdf2:sha256"), role='buyer_seller')
        db.session.add_all([admin, rep1, seller1, seller2, seller3, seller4])
        db.session.flush()
    else:
        # Reuse existing sellers; create new ones if missing
        def get_or_create_user(username, email, password, role):
            u = User.query.filter_by(username=username).first()
            if not u:
                u = User(username=username, email=email,
                         password=generate_password_hash(password, method="pbkdf2:sha256"), role=role)
                db.session.add(u)
                db.session.flush()
            return u
        admin = get_or_create_user('admin', 'admin@buyme.com', 'admin123', 'admin')
        rep1 = get_or_create_user('support_rep', 'rep@buyme.com', 'rep123', 'customer_rep')
        seller1 = get_or_create_user('techseller',   'tech@buyme.com',    'pass123', 'buyer_seller')
        seller2 = get_or_create_user('gadgetguru',   'gadget@buyme.com',  'pass123', 'buyer_seller')
        seller3 = get_or_create_user('vintagefinds', 'vintage@buyme.com', 'pass123', 'buyer_seller')
        seller4 = get_or_create_user('sportsgear',   'sports@buyme.com',  'pass123', 'buyer_seller')

    now = datetime.utcnow()

    seed_items = [
        dict(seller_id=seller1.user_id, category_id=laptops.category_id,
            title='Apple MacBook Pro 14" M3 Pro',
            description='Barely used MacBook Pro with M3 Pro chip. Comes with original charger and box.',
            start_price=1499.00, min_price=1200.00, bid_increment=25.00,
            end_time=now + timedelta(hours=48),
            image_url='https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&q=80',
            attrs=[('brand','Apple'),('processor','M3 Pro'),('ram_gb','18'),('storage_gb','512'),('screen_size_inch','14'),('condition','Like New')]),
        dict(seller_id=seller2.user_id, category_id=laptops.category_id,
            title='Dell XPS 15 OLED - i9, 32GB RAM',
            description='Stunning 3.5K OLED display. Intel Core i9-13900H, NVIDIA RTX 4060, 1TB NVMe SSD.',
            start_price=1299.00, min_price=1100.00, bid_increment=20.00,
            end_time=now + timedelta(hours=36),
            image_url='https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=600&q=80',
            attrs=[('brand','Dell'),('processor','Intel Core i9-13900H'),('ram_gb','32'),('storage_gb','1000'),('screen_size_inch','15.6'),('condition','Good')]),
        dict(seller_id=seller2.user_id, category_id=laptops.category_id,
            title='Lenovo ThinkPad X1 Carbon Gen 11',
            description='Ultra-light business laptop 1.12kg. Intel Evo platform, 16GB LPDDR5, 512GB SSD.',
            start_price=899.00, min_price=800.00, bid_increment=15.00,
            end_time=now + timedelta(hours=18),
            image_url='https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=600&q=80',
            attrs=[('brand','Lenovo'),('processor','Intel Core i7-1365U'),('ram_gb','16'),('storage_gb','512'),('screen_size_inch','14'),('condition','Excellent')]),
        dict(seller_id=seller1.user_id, category_id=laptops.category_id,
            title='ASUS ROG Zephyrus G14 Ryzen 9 RTX 4070',
            description='Compact gaming laptop with Ryzen 9, RTX 4070, 32GB RAM, and 1TB SSD.',
            start_price=1399.00, min_price=1250.00, bid_increment=25.00,
            end_time=now + timedelta(hours=54),
            image_url='https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=600&q=80',
            attrs=[('brand','ASUS'),('processor','AMD Ryzen 9'),('ram_gb','32'),('storage_gb','1000'),('screen_size_inch','14'),('condition','Excellent')]),
        dict(seller_id=seller2.user_id, category_id=laptops.category_id,
            title='HP Spectre x360 14 Convertible Laptop',
            description='OLED touchscreen 2-in-1 laptop with stylus, 16GB RAM, and 1TB SSD.',
            start_price=799.00, min_price=700.00, bid_increment=15.00,
            end_time=now + timedelta(hours=42),
            image_url='https://images.unsplash.com/photo-1587614295999-6c1c1367517c?w=600&q=80',
            attrs=[('brand','HP'),('processor','Intel Core Ultra 7'),('ram_gb','16'),('storage_gb','1000'),('screen_size_inch','14'),('condition','Very Good')]),
        dict(seller_id=seller2.user_id, category_id=smartphones.category_id,
            title='Samsung Galaxy S24 Ultra 256GB',
            description='Factory unlocked, titanium black. Includes S Pen, original box.',
            start_price=699.00, min_price=600.00, bid_increment=10.00,
            end_time=now + timedelta(hours=24),
            image_url='https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=600&q=80',
            attrs=[('brand','Samsung'),('model','Galaxy S24 Ultra'),('storage_gb','256'),('color','Titanium Black'),('carrier','Unlocked'),('condition','Excellent')]),
        dict(seller_id=seller1.user_id, category_id=smartphones.category_id,
            title='iPhone 15 Pro Max 512GB Natural Titanium',
            description='Used 3 months, no scratches, always in case with screen protector.',
            start_price=999.00, min_price=900.00, bid_increment=15.00,
            end_time=now + timedelta(hours=60),
            image_url='https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=600&q=80',
            attrs=[('brand','Apple'),('model','iPhone 15 Pro Max'),('storage_gb','512'),('color','Natural Titanium'),('carrier','Unlocked'),('condition','Like New')]),
        dict(seller_id=seller1.user_id, category_id=smartphones.category_id,
            title='Google Pixel 8 Pro 128GB Bay Blue',
            description='Unlocked Pixel 8 Pro with clean screen, original cable, and Bellroy case.',
            start_price=499.00, min_price=425.00, bid_increment=10.00,
            end_time=now + timedelta(hours=28),
            image_url='https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=600&q=80',
            attrs=[('brand','Google'),('model','Pixel 8 Pro'),('storage_gb','128'),('color','Bay Blue'),('carrier','Unlocked'),('condition','Good')]),
        dict(seller_id=seller2.user_id, category_id=smartphones.category_id,
            title='OnePlus 12 512GB Flowy Emerald',
            description='Fast Android phone with 16GB RAM, 512GB storage, and original SUPERVOOC charger.',
            start_price=629.00, min_price=560.00, bid_increment=10.00,
            end_time=now + timedelta(hours=66),
            image_url='https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600&q=80',
            attrs=[('brand','OnePlus'),('model','12'),('storage_gb','512'),('color','Flowy Emerald'),('carrier','Unlocked'),('condition','Like New')]),
        dict(seller_id=seller1.user_id, category_id=mirrorless.category_id,
            title='Sony A7 IV Full-Frame Mirrorless Camera',
            description='33MP full-frame sensor, 4K 60fps video. Body only, lightly used. Shutter count under 2000.',
            start_price=2199.00, min_price=2000.00, bid_increment=50.00,
            end_time=now + timedelta(hours=72),
            image_url='https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=600&q=80',
            attrs=[('brand','Sony'),('model','A7 IV'),('megapixels','33'),('lens_mount','Sony E'),('condition','Very Good')]),
        dict(seller_id=seller1.user_id, category_id=mirrorless.category_id,
            title='Canon EOS R5 + RF 24-70mm f/2.8L',
            description='45MP powerhouse with 8K RAW video. Includes lens, 2 batteries, and CFexpress card.',
            start_price=3499.00, min_price=3200.00, bid_increment=75.00,
            end_time=now + timedelta(hours=120),
            image_url='https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80',
            attrs=[('brand','Canon'),('model','EOS R5'),('megapixels','45'),('lens_mount','Canon RF'),('condition','Very Good')]),
        dict(seller_id=seller2.user_id, category_id=mirrorless.category_id,
            title='Fujifilm X-T5 Mirrorless Camera Body',
            description='40MP APS-C mirrorless body with film simulations and in-body stabilization.',
            start_price=1299.00, min_price=1150.00, bid_increment=25.00,
            end_time=now + timedelta(hours=88),
            image_url='https://images.unsplash.com/photo-1500634245200-e5245c7574ef?w=600&q=80',
            attrs=[('brand','Fujifilm'),('model','X-T5'),('megapixels','40'),('lens_mount','Fujifilm X'),('condition','Excellent')]),
        dict(seller_id=seller1.user_id, category_id=mirrorless.category_id,
            title='Nikon Z6 II Mirrorless Kit 24-70mm',
            description='Full-frame Nikon Z6 II with 24-70mm lens, two batteries, and charger.',
            start_price=1499.00, min_price=1350.00, bid_increment=30.00,
            end_time=now + timedelta(hours=70),
            image_url='https://images.unsplash.com/photo-1510127034890-ba27508e9f1c?w=600&q=80',
            attrs=[('brand','Nikon'),('model','Z6 II'),('megapixels','24'),('lens_mount','Nikon Z'),('condition','Very Good')]),
        dict(seller_id=seller2.user_id, category_id=desktops.category_id,
            title='Custom Gaming PC - RTX 4090, Ryzen 9 7950X',
            description='64GB DDR5, 2TB NVMe, RTX 4090 24GB. Corsair 5000D Airflow case.',
            start_price=2999.00, min_price=2800.00, bid_increment=100.00,
            end_time=now + timedelta(hours=96),
            image_url='https://images.unsplash.com/photo-1587202372775-e229f172b9d7?w=600&q=80',
            attrs=[('brand','Custom'),('processor','AMD Ryzen 9 7950X'),('ram_gb','64'),('storage_gb','2000'),('gpu','NVIDIA RTX 4090'),('condition','Like New')]),
        dict(seller_id=seller1.user_id, category_id=desktops.category_id,
            title='Apple Mac Studio M2 Max 32GB 1TB',
            description='Compact Mac Studio desktop for creative work. Includes power cable and original box.',
            start_price=1599.00, min_price=1450.00, bid_increment=40.00,
            end_time=now + timedelta(hours=104),
            image_url='https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600&q=80',
            attrs=[('brand','Apple'),('processor','M2 Max'),('ram_gb','32'),('storage_gb','1000'),('gpu','Integrated 30-core GPU'),('condition','Excellent')]),
        dict(seller_id=seller2.user_id, category_id=desktops.category_id,
            title='Dell OptiPlex 7010 Micro i7 Business Desktop',
            description='Small-form-factor desktop with Intel i7, 32GB RAM, 1TB SSD, and Windows 11 Pro.',
            start_price=449.00, min_price=375.00, bid_increment=10.00,
            end_time=now + timedelta(hours=32),
            image_url='https://images.unsplash.com/photo-1593640408182-31c70c8268f5?w=600&q=80',
            attrs=[('brand','Dell'),('processor','Intel Core i7'),('ram_gb','32'),('storage_gb','1000'),('gpu','Intel UHD'),('condition','Good')]),
        dict(seller_id=seller1.user_id, category_id=dslr.category_id,
            title='Nikon D850 DSLR Body 45.7MP',
            description='Professional DSLR body with low shutter count, charger, battery, and strap.',
            start_price=1399.00, min_price=1250.00, bid_increment=30.00,
            end_time=now + timedelta(hours=76),
            image_url='https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600&q=80',
            attrs=[('brand','Nikon'),('model','D850'),('megapixels','45.7'),('lens_mount','Nikon F'),('condition','Very Good')]),
        dict(seller_id=seller2.user_id, category_id=dslr.category_id,
            title='Canon EOS 90D DSLR with EF-S 18-135mm Lens',
            description='32.5MP Canon DSLR bundle with versatile zoom lens, battery grip, and two batteries.',
            start_price=899.00, min_price=775.00, bid_increment=20.00,
            end_time=now + timedelta(hours=58),
            image_url='https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=600&q=80',
            attrs=[('brand','Canon'),('model','EOS 90D'),('megapixels','32.5'),('lens_mount','Canon EF/EF-S'),('condition','Good')]),
        dict(seller_id=seller1.user_id, category_id=dslr.category_id,
            title='Pentax K-1 Mark II Full-Frame DSLR',
            description='Weather-sealed full-frame DSLR with in-body stabilization and original accessories.',
            start_price=1099.00, min_price=950.00, bid_increment=25.00,
            end_time=now + timedelta(hours=110),
            image_url='https://images.unsplash.com/photo-1495707902641-75cac588d2e9?w=600&q=80',
            attrs=[('brand','Pentax'),('model','K-1 Mark II'),('megapixels','36'),('lens_mount','Pentax K'),('condition','Excellent')]),
    ]

    for d in seed_items:
        attrs = d.pop('attrs')
        title_key = normalize_item_title(d['title'])
        existing_keys = {
            normalize_item_title(item.title)
            for item in Item.query.filter(Item.category_id.in_(allowed_category_ids)).all()
        }
        if title_key in existing_keys:
            continue
        item = Item(current_price=d['start_price'], **d)
        db.session.add(item)
        db.session.flush()
        for name, val in attrs:
            db.session.add(ItemAttribute(item_id=item.item_id, attr_name=name, attr_value=val))

    seen_titles = set()
    for item in Item.query.filter(Item.category_id.in_(allowed_category_ids)).order_by(Item.item_id.asc()).all():
        title_key = normalize_item_title(item.title)
        if title_key in seen_titles:
            delete_item_tree(item)
        else:
            seen_titles.add(title_key)

    seed_questions = [
        ('How does automatic bidding work?',
         'If I set an auto-bid limit, does everyone see my maximum?',
         'No. Your maximum stays secret. BuyMe only raises your visible bid by the required increment when another bidder challenges you.'),
        ('What happens if reserve price is not met?',
         'Can an auction close without a winner?',
         'Yes. If the highest bid is below the seller reserve price, the auction closes as unsold and no winner is assigned.'),
        ('Can a bid be removed?',
         'I made a mistake while bidding. Can support help?',
         'A customer representative can remove a bid if they decide the request is reasonable.')
    ]
    for subject, question, answer in seed_questions:
        if not SupportQuestion.query.filter_by(subject=subject).first():
            db.session.add(SupportQuestion(
                user_id=seller1.user_id,
                rep_id=rep1.user_id,
                subject=subject,
                question=question,
                answer=answer,
                status='answered',
                answered_at=datetime.utcnow()
            ))

    db.session.commit()
    print('Seeded database with Electronics categories, users, and expanded sample items.')


def migrate_db():
    """Add any missing columns to existing databases without wiping data."""
    import sqlite3
    db_path = os.path.join(app.instance_path, 'buyme.db')
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Helper: check if column exists
    def has_col(table, col):
        cur.execute(f"PRAGMA table_info({table})")
        return any(row[1] == col for row in cur.fetchall())

    # Helper: check if table exists
    def has_table(table):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        return cur.fetchone() is not None

    migrations = [
        ("users",               "is_anonymous",    "INTEGER NOT NULL DEFAULT 0"),
        ("items",               "image_url",        "TEXT"),
        ("bids",                "auto_bid_limit",   "REAL"),
        ("bids",                "is_auto",          "INTEGER NOT NULL DEFAULT 0"),
        ("alerts",              "attr_filters",     "TEXT"),
    ]
    for table, col, col_def in migrations:
        if has_table(table) and not has_col(table, col):
            print(f"  Migrating: adding {table}.{col}")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

    # Create outbid_notifications table if missing
    if not has_table('outbid_notifications'):
        print("  Migrating: creating outbid_notifications table")
        cur.execute("""
            CREATE TABLE outbid_notifications (
                notif_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(user_id),
                item_id    INTEGER NOT NULL REFERENCES items(item_id),
                message    VARCHAR(300),
                is_read    INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    if not has_table('support_questions'):
        print("  Migrating: creating support_questions table")
        cur.execute("""
            CREATE TABLE support_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(user_id),
                rep_id      INTEGER REFERENCES users(user_id),
                subject     VARCHAR(160) NOT NULL,
                question    TEXT NOT NULL,
                answer      TEXT,
                status      VARCHAR(20) DEFAULT 'open',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                answered_at DATETIME
            )
        """)

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    with app.app_context():
        migrate_db()
        db.create_all()
        seed_data()
    app.run(debug=True)
