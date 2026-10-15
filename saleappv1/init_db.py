import hashlib
import json
from app import app, db
from app.models import Category, Product, User

with app.app_context():
    # Tạo bảng nếu chưa có
    db.create_all()

    # Nạp danh mục từ categories.json
    if Category.query.count() == 0:
        with open("app/data/categories.json", encoding="utf-8") as f:
            cats = json.load(f)
            for c in cats:
                db.session.add(Category(id=c["id"], name=c["name"]))

    # Nạp sản phẩm từ products.json
    if Product.query.count() == 0:
        with open("app/data/products.json", encoding="utf-8") as f:
            prods = json.load(f)
            for p in prods:
                db.session.add(
                    Product(
                        id=p["id"],
                        name=p["name"],
                        description=p.get("description"),
                        price=p["price"],
                        image=p.get("image"),
                        category_id=p["category_id"],
                    )
                )

    # Tạo tài khoản admin mặc định (user: admin, pass: 123456)
    if User.query.filter_by(username="admin").count() == 0:
        admin = User(
            name="Quản trị viên",
            email="admin@ou.edu.vn",
            username="admin",
            password=hashlib.md5("123456".encode("utf-8")).hexdigest(),
            user_role="admin",
            active=True,
        )
        db.session.add(admin)

    db.session.commit()
    print("Đã khởi tạo và đồng bộ dữ liệu vào MySQL thành công!")
