# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import os
import mysql.connector


class PhonescraperPipeline:

    def __init__(self):
        self.connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.environ["MYSQL_PASSWORD"],
            database="phonescraper",
            charset="utf8mb4",
        )

        self.cursor = self.connection.cursor()

    def process_item(self, item):

        adapter = ItemAdapter(item)
        # Perform any necessary processing on the item

        # Strip all whitespace from strings
        field_names = adapter.field_names()
        for field_name in field_names:
            value = adapter.get(field_name)
            if isinstance(value, str):
                adapter[field_name] = value.strip()

        ## Price --> convert to int and remove currency sign
        price_keys = ['price']
        for key in price_keys:
            value = adapter.get(key)
            if isinstance(value, str) and value:
                # Remove currency sign and convert to int
                adapter[key] = int(value.replace('₫', '').replace('.', ''))

        ## Stars --> convert to int
        stars_string = adapter.get('stars')
        if stars_string:
            stars_value = float(stars_string)
            adapter['stars'] = stars_value

        sql = """
        INSERT INTO phones (url, title, price, currency, brand)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = %s,
            price = %s,
            currency = %s,
            brand = %s
        """

        title = adapter.get("title")
        price = adapter.get("price")
        currency = adapter.get("currency")
        brand = adapter.get("brand")

        data = (
            # 5 values for INSERT
            adapter.get("url"),
            title,
            price,
            currency,
            brand,

            # 4 values for UPDATE
            title,
            price,
            currency,
            brand
        )

        self.cursor.execute(sql, data)
        self.connection.commit()

        return item

    def close_spider(self):
        try:
            self.cursor.close()
        finally:
            self.connection.close()

