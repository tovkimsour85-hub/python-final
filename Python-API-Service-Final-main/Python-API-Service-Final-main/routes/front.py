from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from extensions import db
from models import User, Category, Product, CartItem, Order, OrderDetail

front_bp = Blueprint("front", __name__)


# ---------- PUBLIC READ ----------
@front_bp.get("/category-list")
def category_list():
    """Get all categories"""
    rows = Category.query.order_by(Category.id.desc()).all()
    return jsonify([{"id": c.id, "name": c.name} for c in rows]), 200


@front_bp.get("/category-list/<int:category_id>")
def category_products(category_id):
    """Get all products for a specific category"""
    # Check if category exists
    category = Category.query.get(category_id)
    if not category:
        return jsonify({"message": "category not found"}), 404

    # Get products for this category
    products = Product.query.filter_by(category_id=category_id).order_by(Product.id.desc()).all()

    return jsonify({
        "category": {"id": category.id, "name": category.name},
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.price,
                "stock": p.stock,
                "category_id": p.category_id
            }
            for p in products
        ]
    }), 200


@front_bp.get("/product-list")
def product_list():
    """Get all products"""
    rows = Product.query.order_by(Product.id.desc()).all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock,
            "category_id": p.category_id,
        }
        for p in rows
    ]), 200


# ---------- AUTH ----------
@front_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"message": "name, email, password required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "email already exists"}), 409

    u = User(name=name, email=email, role="customer")
    u.set_password(password)

    db.session.add(u)
    db.session.commit()
    return jsonify({"message": "registered"}), 201


@front_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(password):
        return jsonify({"message": "invalid credentials"}), 401

    # DEBUG PRINT
    print(f"Creating token for identity: {u.id} (type: {type(u.id)})")

    # FORCE STRING CONVERSION
    identity_str = str(u.id)
    print(f"Using identity string: {identity_str} (type: {type(identity_str)})")

    access_token = create_access_token(identity=identity_str)

    return jsonify({
        "access_token": access_token,
        "user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role},
    }), 200


@front_bp.post("/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    new_password = data.get("new_password") or ""

    if not email or not new_password:
        return jsonify({"message": "email and new_password required"}), 400

    u = User.query.filter_by(email=email).first()
    if not u:
        return jsonify({"message": "email not found"}), 404

    u.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "password updated"}), 200


@front_bp.post("/logout")
def logout():
    # Simple version: client deletes token.
    # If you want true logout, use a token blocklist/revoking approach. [web:161]
    return jsonify({"message": "logout successfully"}), 200


@front_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    u = User.query.get_or_404(user_id)
    return jsonify({"id": u.id, "name": u.name, "email": u.email, "role": u.role}), 200


# ---------- CART ----------
@front_bp.post("/add-to-cart")
@jwt_required()
def add_to_cart():
    # 1. Safely get user_id (cast string back to int)
    current_identity = get_jwt_identity()
    try:
        user_id = int(current_identity)
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid user identity in token"}), 401

    data = request.get_json(silent=True) or {}

    # 2. Validate product_id and qty
    product_id = data.get("product_id")
    if product_id is None:
        return jsonify({"message": "product_id required"}), 400

    try:
        product_id = int(product_id)
        # Default qty to 1 if missing or invalid
        qty = int(data.get("qty", 1))
    except (TypeError, ValueError):
        return jsonify({"message": "product_id and qty must be numbers"}), 400

    if qty < 1:
        return jsonify({"message": "qty must be >= 1"}), 400

    # 3. Check product existence
    p = Product.query.get(product_id)
    if not p:
        return jsonify({"message": "product not found"}), 404

    # 4. Add to cart logic
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item:
        item.qty += qty
    else:
        item = CartItem(user_id=user_id, product_id=product_id, qty=qty)
        db.session.add(item)

    db.session.commit()
    return jsonify({"message": "added to cart"}), 200



@front_bp.delete("/cart/<int:product_id>")
@jwt_required()
def delete_cart_item(product_id):
    user_id = get_jwt_identity()
    item = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()

    if not item:
        return jsonify({"message": "item not found"}), 404

    db.session.delete(item)
    db.session.commit()
    return jsonify({"message": "item deleted"}), 200


# ---------- CHECKOUT / ORDERS ----------
@front_bp.post("/checkout")
@jwt_required()
def checkout():
    # FIX: Cast identity back to int
    try:
        user_id = int(get_jwt_identity())
    except (ValueError, TypeError):
        return jsonify({"message": "Invalid user identity"}), 401

    items = CartItem.query.filter_by(user_id=user_id).all()
    if not items:
        return jsonify({"message": "cart empty"}), 400


    total = 0.0

    # Validate stock + compute total
    for it in items:
        product = Product.query.get(it.product_id)
        if not product:
            return jsonify({"message": f"product not found: {it.product_id}"}), 404

        if it.qty > product.stock:
            return jsonify({"message": f"insufficient stock for product {product.id}"}), 400

        total += float(it.qty) * float(product.price)

    order = Order(user_id=user_id, total=total, status="pending")
    db.session.add(order)
    db.session.flush()  # order.id available without committing

    # Create details + reduce stock + clear cart
    for it in items:
        product = Product.query.get(it.product_id)

        db.session.add(OrderDetail(
            order_id=order.id,
            product_id=product.id,
            qty=it.qty,
            price=product.price,
        ))

        product.stock -= it.qty
        db.session.delete(it)

    db.session.commit()
    return jsonify({"message": "checkout ok", "order_id": order.id, "total": total}), 200


@front_bp.get("/tracking-order")
@jwt_required()
def tracking_order():
    user_id = get_jwt_identity()
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.id.desc()).all()

    return jsonify([
        {
            "id": o.id,
            "total": o.total,
            "status": o.status,
            "created_at": o.created_at.isoformat() if getattr(o, "created_at", None) else None,
        }
        for o in orders
    ]), 200
