from flask import Flask, jsonify
from config import Config
from extensions import db, migrate, jwt

from routes.front import front_bp
from routes.admin import admin_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    app.register_blueprint(front_bp, url_prefix="/api/front")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.get("/")
    def index():
        return jsonify({
            "message": "Ecommerce API is running",
            "health": "/health",
            "front_api": "/api/front",
            "admin_api": "/api/admin",
        }), 200

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
