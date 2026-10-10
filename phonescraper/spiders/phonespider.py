import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import scrapy
from scrapy import Selector
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class PhonespiderSpider(scrapy.Spider):
    name = "phonespider"
    allowed_domains = ["thegioididong.com"]
    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_START_DELAY": 1,
        "DOWNLOAD_DELAY": 0.5,
        "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 2,
        "TELNETCONSOLE_ENABLED": False,
    }

    def __init__(self, limit=None, urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.limit = int(limit) if limit else None
        self.seen_items = set()
        self.direct_urls = urls.split(",") if urls else []

    async def start(self):
        if self.direct_urls:
            for url in self.direct_urls:
                yield scrapy.Request(url, callback=self.parse_product, errback=self.request_failed)
            return
        yield scrapy.Request(
            "https://www.thegioididong.com/dtdd",
            callback=self.parse_listing,
            errback=self.request_failed,
            meta={
                **self.browser_meta(),
                "playwright_include_page": True,
            },
        )

    @staticmethod
    def browser_meta():
        return {
            "playwright": True,
            "playwright_page_goto_kwargs": {
                "wait_until": "domcontentloaded",
                "timeout": 60000,
            },
        }

    async def parse_listing(self, response):
        page = response.meta["playwright_page"]
        complete = False
        try:
            await page.locator('[data-product-code][data-model-code] a[href*="/dtdd/"]').first.wait_for(
                state="attached", timeout=30000
            )
            more = page.get_by_role("button", name=re.compile(r"Xem thêm.*Điện thoại", re.I))
            for batch in range(100):
                if not await more.count() or not await more.is_visible():
                    complete = True
                    break
                before = await page.locator('a[href*="/dtdd/"]').count()
                await more.click(timeout=30000)
                await page.wait_for_function(
                    """before => {
                        const links = document.querySelectorAll('a[href*="/dtdd/"]');
                        return links.length > before;
                    }""",
                    arg=before,
                    timeout=30000,
                )
                self.logger.info("Loaded listing batch %d", batch + 1)
            html = await page.content()
        except PlaywrightTimeoutError:
            self.logger.error("Listing did not finish loading; exporting discovered products only.")
            self.crawler.stats.inc_value("phones/listing_incomplete")
            html = await page.content()
        finally:
            await page.close()

        self.crawler.stats.set_value("phones/listing_complete", complete)
        Path("debug_listing.html").write_text(html, encoding="utf-8")
        urls = set()
        for href in Selector(text=html).css('[data-product-code][data-model-code] a::attr(href)').getall():
            absolute = response.urljoin(href)
            parts = urlsplit(absolute)
            if parts.hostname in ("www.thegioididong.com", "thegioididong.com") and re.fullmatch(r"/dtdd/[a-zA-Z0-9-]+/?", parts.path):
                urls.add(f"https://www.thegioididong.com{parts.path.rstrip('/')}")
        self.crawler.stats.set_value("phones/discovered_urls", len(urls))
        if not urls:
            self.crawler.stats.set_value("phones/listing_complete", False)
            raise ValueError("No product card URLs found; inspect debug_listing.html")
        Path("discovered_phone_urls.json").write_text(
            json.dumps({"listing_complete": complete, "urls": sorted(urls)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.logger.info("Discovered %d product URLs; listing complete=%s", len(urls), complete)
        selected = sorted(urls)
        if self.limit:
            selected = selected[:self.limit]
        for url in selected:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                errback=self.request_failed,
            )

    @classmethod
    def nodes(cls, value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from cls.nodes(child)
        elif isinstance(value, list):
            for child in value:
                yield from cls.nodes(child)

    def parse_product(self, response):
        found = False

        # Lấy tên danh mục thương hiệu từ breadcrumb.
        brand_text = response.css(
            "ul.breadcrumb li:nth-child(2) a"
        ).xpath("string(.)").get()

        # Nếu cấu trúc trên không có, thử cấu trúc giao diện mới.
        if not brand_text:
            brand_text = response.css(
                'main > div:first-child a[href^="/dtdd-"]'
            ).xpath("string(.)").get()

        if brand_text:
            brand_text = brand_text.strip()

        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for product in self.nodes(data):
                types = product.get("@type", [])
                if isinstance(types, str):
                    types = [types]
                if "Product" not in types:
                    continue
                offers = product.get("offers", [])
                if isinstance(offers, dict):
                    offers = [offers]
                for offer in offers:
                    if not isinstance(offer, dict) or offer.get("price") is None:
                        continue
                    url = response.urljoin(offer.get("url") or product.get("url") or response.url)
                    if not urlsplit(url).path.startswith("/dtdd/"):
                        continue
                    found = True
                    key = (url, product.get("sku"), product.get("color"))
                    if key in self.seen_items:
                        continue
                    self.seen_items.add(key)
                    brand = product.get("brand", {})
                    yield {
                        "url": url,
                        "title": product.get("name"),
                        "sku": product.get("sku"),
                        "color": product.get("color"),
                        "brand": (
                            brand.get("name") if isinstance(brand, dict) else brand
                        ) or brand_text,
                        "price": offer["price"],
                        "currency": offer.get("priceCurrency"),
                        "availability": offer.get("availability"),
                        "price_source": "json_ld",
                        "source_url": response.url,
                    }
        if not found:
            price_text = response.css("p.box-price-present").xpath("string(.)").get()
            price_match = re.search(r"\d[\d.,]*", price_text or "")
            if price_match:
                yield {
                    "url": response.url,
                    "title": response.css("h1::text").get(),
                    "price": int(re.sub(r"\D", "", price_match.group())),
                    "currency": "VND",
                    "price_source": "dom",
                    "source_url": response.url,
                }
                return
            self.crawler.stats.inc_value("phones/no_price_pages")
            self.logger.warning("No Product offer with price: %s", response.url)
            yield {
                "url": response.url,
                "title": response.css("h1::text").get() or response.css("title::text").get(),
                "price": None,
                "currency": "VND",
                "price_source": "json_ld",
                "status": "no_product_offer_in_json_ld",
                "source_url": response.url,
            }

    async def request_failed(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page is not None and not page.is_closed():
            await page.close()
        self.crawler.stats.inc_value("phones/failed_requests")
        self.logger.error("Request failed: %s: %s", failure.request.url, failure.value)
