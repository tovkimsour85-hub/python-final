from functools import wraps
from flask import request, jsonify, current_app
import jwt

from models import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("x-access-token")  # or "Authorization"

        if not token:
            return jsonify({"message": "Token is missing"}), 401

        try:
            data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user = User.query.get(data["user_id"])
        except Exception:
            return jsonify({"message": "Token is invalid"}), 401

        return f(user, *args, **kwargs)
    return decorated
