#!/usr/bin/env python3
"""
Fetch/import property data from Singapore property portals.

This script supports two modes:
1. IMPORT MODE: Convert CSV exports from property portals into dashboard-ready JSON
2. MANUAL MODE: Enter transaction data manually

Supported CSV formats:
- EdgeProp transaction exports
- 99.co transaction downloads
- PropertyGuru saved searches
- Generic CSV with standard columns

USAGE:
  python fetch_portal_data.py import cluster_houses.csv --type cluster
  python fetch_portal_data.py import 4bed_condos.csv --type condo4
  python fetch_portal_data.py manual

HOW TO GET CSVs:
  EdgeProp:
    1. Go to https://www.edgeprop.sg/transaction-search
    2. Filter by: Property Type → Cluster House (or Condo, 4-bed)
    3. Click "Download" to export CSV

  99.co:
    1. Go to https://www.99.co/singapore/sale
    2. Filter by property type and bedrooms
    3. Use browser developer tools to export listing data

  PropertyGuru:
    1. Go to https://www.propertyguru.com.sg/property-for-sale
    2. Filter by: Cluster House / Condo, 4 bedrooms
    3. Export or copy listing data

  URA PMI (free, official):
    1. Go to https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch
    2. Search with filters (Property Type, Area, etc.)
    3. Download results as CSV
"""

import csv
import json
import os
import sys
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# Standard column mappings for different portal CSV formats
COLUMN_MAPS = {
    "edgeprop": {
        "project": ["Project Name", "Project", "project_name"],
        "address": ["Address", "Street", "address", "street"],
        "property_type": ["Property Type", "Type", "property_type"],
        "area_sqft": ["Area (sqft)", "Floor Area (sqft)", "area_sqft", "Size (sqft)"],
        "price": ["Transacted Price ($)", "Price ($)", "price", "Transacted Price"],
        "psf": ["Unit Price ($ psf)", "Price PSF", "psf", "$ PSF"],
        "date": ["Contract Date", "Sale Date", "date", "Transaction Date"],
        "tenure": ["Tenure", "tenure"],
        "district": ["District", "Postal District", "district"],
        "floor": ["Floor", "Level", "floor_range"],
        "type_of_sale": ["Type of Sale", "Sale Type", "type_of_sale"],
        "bedrooms": ["Bedrooms", "Beds", "No. of Bedrooms", "bedrooms"],
    },
}


def find_column(headers, possible_names):
    """Find the matching column header from a list of possibilities."""
    headers_lower = [h.lower().strip() for h in headers]
    for name in possible_names:
        if name.lower().strip() in headers_lower:
            return headers[headers_lower.index(name.lower().strip())]
    return None


def parse_number(val):
    """Parse a number string, removing $, commas, etc."""
    if not val:
        return 0
    cleaned = str(val).replace("$", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0


def import_csv(filepath, category):
    """Import a CSV file and convert to dashboard JSON format."""
    transactions = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Auto-detect column mapping
        col_map = {}
        for field, possible_names in COLUMN_MAPS["edgeprop"].items():
            matched = find_column(headers, possible_names)
            if matched:
                col_map[field] = matched

        print(f"  Detected columns: {list(col_map.keys())}")
        print(f"  Available headers: {headers}")

        for row in reader:
            area_sqft = parse_number(row.get(col_map.get("area_sqft", ""), 0))
            price = parse_number(row.get(col_map.get("price", ""), 0))
            psf = parse_number(row.get(col_map.get("psf", ""), 0))

            # Calculate PSF if not provided
            if not psf and area_sqft > 0 and price > 0:
                psf = round(price / area_sqft, 2)

            # Convert sqft to sqm
            area_sqm = round(area_sqft / 10.7639, 1) if area_sqft else 0

            txn = {
                "category": category,
                "project": row.get(col_map.get("project", ""), "").strip(),
                "street": row.get(col_map.get("address", ""), "").strip(),
                "propertyType": row.get(col_map.get("property_type", ""), "").strip(),
                "area_sqft": area_sqft,
                "area_sqm": area_sqm,
                "price": price,
                "psf": psf,
                "contractDate": row.get(col_map.get("date", ""), "").strip(),
                "tenure": row.get(col_map.get("tenure", ""), "").strip(),
                "district": row.get(col_map.get("district", ""), "").strip(),
                "floorRange": row.get(col_map.get("floor", ""), "").strip(),
                "typeOfSale": row.get(col_map.get("type_of_sale", ""), "").strip(),
                "bedrooms": row.get(col_map.get("bedrooms", ""), "").strip(),
                "source": "Property Portal CSV",
            }
            transactions.append(txn)

    return transactions


def manual_entry():
    """Interactive manual data entry mode."""
    transactions = []
    print("\nManual Transaction Entry")
    print("Enter 'done' when finished.\n")

    while True:
        print(f"\n--- Transaction #{len(transactions) + 1} ---")
        category = input("Category (cluster/condo4): ").strip()
        if category.lower() == "done":
            break

        category = "Cluster House" if "cluster" in category.lower() else "4-Bed Condo"

        txn = {
            "category": category,
            "project": input("Project name: ").strip(),
            "street": input("Street/Address: ").strip(),
            "propertyType": input("Property type: ").strip(),
            "area_sqft": parse_number(input("Area (sqft): ")),
            "price": parse_number(input("Price ($): ")),
            "contractDate": input("Contract date (MMYY or YYYY-MM): ").strip(),
            "tenure": input("Tenure (e.g. 99 yrs, Freehold): ").strip(),
            "district": input("District (e.g. D19): ").strip(),
            "source": "Manual Entry",
        }
        txn["area_sqm"] = round(txn["area_sqft"] / 10.7639, 1) if txn["area_sqft"] else 0
        txn["psf"] = round(txn["price"] / txn["area_sqft"], 2) if txn["area_sqft"] else 0

        transactions.append(txn)
        print(f"  ✓ Added: {txn['project']} - ${txn['price']:,.0f} ({txn['psf']:.0f} psf)")

    return transactions


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    mode = sys.argv[1].lower()

    if mode == "import":
        if len(sys.argv) < 4 or "--type" not in sys.argv:
            print("Usage: python fetch_portal_data.py import <file.csv> --type <cluster|condo4>")
            sys.exit(1)

        filepath = sys.argv[2]
        type_idx = sys.argv.index("--type") + 1
        prop_type = sys.argv[type_idx]

        category = "Cluster House" if "cluster" in prop_type.lower() else "4-Bed Condo"

        print(f"\nImporting {filepath} as {category}...")
        transactions = import_csv(filepath, category)
        print(f"  ✓ Imported {len(transactions)} transactions")

    elif mode == "manual":
        transactions = manual_entry()

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

    if not transactions:
        print("\nNo transactions to save.")
        sys.exit(0)

    # Save output
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cluster_txns = [t for t in transactions if t["category"] == "Cluster House"]
    condo_txns = [t for t in transactions if t["category"] == "4-Bed Condo"]

    if cluster_txns:
        path = os.path.join(OUTPUT_DIR, "portal_cluster_houses.json")
        with open(path, "w") as f:
            json.dump({
                "source": "Property Portal",
                "fetchedAt": datetime.now().isoformat(),
                "count": len(cluster_txns),
                "transactions": cluster_txns,
            }, f, indent=2)
        print(f"\n✓ Saved {len(cluster_txns)} cluster house records → {path}")

    if condo_txns:
        path = os.path.join(OUTPUT_DIR, "portal_4bed_condos.json")
        with open(path, "w") as f:
            json.dump({
                "source": "Property Portal",
                "fetchedAt": datetime.now().isoformat(),
                "count": len(condo_txns),
                "transactions": condo_txns,
            }, f, indent=2)
        print(f"\n✓ Saved {len(condo_txns)} 4-bed condo records → {path}")


if __name__ == "__main__":
    main()
