from functools import wraps
import os
import hashlib
from flask import render_template, request, redirect, url_for, session
from app import app, db, utils
from app.models import Category, Product, User
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView


# --- YC6: Decorator kiểm tra trạng thái login (khớp chuẩn gợi ý đề Bài 3) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


# --- YC4: Quản lý Admin ---
class AuthenticatedView(ModelView):
    def is_accessible(self):
        u = session.get("user")
        return bool(u and u.get("user_role") == "admin")


class CategoryView(AuthenticatedView):
    column_list = ["id", "name"]
    form_columns = ("name",)


class ProductView(AuthenticatedView):
    column_list = ["id", "name", "price", "active", "category"]
    form_columns = ("name", "description", "price", "image", "active", "category")


class UserView(AuthenticatedView):
    column_list = ["id", "username", "name", "email", "active", "user_role"]
    form_columns = (
        "name",
        "email",
        "username",
        "password",
        "avatar",
        "active",
        "user_role",
    )


class ContactView(BaseView):
    @expose("/")
    def index(self):
        return self.render("admin/contact.html")

    def is_accessible(self):
        u = session.get("user")
        return bool(u and u.get("user_role") == "admin")


class LogoutView(BaseView):
    @expose("/")
    def index(self):
        session.pop("user", None)
        return redirect("/admin")

    def is_accessible(self):
        u = session.get("user")
        return bool(u and u.get("user_role") == "admin")


admin = Admin(app, name="Quan ly ban hang")
admin.add_view(CategoryView(Category, db.session, name="Danh muc"))
admin.add_view(ProductView(Product, db.session, name="San pham"))
admin.add_view(UserView(User, db.session, name="Nguoi dung"))
admin.add_view(ContactView(name="Lien he admin"))
admin.add_view(LogoutView(name="Dang xuat"))


@app.route("/")
def index():
    categories = utils.load_category()
    return render_template("index.html", categories=categories)


@app.route("/products")
def products():
    prod_list = utils.load_products(
        category_id=request.args.get("category_id"),
        keyword=request.args.get("keyword"),
        from_price=request.args.get("from_price"),
        to_price=request.args.get("to_price"),
    )
    return render_template("products.html", products=prod_list)


@app.route("/products/<int:product_id>")
def product_detail(product_id):
    prod = utils.get_product_by_id(product_id)
    return render_template("product-detail.html", product=prod)


# --- YC5: Đăng ký người dùng (Băm MD5 mật khẩu + Tải ảnh đại diện) ---
@app.route("/register", methods=["GET", "POST"])
def register():
    err = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        avatar_path = None
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            upload_dir = os.path.join(app.root_path, "static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            avatar_path = "uploads/" + avatar_file.filename
            avatar_file.save(os.path.join(upload_dir, avatar_file.filename))

        try:
            if not (name and email and username and password):
                err = "Vui lòng nhập đầy đủ thông tin bắt buộc!"
            else:
                # Băm mật khẩu bằng MD5 theo gợi ý YC5
                hashed_password = hashlib.md5(password.encode("utf-8")).hexdigest()

                u = User(
                    name=name,
                    email=email,
                    username=username,
                    password=hashed_password,
                    avatar=avatar_path,
                    active=True,
                    user_role="user",
                )
                db.session.add(u)
                db.session.commit()
                return redirect(url_for("login"))
        except Exception as ex:
            db.session.rollback()
            err = f"Lỗi đăng ký (Tên đăng nhập hoặc Email đã tồn tại): {str(ex)}"

    return render_template("register.html", err=err)


# --- YC6: Đăng nhập + Quay về trang trước lúc redirect (next) ---
@app.route("/login", methods=["GET", "POST"])
def login():
    err = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        hashed_password = hashlib.md5(password.encode("utf-8")).hexdigest()
        u = User.query.filter_by(
            username=username, password=hashed_password, active=True
        ).first()

        if u:
            session["user"] = {
                "id": u.id,
                "name": u.name,
                "username": u.username,
                "avatar": u.avatar,
                "user_role": u.user_role,
            }
            # Chuyển về trang trước đó (next) hoặc trang chủ
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            err = "Tài khoản hoặc mật khẩu không chính xác!"

    return render_template("login.html", err=err)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# Ví dụ trang bí mật bắt buộc đăng nhập (test decorator YC6)
@app.route("/secret")
@login_required
def secret():
    return f"Chào mừng bạn đến trang bí mật, {session['user']['name']}! Bạn đã đăng nhập thành công."


# YC1: Thêm sản phẩm vào giỏ hàng lưu trên session
@app.route("/api/cart", methods=["POST"])
def add_to_cart():
    data = request.json
    product_id = str(data.get("id"))
    name = data.get("name")
    price = float(data.get("price", 0))
    image = data.get("image")

    # Lấy giỏ hàng từ session hiện tại, nếu chưa có thì tạo dict rỗng
    cart = session.get("cart", {})

    if product_id in cart:
        # Nếu sản phẩm đã có trong giỏ -> tăng số lượng lên 1
        cart[product_id]["quantity"] += 1
    else:
        cart[product_id] = {
            "id": product_id,
            "name": name,
            "price": price,
            "image": image,
            "quantity": 1,
        }

    session["cart"] = cart

    # Tính tổng số lượng sản phẩm trong giỏ hàng để trả về cập nhật giao diện
    total_quantity = sum(item["quantity"] for item in cart.values())
    total_amount = sum(item["quantity"] * item["price"] for item in cart.values())

    return {
        "status": 200,
        "total_quantity": total_quantity,
        "total_amount": total_amount,
    }


# YC1: Trang giỏ hàng - hiển thị, cập nhật số lượng, xóa sản phẩm
@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    total_quantity = sum(item["quantity"] for item in cart_data.values())
    total_amount = sum(item["quantity"] * item["price"] for item in cart_data.values())
    return render_template(
        "cart.html",
        cart=cart_data,
        total_quantity=total_quantity,
        total_amount=total_amount,
    )


@app.route("/api/cart/<product_id>", methods=["PUT"])
def update_cart_item(product_id):
    cart_data = session.get("cart", {})
    if product_id in cart_data:
        quantity = int((request.json or {}).get("quantity", 1))
        if quantity > 0:
            cart_data[product_id]["quantity"] = quantity
        else:
            cart_data.pop(product_id)  # số lượng <= 0 thì xóa luôn khỏi giỏ
        session["cart"] = cart_data
    return {
        "status": 200,
        "total_quantity": sum(item["quantity"] for item in cart_data.values()),
        "total_amount": sum(item["quantity"] * item["price"] for item in cart_data.values()),
    }


@app.route("/api/cart/<product_id>", methods=["DELETE"])
def delete_cart_item(product_id):
    cart_data = session.get("cart", {})
    if product_id in cart_data:
        cart_data.pop(product_id)
        session["cart"] = cart_data
    return {
        "status": 200,
        "total_quantity": sum(item["quantity"] for item in cart_data.values()),
        "total_amount": sum(item["quantity"] * item["price"] for item in cart_data.values()),
    }


# Bơm tổng số lượng giỏ hàng cho mọi template để hiển thị trên header
@app.context_processor
def inject_cart_count():
    cart_data = session.get("cart", {})
    return {"cart_count": sum(item["quantity"] for item in cart_data.values())}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # In ra danh sách các đường dẫn trực tiếp trong terminal khi khởi động
    print("\n" + "=" * 50)
    print(" Ứng dụng Flask đã khởi động thành công!")
    print(" Bạn có thể click vào các đường dẫn sau để truy cập:")
    print("   - Trang chủ       : http://127.0.0.1:5000/")
    print("   - Danh sách SP    : http://127.0.0.1:5000/products")
    print("   - Trang Admin     : http://127.0.0.1:5000/admin")
    print("   - Đăng ký         : http://127.0.0.1:5000/register")
    print("   - Đăng nhập       : http://127.0.0.1:5000/login")
    print("   - Trang bí mật    : http://127.0.0.1:5000/secret")
    print("=" * 50 + "\n")

    app.run(debug=True)
