"""Force delete and recreate admin user. Use when login keeps failing."""
from app import app
from extensions import db
from models import User

with app.app_context():
    # Delete existing admin (any user with this email)
    deleted = User.query.filter_by(email="admin@example.com").delete()
    db.session.commit()
    if deleted:
        print("Removed existing admin user.")

    # Create fresh admin
    u = User(name="Admin", email="admin@example.com", role="admin")
    u.set_password("123456")
    db.session.add(u)
    db.session.commit()
    print("Admin created: admin@example.com / 123456")
    print("Try logging in again.")
