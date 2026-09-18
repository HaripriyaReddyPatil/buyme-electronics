from datetime import datetime

from extensions import db


class User(db.Model):
    __tablename__ = 'users'
    user_id    = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.Enum('buyer_seller', 'customer_rep', 'admin'), default='buyer_seller')
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)

    is_anonymous = db.Column(db.Boolean, default=False)  # hide username in bid history

    items      = db.relationship('Item', backref='seller', foreign_keys='Item.seller_id', lazy=True)
    bids       = db.relationship('Bid', backref='bidder', lazy=True)
    alerts     = db.relationship('Alert', backref='user', lazy=True)


class Category(db.Model):
    __tablename__ = 'categories'
    category_id = db.Column(db.Integer, primary_key=True)
    parent_id   = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    attributes  = db.Column(db.JSON)   # list of required attr names for this category

    children    = db.relationship('Category', backref=db.backref('parent', remote_side='Category.category_id'), lazy=True)
    items       = db.relationship('Item', backref='category', lazy=True)


class Item(db.Model):
    __tablename__ = 'items'
    item_id       = db.Column(db.Integer, primary_key=True)
    seller_id     = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    category_id   = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=False)
    title         = db.Column(db.String(200), nullable=False)
    description   = db.Column(db.Text)
    start_price   = db.Column(db.Numeric(10, 2), nullable=False)
    min_price     = db.Column(db.Numeric(10, 2), nullable=False)   # secret reserve
    bid_increment = db.Column(db.Numeric(10, 2), nullable=False)
    current_price = db.Column(db.Numeric(10, 2))
    start_time    = db.Column(db.DateTime, default=datetime.utcnow)
    end_time      = db.Column(db.DateTime, nullable=False)
    status        = db.Column(db.Enum('active', 'closed', 'cancelled'), default='active')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    image_url     = db.Column(db.String(500), nullable=True)

    bids          = db.relationship('Bid', backref='item', lazy=True, order_by='Bid.amount.desc()')
    attributes    = db.relationship('ItemAttribute', backref='item', lazy=True, cascade='all, delete-orphan')
    result        = db.relationship('AuctionResult', backref='item', uselist=False, lazy=True)

    @property
    def top_bid(self):
        return self.bids[0] if self.bids else None

    @property
    def display_price(self):
        return self.current_price if self.current_price else self.start_price


class ItemAttribute(db.Model):
    __tablename__ = 'item_attributes'
    attr_id   = db.Column(db.Integer, primary_key=True)
    item_id   = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    attr_name = db.Column(db.String(100), nullable=False)
    attr_value = db.Column(db.String(255))


class Bid(db.Model):
    __tablename__ = 'bids'
    bid_id         = db.Column(db.Integer, primary_key=True)
    item_id        = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    bidder_id      = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    amount         = db.Column(db.Numeric(10, 2), nullable=False)
    auto_bid_limit = db.Column(db.Numeric(10, 2), nullable=True)   # secret
    placed_at      = db.Column(db.DateTime, default=datetime.utcnow)
    is_auto        = db.Column(db.Boolean, default=False)


class Alert(db.Model):
    __tablename__ = 'alerts'
    alert_id    = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    keywords    = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'), nullable=True)
    attr_filters = db.Column(db.JSON)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.relationship('Category', backref='alerts')


class AuctionResult(db.Model):
    __tablename__ = 'auction_results'
    result_id   = db.Column(db.Integer, primary_key=True)
    item_id     = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    winner_id   = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    final_price = db.Column(db.Numeric(10, 2))
    closed_at   = db.Column(db.DateTime, default=datetime.utcnow)

    winner = db.relationship('User', backref='wins')


class OutbidNotification(db.Model):
    __tablename__ = 'outbid_notifications'
    notif_id   = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    item_id    = db.Column(db.Integer, db.ForeignKey('items.item_id'), nullable=False)
    message    = db.Column(db.String(300))
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='notifications')
    item = db.relationship('Item', backref='notifications')


class SupportQuestion(db.Model):
    __tablename__ = 'support_questions'
    question_id = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    rep_id      = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    subject     = db.Column(db.String(160), nullable=False)
    question    = db.Column(db.Text, nullable=False)
    answer      = db.Column(db.Text, nullable=True)
    status      = db.Column(db.Enum('open', 'answered'), default='open')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='support_questions')
    rep = db.relationship('User', foreign_keys=[rep_id])
