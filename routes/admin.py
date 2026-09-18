from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from auth import (
    login_required,
    role_required,
)
from extensions import db
from models import (
    AuctionResult,
    Category,
    Item,
    User,
)


admin_bp = Blueprint(
    "admin",
    __name__,
)


@admin_bp.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    from sqlalchemy import func

    total_earnings = db.session.query(func.sum(AuctionResult.final_price)).scalar() or 0

    # Earnings per item
    earnings_per_item = (
        db.session.query(Item.title, AuctionResult.final_price, AuctionResult.closed_at)
        .join(AuctionResult, AuctionResult.item_id == Item.item_id)
        .order_by(AuctionResult.closed_at.desc())
        .limit(20).all()
    )

    # Earnings per category
    earnings_by_cat = (
        db.session.query(Category.name, func.sum(AuctionResult.final_price))
        .join(Item, Item.item_id == AuctionResult.item_id)
        .join(Category, Category.category_id == Item.category_id)
        .group_by(Category.name)
        .all()
    )

    # Earnings per end-user as seller
    earnings_by_user = (
        db.session.query(User.username, func.sum(AuctionResult.final_price).label('total'))
        .join(Item, Item.seller_id == User.user_id)
        .join(AuctionResult, AuctionResult.item_id == Item.item_id)
        .group_by(User.username)
        .order_by(db.text('total DESC'))
        .all()
    )

    # End-users ranked by number of completed winning purchases
    best_buyers = (
        db.session.query(User.username, func.count(AuctionResult.result_id).label('wins'))
        .join(AuctionResult, AuctionResult.winner_id == User.user_id)
        .filter(AuctionResult.winner_id != None)
        .group_by(User.username)
        .order_by(db.text('wins DESC'))
        .limit(10).all()
    )

    # Best selling users (by total earnings as seller)
    best_sellers = (
        db.session.query(User.username, func.sum(AuctionResult.final_price).label('total'))
        .join(Item, Item.seller_id == User.user_id)
        .join(AuctionResult, AuctionResult.item_id == Item.item_id)
        .group_by(User.username)
        .order_by(db.text('total DESC'))
        .limit(10).all()
    )

    # Best items
    best_items = (
        db.session.query(Item.title, AuctionResult.final_price)
        .join(AuctionResult, AuctionResult.item_id == Item.item_id)
        .order_by(AuctionResult.final_price.desc())
        .limit(10).all()
    )

    reps = User.query.filter_by(role='customer_rep').all()
    categories = Category.query.order_by(Category.parent_id.asc().nullsfirst(), Category.name.asc()).all()
    return render_template('admin_dashboard.html',
                           total_earnings=total_earnings,
                           earnings_by_cat=earnings_by_cat,
                           best_sellers=best_sellers,
                           best_buyers=best_buyers,
                           best_items=best_items,
                           earnings_per_item=earnings_per_item,
                           earnings_by_user=earnings_by_user,
                           reps=reps,
                           categories=categories)


@admin_bp.route('/admin/create_rep', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_rep():
    username = request.form['username'].strip()
    email    = request.form['email'].strip()
    password = request.form['password']

    if User.query.filter_by(username=username).first():
        flash('Username already taken.', 'danger')
        return redirect(url_for('admin_dashboard'))

    rep = User(
        username   = username,
        email      = email,
        password   = generate_password_hash(password, method="pbkdf2:sha256"),
        role       = 'customer_rep',
        created_by = session['user_id']
    )
    db.session.add(rep)
    db.session.commit()
    flash(f'Customer rep {username} created.', 'success')
    return redirect(url_for('admin_dashboard'))


@admin_bp.route('/admin/deactivate_rep/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_deactivate_rep(user_id):
    rep = db.get_or_404(User, user_id)
    rep.is_active = False
    db.session.commit()
    flash('Rep deactivated.', 'info')
    return redirect(url_for('admin_dashboard'))


@admin_bp.route('/admin/category/create', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_category():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    parent_id = request.form.get('parent_id') or None
    attrs_raw = request.form.get('attributes', '')
    attributes = [
        attr.strip().lower().replace(' ', '_')
        for attr in attrs_raw.split(',')
        if attr.strip()
    ]
    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('admin_dashboard'))
    cat = Category(name=name, description=description,
                   parent_id=parent_id, attributes=attributes)
    db.session.add(cat)
    db.session.commit()
    flash(f'Category {name} created.', 'success')
    return redirect(url_for('admin_dashboard'))


@admin_bp.route('/admin/category/<int:category_id>/update', methods=['POST'])
@login_required
@role_required('admin')
def admin_update_category(category_id):
    cat = db.get_or_404(Category, category_id)
    cat.description = request.form.get('description', '').strip()
    attrs_raw = request.form.get('attributes', '')
    cat.attributes = [
        attr.strip().lower().replace(' ', '_')
        for attr in attrs_raw.split(',')
        if attr.strip()
    ]
    db.session.commit()
    flash(f'Category {cat.name} updated.', 'success')
    return redirect(url_for('admin_dashboard'))
