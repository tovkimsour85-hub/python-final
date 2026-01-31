from app import app
from extensions import db
from models import User

with app.app_context():
    u = User(name="Admin", email="admin@example.com", role="admin")
    u.set_password("123456")
    db.session.add(u)
    db.session.commit()
    print("Admin created:", u.email)
