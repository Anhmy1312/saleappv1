import json
import os
from app import app

def read_json(filename):
    path = os.path.join(app.root_path, 'data', filename) 
    with open(path, mode ='r', encoding ='utf-8') as f: 
        return json.load(f)


def load_category(): 
    return read_json('categories.json') #Gọi lại hàm read_json để lấy toàn bộ danh sách danh mục (Điện thoại, Máy tính bảng).

def load_products(category_id=None, keyword=None, from_price=None, to_price=None):
    products = read_json('products.json')

    if category_id:
        products = [p for p in products if p['category_id'] == int(category_id)]

    if keyword:
        kw = keyword.lower().strip()
        products = [p for p in products if kw in p['name'].lower()]

    if from_price:
        products = [p for p in products if p['price'] >= float(from_price)]

    if to_price:
        products = [p for p in products if p['price'] <= float(to_price)]

    return products

def get_product_by_id(product_id):
    products = read_json('products.json')
    for p in products:
        if p['id'] == int(product_id):
            return p
    return None


