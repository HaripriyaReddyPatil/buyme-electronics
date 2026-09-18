from app import app
from db_setup import migrate_db, seed_data
from extensions import db


with app.app_context():
    migrate_db(app)
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run()
