from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from extensions import db
from models import User, Category, Product, Order, OrderDetail

admin_bp = Blueprint("admin", __name__)


def require_admin():
    try:
        identity = get_jwt_identity()
        uid = int(identity)
    except (ValueError, TypeError):
        return None

    u = User.query.get(uid)
    if not u or u.role != "admin":
        return None
    return u


# -----------------------
# Auth
# -----------------------
@admin_bp.post("/auth/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    u = User.query.filter_by(email=email, role="admin").first()
    if not u or not u.check_password(password):
        return jsonify({"message": "invalid admin credentials"}), 401

    return jsonify({
        "access_token": create_access_token(identity=str(u.id)),
        "user": {"id": u.id, "email": u.email, "role": u.role}
    }), 200


@admin_bp.post("/auth/logout")
def admin_logout():
    return jsonify({"message": "admin logout success"}), 200


# -----------------------
# Users (CRUD)
# -----------------------
@admin_bp.get("/users")
@jwt_required()
def users_list():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403
    rows = User.query.order_by(User.id.desc()).all()
    return jsonify([{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in rows]), 200


@admin_bp.post("/users")
@jwt_required()
def user_create():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "customer")

    if not name or not email or not password:
        return jsonify({"message": "name, email, password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "email exists"}), 409

    u = User(name=name, email=email, role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({"message": "created", "id": u.id}), 201


@admin_bp.put("/users/<int:user_id>")
@jwt_required()
def user_update(user_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    u = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        u.name = (data["name"] or "").strip()
    if "email" in data:
        new_email = (data["email"] or "").strip().lower()
        if new_email != u.email and User.query.filter_by(email=new_email).first():
            return jsonify({"message": "email exists"}), 409
        u.email = new_email
    if "role" in data:
        u.role = data["role"]
    if "password" in data and data["password"]:
        u.set_password(data["password"])

    db.session.commit()
    return jsonify({"message": "updated", "id": u.id}), 200


@admin_bp.delete("/users/<int:user_id>")
@jwt_required()
def user_delete(user_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    u = User.query.get_or_404(user_id)
    db.session.delete(u)
    db.session.commit()
    return jsonify({"message": "deleted"}), 200


@admin_bp.get("/users/<int:user_id>")
@jwt_required()
def user_detail(user_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403
    u = User.query.get_or_404(user_id)
    return jsonify({"id": u.id, "name": u.name, "email": u.email, "role": u.role}), 200


# -----------------------
# Categories (CRUD)
# -----------------------
@admin_bp.post("/categories")
@jwt_required()
def category_create():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    data = request.get_json(silent=True)
    if isinstance(data, list):
        created = []
        for item in data:
            name = (item.get("name") or "").strip()
            if not name: continue
            c = Category(name=name)
            db.session.add(c)
            db.session.flush()
            created.append({"id": c.id, "name": c.name})
        db.session.commit()
        return jsonify({"message": "created", "categories": created}), 201

    data = data or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"message": "name required"}), 400
    if Category.query.filter_by(name=name).first():
        return jsonify({"message": "category name exists"}), 409

    c = Category(name=name)
    db.session.add(c)
    db.session.commit()
    return jsonify({"message": "created", "id": c.id, "name": c.name}), 201


@admin_bp.get("/categories")
@jwt_required()
def category_list_admin():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403
    rows = Category.query.order_by(Category.id.desc()).all()
    return jsonify([{"id": c.id, "name": c.name} for c in rows]), 200


@admin_bp.put("/categories/<int:category_id>")
@jwt_required()
def category_update(category_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    c = Category.query.get_or_404(category_id)
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"message": "name required"}), 400

    c.name = name
    db.session.commit()
    return jsonify({"message": "updated", "id": c.id, "name": c.name}), 200


@admin_bp.delete("/categories/<int:category_id>")
@jwt_required()
def category_delete(category_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    c = Category.query.get_or_404(category_id)
    if Product.query.filter_by(category_id=category_id).first():
        return jsonify({"message": "cannot delete: category has products"}), 400

    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "deleted"}), 200


# -----------------------
# Products (CRUD)
# -----------------------
@admin_bp.get("/products")
@jwt_required()
def product_list_admin():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403
    rows = Product.query.order_by(Product.id.desc()).all()
    return jsonify([{
        "id": p.id,
        "name": p.name,
        "price": p.price,
        "stock": p.stock,
        "category_id": p.category_id
    } for p in rows]), 200


@admin_bp.post("/products")
@jwt_required()
def product_create():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    payload = request.get_json(silent=True)

    def create_one(item):
        category_id = item.get("category_id")
        name = (item.get("name") or "").strip()
        price = item.get("price")
        stock = int(item.get("stock", 0) or 0)
        description = item.get("description", "")

        if not category_id or not name or price is None:
            return None, {"message": "category_id, name, price required"}
        if not Category.query.get(category_id):
            return None, {"message": f"category not found: {category_id}"}

        p = Product(category_id=category_id, name=name, price=float(price), stock=stock, description=description)
        db.session.add(p)
        db.session.flush()
        return p, None

    if isinstance(payload, list):
        created = []
        errors = []
        for idx, item in enumerate(payload):
            if not isinstance(item, dict): continue
            p, err = create_one(item)
            if err: errors.append({"index": idx, **err})
            else: created.append({"id": p.id, "name": p.name})
        db.session.commit()
        return jsonify({"message": "created", "created": created, "errors": errors}), 201

    data = payload or {}
    p, err = create_one(data)
    if err: return jsonify(err), 400

    db.session.commit()
    return jsonify({"message": "created", "id": p.id}), 201


@admin_bp.put("/products/<int:product_id>")
@jwt_required()
def product_update(product_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    p = Product.query.get_or_404(product_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        p.name = (data["name"] or "").strip()
    if "price" in data:
        p.price = float(data["price"])
    if "stock" in data:
        p.stock = int(data["stock"])
    if "description" in data:
        p.description = data["description"]
    if "category_id" in data:
        cat_id = data["category_id"]
        if Category.query.get(cat_id):
            p.category_id = cat_id
        else:
            return jsonify({"message": f"category not found: {cat_id}"}), 400

    db.session.commit()
    return jsonify({"message": "updated", "id": p.id}), 200


@admin_bp.delete("/products/<int:product_id>")
@jwt_required()
def product_delete(product_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    p = Product.query.get_or_404(product_id)
    # Check if ordered
    if OrderDetail.query.filter_by(product_id=product_id).first():
        return jsonify({"message": "cannot delete: product in orders"}), 400

    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "deleted"}), 200


# -----------------------
# Orders (management)
# -----------------------
@admin_bp.get("/orders")
@jwt_required()
def orders_list():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    rows = Order.query.order_by(Order.id.desc()).all()
    return jsonify([{
        "id": o.id,
        "user_id": o.user_id,
        "total": o.total,
        "status": o.status,
        "created_at": o.created_at.isoformat() if getattr(o, "created_at", None) else None
    } for o in rows]), 200

@admin_bp.get("/orders/<int:order_id>")
@jwt_required()
def order_details(order_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    o = Order.query.get_or_404(order_id)
    details = OrderDetail.query.filter_by(order_id=order_id).all()
    return jsonify({
        "order": {"id": o.id, "user_id": o.user_id, "total": o.total, "status": o.status},
        "items": [{"product_id": d.product_id, "qty": d.qty, "price": d.price} for d in details]
    }), 200

@admin_bp.patch("/orders/<int:order_id>/status")
@jwt_required()
def order_update_status(order_id):
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    o = Order.query.get_or_404(order_id)
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    if not status:
        return jsonify({"message": "status required"}), 400

    o.status = status
    db.session.commit()
    return jsonify({"message": "updated", "id": o.id, "status": o.status}), 200


# -----------------------
# Report
# -----------------------
@admin_bp.get("/report/sale")
@jwt_required()
def report_sale():
    if not require_admin():
        return jsonify({"message": "forbidden"}), 403

    rows = Order.query.filter(Order.status.in_(["paid", "delivered"])).all()
    total = sum(o.total for o in rows)
    return jsonify({"orders_count": len(rows), "total_sales": total}), 200
