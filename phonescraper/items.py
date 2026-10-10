# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass

import scrapy


# @dataclass
class PhonescraperItem:
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    brand = scrapy.Field()

    os = scrapy.Field()
    cpu = scrapy.Field()
    cpu_speed = scrapy.Field()
    gpu = scrapy.Field()
    ram = scrapy.Field()
    capacity = scrapy.Field()

    rear_camera = scrapy.Field()
    front_camera = scrapy.Field()
    screen_technology = scrapy.Field()
    screen_resolution = scrapy.Field()

    battery = scrapy.Field()
    battery_type = scrapy.Field()
    adapter = scrapy.Field()

    stars = scrapy.Field()
