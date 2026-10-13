from flask import render_template, request
from app import app, utils #  Lấy ứng dụng Flask từ __init__.py và các hàm tiện ích từ utils.py.


@app.route("/")
def index():
    categories = utils.load_category()
    return render_template("index.html", categories=categories)

@app.route("/products")
def products():
    category_id = request.args.get("category_id");
    keyword = request.args.get("keyword");
    from_price = request.args.get("from_price");
    to_price = request.args.get("to_price");

    prod_list = utils.load_products(
        category_id=category_id,
        keyword=keyword,
        from_price=from_price,
        to_price=to_price
    )
    return render_template("products.html", products=prod_list)

@app.route("/products/<int:product_id>")
def product_detail(product_id):
    prod = utils.get_product_by_id(product_id)
    return render_template("product-detail.html", product=prod)


if __name__ == "__main__":
    app.run(debug=True)
