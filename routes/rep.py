from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash

from auth import (
    login_required,
    role_required,
)
from extensions import db
from models import (
    Bid,
    Item,
    SupportQuestion,
    User,
)


rep_bp = Blueprint(
    "rep",
    __name__,
)


@rep_bp.route('/rep/dashboard')
@login_required
@role_required('customer_rep', 'admin')
def rep_dashboard():
    users = User.query.filter_by(role='buyer_seller').order_by(User.created_at.desc()).all()
    flagged_items = Item.query.filter_by(status='active').order_by(Item.created_at.desc()).all()
    questions = SupportQuestion.query.order_by(
        SupportQuestion.status.asc(),
        SupportQuestion.created_at.desc()
    ).all()
    return render_template('rep_dashboard.html', users=users,
                           flagged_items=flagged_items,
                           questions=questions)


@rep_bp.route('/rep/question/<int:question_id>/answer', methods=['POST'])
@login_required
@role_required('customer_rep', 'admin')
def rep_answer_question(question_id):
    question = db.get_or_404(SupportQuestion, question_id)
    answer = request.form.get('answer', '').strip()
    if not answer:
        flash('Answer cannot be blank.', 'danger')
        return redirect(url_for('rep_dashboard'))
    question.answer = answer
    question.status = 'answered'
    question.rep_id = session['user_id']
    question.answered_at = datetime.utcnow()
    db.session.commit()
    flash('Question answered.', 'success')
    return redirect(url_for('rep_dashboard'))


@rep_bp.route('/rep/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('customer_rep', 'admin')
def rep_edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == 'POST':
        user.username = request.form['username'].strip()
        user.email    = request.form['email'].strip()
        if request.form.get('new_password'):
            user.password = generate_password_hash(request.form["new_password"], method="pbkdf2:sha256")
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('rep_dashboard'))
    return render_template('rep_edit_user.html', user=user)


@rep_bp.route('/rep/bid/<int:bid_id>/remove', methods=['POST'])
@login_required
@role_required('customer_rep', 'admin')
def rep_remove_bid(bid_id):
    bid = db.get_or_404(Bid, bid_id)
    item = bid.item
    db.session.delete(bid)
    # Recalculate current price
    top = Bid.query.filter_by(item_id=item.item_id).order_by(Bid.amount.desc()).first()
    item.current_price = top.amount if top else item.start_price
    db.session.commit()
    flash('Bid removed.', 'info')
    return redirect(url_for('public.item_detail', item_id=item.item_id))


@rep_bp.route('/rep/item/<int:item_id>/remove', methods=['POST'])
@login_required
@role_required('customer_rep', 'admin')
def rep_remove_item(item_id):
    item = db.get_or_404(Item, item_id)
    item.status = 'cancelled'
    db.session.commit()
    flash('Auction removed.', 'info')
    return redirect(url_for('rep_dashboard'))
