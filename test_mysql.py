from getpass import getpass

import mysql.connector

connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password=getpass("Nhập mật khẩu MySQL: "),
    database="phonescraper",
)

cursor = connection.cursor()

sql = """
INSERT INTO phones (url, title, price, currency)
VALUES (%s, %s, %s, %s)
"""

data = (
    "https://example.com/phone-test",
    "Điện thoại thử nghiệm",
    10000000,
    "VND",
)

cursor.execute(sql, data)
connection.commit()

print("Đã lưu một sản phẩm!")

cursor.close()
connection.close()