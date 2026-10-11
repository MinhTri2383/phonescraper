# PhoneScraper

A learning project that collects phone listings from [The Gioi Di Dong](https://www.thegioididong.com/dtdd) using Scrapy and Playwright, exports JSON, and stores selected fields in MySQL.

## How it works

1. Playwright opens the phone category and clicks **Xem thêm** until the button disappears, with a maximum of 100 clicks.
2. The spider collects unique product and capacity links from product cards.
3. Scrapy downloads product pages through regular HTTP requests.
4. The spider reads Product offers from JSON-LD, including variants declared on each page. If no offer contains a price, it tries the older HTML price selector.
5. The pipeline cleans strings and inserts or updates MySQL rows using the product URL as the unique key.

Products without an extracted price are retained with a null price. Failed requests are logged and do not produce records. A timeout while loading the category can produce a partial result; check the crawl statistics before treating a run as complete.

## Requirements

- Python 3.12 (used during development)
- MySQL Server running locally
- The packages pinned in `requirements.txt`
- Playwright Chromium

MySQL Server is separate from the Python connector. Installing the dependencies does not install or start the server.

## Installation

The commands below use Windows PowerShell. Run them from the directory containing `scrapy.cfg`.

```powershell
git clone https://github.com/MinhTri2383/phonescraper.git
cd phonescraper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

If you already have an activated environment, skip creating another one.

## MySQL setup

In PowerShell, open the MySQL monitor:

```powershell
chcp 65001
mysql --default-character-set=utf8mb4 -u root -p
```

Enter your MySQL password when prompted. At the `mysql>` prompt, run:

```sql
CREATE DATABASE IF NOT EXISTS phonescraper CHARACTER SET utf8mb4;
USE phonescraper;

CREATE TABLE IF NOT EXISTS phones (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(768) NOT NULL,
    title VARCHAR(255),
    price BIGINT UNSIGNED NULL,
    currency VARCHAR(10),
    brand VARCHAR(255),
    UNIQUE KEY unique_phone_url (url)
) CHARACTER SET utf8mb4;
```

If an existing `phones` table lacks the `brand` column, run this once:

```sql
ALTER TABLE phones ADD COLUMN brand VARCHAR(255);
```

The pipeline currently connects to `localhost` as `root`, using the `phonescraper` database. Change `phonescraper/pipelines.py` if your server, account, or database differs.

Exit the MySQL monitor:

```sql
exit;
```

Back in PowerShell, set the password for this terminal session:

```powershell
$mysqlCredential = Get-Credential -UserName root -Message "Enter your MySQL password"
$env:MYSQL_PASSWORD = $mysqlCredential.GetNetworkCredential().Password
```

Enter the password in the credential dialog, not in the `-Message` argument. Keep credentials out of source files. Repeat this step when using a new terminal session. The project does not automatically load `.env` files.

## Run the spider

Start with one product page:

```powershell
scrapy crawl phonespider -a urls=https://www.thegioididong.com/dtdd/iphone-18-pro-max
```

One page may produce several records because its JSON-LD contains multiple capacity and color variants.

Collect the full phone category:

```powershell
scrapy crawl phonespider
```

Limit the number of detail URLs after loading the full category:

```powershell
scrapy crawl phonespider -a limit=3
```

`limit` applies to sorted category URLs, not to the number of exported records or to explicitly supplied URLs. To supply multiple URLs, pass `-a "urls=URL1,URL2"` with comma-separated product URLs.

### JSON only

Disable the MySQL pipeline for a run that requires no database connection:

```powershell
scrapy crawl phonespider -a urls=https://www.thegioididong.com/dtdd/iphone-18-pro-max -s ITEM_PIPELINES="{}" -s FEEDS="{}" -O sample.json
```

To choose a different JSON filename while also saving to MySQL:

```powershell
scrapy crawl phonespider -s FEEDS="{}" -O all_phones.json
```

`-O` overwrites the selected file. MySQL rows persist between runs; existing URLs have their title, price, currency, and brand updated. A newly extracted null price can replace a previous price. This project stores the latest values, not a price history.

## Outputs

| Output | Contents |
| --- | --- |
| `scraped_phones.json` | Default JSON export, overwritten on each run |
| `debug_listing.html` | Category HTML after loading additional products |
| `discovered_phone_urls.json` | Discovered URLs and the category completion flag |
| MySQL `phones` table | URL, title, price, currency, and brand, plus an automatic ID |

The two category diagnostic files are generated only when crawling the category. JSON-LD records can also include SKU, color, availability, price source, and source URL. Fallback records contain fewer fields. These additional fields are not currently stored in MySQL.

Brand is read from the Product object or a breadcrumb fallback. Breadcrumb values can be category labels such as `Điện thoại iPhone (Apple)` rather than a normalized manufacturer name. Missing fields remain null.

Prices from JSON-LD may differ from location-specific or promotional prices displayed in the browser. Multiple records with the same title can represent different variants distinguished by URL query parameters.

## View saved data

At the `mysql>` prompt:

```sql
USE phonescraper;
SELECT id, title, price, currency, brand FROM phones LIMIT 20;
SELECT COUNT(*) AS total FROM phones;
SELECT title, price FROM phones WHERE title LIKE '%Samsung%';
```

You can also browse the table in MySQL Workbench. In VS Code, open the JSON output and use **Shift + Alt + F** to format it.

## Project structure

```text
phonescraper/
├── phonescraper/
│   ├── spiders/phonespider.py  # Listing navigation and product extraction
│   ├── pipelines.py           # Data cleanup and MySQL writes
│   ├── settings.py            # Scrapy, Playwright, and export settings
│   └── items.py               # Optional Scrapy Item definition
├── scrapy.cfg
├── requirements.txt
└── test_mysql.py              # Manual connection/insertion experiment
```

The spider currently yields dictionaries; it does not depend on the Item definition. `test_mysql.py` is a manual experiment and may insert a sample row; it is not an automated test suite.

## Troubleshooting

- **`KeyError: MYSQL_PASSWORD`:** set the environment variable in the same PowerShell session used to run Scrapy.
- **Access denied:** verify the MySQL account and password.
- **Unknown database or missing table/column:** complete the MySQL setup above.
- **No database selected:** run `USE phonescraper;` before querying in the MySQL monitor.
- **Vietnamese characters display incorrectly:** use `chcp 65001` and the UTF-8 MySQL client command above; the pipeline uses `utf8mb4`.
- **Partial category results:** check `phones/listing_complete`, `phones/listing_incomplete`, `phones/failed_requests`, and the log. Inspect `debug_listing.html` if product selectors stop matching.
- **`mysql>` versus `PS ...>`:** enter SQL in the MySQL monitor and commands such as `scrapy`, `python`, and `cd` in PowerShell. Use `\c` to cancel an unfinished SQL statement.

Website markup can change. The project obeys `robots.txt`, uses AutoThrottle, and limits request concurrency to two. Review the site's access requirements before running large crawls.
