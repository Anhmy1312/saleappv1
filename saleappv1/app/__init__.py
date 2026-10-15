from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = "cnpm-saleappv1-lab3-secret"

# Cấu hình kết nối MySQL: 'root' là username, '' là password , 'saledb' là tên database
# Nếu mật khẩu có ký tự đặc biệt 
username = "root"
password = "anhmy1312"  # Điền mật khẩu MySQL của bạn vào đây nếu có
database_name = "saledb"

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{username}:{quote(password)}@localhost/{database_name}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)