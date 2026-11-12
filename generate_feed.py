
import gzip
import json
import re
from decimal import Decimal
from html import unescape
from urllib.request import Request, urlopen
from urllib.parse import urlencode

STORE = "https://66hundred.com"
OUTPUT = "products.jsonl.gz"


def clean_html(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(value)).strip()


def get_products():
    products = []
    page = 1

    while True:
        query = urlencode({"limit": 250, "page": page})
        url = f"{STORE}/products.json?{query}"
        request = Request(
            url, headers={"User-Agent": "66HUNDRED-Feed/1.0"}
        )

        with urlopen(request, timeout=30) as response:
            batch = json.load(response)["products"]

        if not batch:
            break

        products.extend(batch)

        if len(batch) < 250:
            break

        page += 1

    return products


def generate():
    records = []

    for product in get_products():
        images = product.get("images") or []
        if not images:
            continue

        variants = product.get("variants") or []
        has_options = len(variants) > 1
        options = product.get("options") or []

        for variant in variants:
            price = Decimal(str(variant["price"]))
            if price <= 0:
                continue

            image = next(
                (
                    img["src"] for img in images
                    if img["id"] == variant.get("image_id")
                ),
                images[0]["src"]
            )

            url = f"{STORE}/products/{product['handle']}"
            if has_options:
                url += f"?variant={variant['id']}"

            title = product["title"]
            if has_options and variant.get("title"):
                title += f" - {variant['title']}"

            record = {
                "item_id": str(variant["id"]),
                "title": title[:150],
                "description": (
                    clean_html(product.get("body_html"))
                    or product["title"]
                )[:5000],
                "url": url,
                "brand": "66HUNDRED",
                "seller_name": "66HUNDRED",
                "image_url": image,
                "availability": (
                    "in_stock" if variant.get("available")
                    else "out_of_stock"
                ),
                "price": f"{price:.2f} GBP",
                "is_eligible_search": bool(variant.get("available")),
            }

            if has_options:
                selected = {}
                for index, option in enumerate(options, start=1):
                    value = variant.get(f"option{index}")
                    if value:
                        selected[option["name"]] = str(value)

                record.update({
                    "group_id": f"product-{product['id']}",
                    "listing_has_variations": True,
                    "variant_dict": selected,
                })

            records.append(record)

    if not records:
        raise RuntimeError("No products found; refusing empty feed")

    with gzip.open(OUTPUT, "wt", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Generated {len(records)} product records")


if __name__ == "__main__":
    generate()
