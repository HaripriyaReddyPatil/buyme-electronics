from flask import Flask

from auth import get_current_user
from config import Config
from db_setup import migrate_db, seed_data
from extensions import db
from routes.admin import admin_bp
from routes.api import api_bp
from routes.auction import auction_bp
from routes.auth_routes import auth_bp
from routes.public import public_bp
from routes.rep import rep_bp


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


@app.context_processor
def inject_current_user():
    """Expose the authenticated user safely to Jinja templates."""
    return {
        "current_user": get_current_user()
    }


# Register application route groups.
app.register_blueprint(public_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(auction_bp)
app.register_blueprint(rep_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)


if __name__ == "__main__":
    with app.app_context():
        migrate_db(app)
        db.create_all()
        seed_data()

    app.run(debug=True)
