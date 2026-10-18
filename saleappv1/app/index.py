from functools import wraps
import os
import hashlib
from datetime import datetime
from flask import render_template, request, redirect, url_for, session, Response
from app import app, db, utils
from app.models import Category, Product, User, Receipt, ReceiptDetail
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy import func  # Cho phép gọi các hàm SQL thông qua SQLAlchemy.


# YC6: Decorator kiểm tra trạng thái login (gợi ý đề Bài 3)
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
    column_filters = ["name", "price", "category"]  # YC3: lọc sản phẩm theo danh mục


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
        return self.render("contact.html")

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


# YC3(bước 5): Thống kê doanh thu trong Admin
class StatsView(BaseView):
    @expose("/")  # Đăng ký đường dẫn trang chính của StatsView
    def index(self):  # Hàm được gọi khi người dùng truy cập trang thống kê
        from_date_str = request.args.get("from_date")  # Ngày bắt đầu thống kê
        to_date_str = request.args.get("to_date")  # Ngày kết thúc thống kê
        category_id = request.args.get("category_id")

        try:
            from_date = (
                datetime.strptime(from_date_str, "%Y-%m-%d")
                if from_date_str
                else datetime.now().replace(day=1)
            )
        except ValueError:
            from_date = datetime.now().replace(day=1)

        try:
            to_date = (
                datetime.strptime(to_date_str, "%Y-%m-%d")
                if to_date_str
                else datetime.now()
            )
        except ValueError:
            to_date = datetime.now()
        to_date = to_date.replace(hour=23, minute=59, second=59)

        # Doanh thu gom theo danh mục trong khoảng thời gian
        q = (
            # Chọn dữ liệu cần thống kê
            db.session.query(
                Category.name,
                func.sum(ReceiptDetail.quantity * ReceiptDetail.unit_price),
            )
            # Chọn bảng bắt đầu truy vấn
            .select_from(ReceiptDetail)
            # Kết nối với bảng hóa đơn
            .join(Receipt, ReceiptDetail.receipt_id == Receipt.id)
            # Kết nối với bảng sản phẩm
            .join(Product, ReceiptDetail.product_id == Product.id)
            # Kết nối với bảng danh mục
            .join(Category, Product.category_id == Category.id)
            # Lọc theo khoảng thời gian
            .filter(Receipt.created_date >= from_date, Receipt.created_date <= to_date)
        )
        if category_id and category_id.isdigit():
            q = q.filter(Category.id == int(category_id))

        # Gom nhóm và lấy kết quả thống kê
        stats = q.group_by(Category.id, Category.name).all()

        # Đếm số lượng hóa đơn
        receipt_count = Receipt.query.filter(
            Receipt.created_date >= from_date, Receipt.created_date <= to_date
        ).count()

        # Truyền dữ liệu sang giao diện HTML
        return render_template(
            "stats.html",
            # Danh sách thống kê
            stats=[
                {"name": name, "revenue": float(revenue or 0)}
                for name, revenue in stats  # Duyệt từng kết quả truy vấn
            ],
            labels=[name for name, _ in stats],  # Nhãn biểu đồ
            values=[float(revenue or 0) for _, revenue in stats],
            total_revenue=sum(float(revenue or 0) for _, revenue in stats),
            receipt_count=receipt_count,
            categories=Category.query.all(),
            from_date=from_date.strftime("%Y-%m-%d"),
            to_date=to_date.strftime("%Y-%m-%d"),
            selected_category=category_id or "",
        )

    def is_accessible(self):
        u = session.get("user")
        return bool(u and u.get("user_role") == "admin")


admin = Admin(app, name="Quan ly ban hang")
admin.add_view(CategoryView(Category, db.session, name="Danh muc"))
admin.add_view(ProductView(Product, db.session, name="San pham"))
admin.add_view(UserView(User, db.session, name="Nguoi dung"))
admin.add_view(ContactView(name="Lien he admin"))
admin.add_view(LogoutView(name="Dang xuat"))
admin.add_view(StatsView(name="Thong ke doanh thu", endpoint="stats"))


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


#  YC5: Đăng ký người dùng (Băm MD5 mật khẩu + Tải ảnh đại diện)
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


#  YC6: Đăng nhập + Quay về trang trước lúc redirect (next)
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
        "total_amount": sum(
            item["quantity"] * item["price"] for item in cart_data.values()
        ),
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
        "total_amount": sum(
            item["quantity"] * item["price"] for item in cart_data.values()
        ),
    }


#  YC2 (Bước 3): Thanh toán giỏ hàng, bắt buộc đăng nhập
@app.route("/pay", methods=["POST"])
def pay():
    if not session.get("user"):
        # Chưa đăng nhập -> chuyển sang trang login rồi quay lại giỏ hàng
        return redirect(url_for("login", next=url_for("cart")))

    cart_data = session.get("cart", {})
    if not cart_data:
        return redirect(url_for("cart"))

    receipt = Receipt(user_id=session["user"]["id"])
    db.session.add(receipt)
    db.session.flush()  # lấy receipt.id trước khi tạo chi tiết

    for item in cart_data.values():
        db.session.add(
            ReceiptDetail(
                receipt_id=receipt.id,
                product_id=int(item["id"]),
                quantity=item["quantity"],
                unit_price=item["price"],
            )
        )
    db.session.commit()  # Xác nhận giao dịch để lưu sản phẩm vào database.

    session.pop("cart", None)  # thanh toán xong thì xóa giỏ hàng
    return redirect(url_for("receipt_detail", receipt_id=receipt.id))


# Trang hóa đơn chi tiết
@app.route("/receipts/<int:receipt_id>")
@login_required
def receipt_detail(receipt_id):
    r = Receipt.query.get_or_404(receipt_id)
    if r.user_id != session["user"]["id"]:
        return redirect(url_for("index"))
    total = sum(
        d.quantity * d.unit_price for d in r.details
    )  # d: Đại diện cho từng chi tiết hóa đơn
    return render_template("receipt.html", receipt=r, total=total)


#  YC2 (Bước 4): Xuất hóa đơn ra file PDF bằng fpdf2
@app.route("/receipts/<int:receipt_id>/pdf")
@login_required
def export_receipt_pdf(receipt_id):
    r = Receipt.query.get_or_404(receipt_id)
    if r.user_id != session["user"]["id"]:
        return redirect(url_for("index"))

    pdf = FPDF()
    pdf.add_page()
    # Nhúng font Arial có sẵn trên Windows để hiển thị đúng tiếng Việt
    pdf.add_font("Arial", "", "C:/Windows/Fonts/arial.ttf")
    pdf.add_font("Arial", "B", "C:/Windows/Fonts/arialbd.ttf")

    pdf.set_font("Arial", "B", 16)
    pdf.cell(
        0,
        10,
        f"HÓA ĐƠN THANH TOÁN #{r.id}",
        align="C",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Khách hàng: {r.user.name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(
        0,
        8,
        f"Ngày lập: {r.created_date.strftime('%d/%m/%Y %H:%M')}",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(4)

    widths = [12, 78, 20, 38, 42]  # STT, Tên SP, SL, Đơn giá, Thành tiền
    headers = ["STT", "Tên sản phẩm", "SL", "Đơn giá", "Thành tiền"]

    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(widths, headers):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln(8)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 10)
    total = 0
    for i, d in enumerate(r.details, start=1):
        amount = d.quantity * d.unit_price
        total += amount
        name = d.product.name if d.product else "(Sản phẩm đã xóa)"
        pdf.cell(widths[0], 8, str(i), border=1, align="C")
        pdf.cell(widths[1], 8, name, border=1)
        pdf.cell(widths[2], 8, str(d.quantity), border=1, align="C")
        pdf.cell(widths[3], 8, f"{d.unit_price:,.0f}", border=1, align="R")
        pdf.cell(
            widths[4],
            8,
            f"{amount:,.0f}",
            border=1,
            align="R",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    pdf.set_font("Arial", "B", 11)
    pdf.cell(sum(widths[:4]), 8, "TỔNG CỘNG", border=1, align="R")
    pdf.cell(
        widths[4],
        8,
        f"{total:,.0f} VNĐ",
        border=1,
        align="R",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    pdf_bytes = bytes(pdf.output())
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{r.id}.pdf"},
    )


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
