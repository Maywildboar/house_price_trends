#!/usr/bin/env python3
"""
Fetch private residential property transaction data from URA API.

Data source: Urban Redevelopment Authority (URA) Singapore
API docs: https://eservice.ura.gov.sg/maps/api/

SETUP:
1. Register at https://www.ura.gov.sg/maps/api/ for a free access key
2. Set your access key below or as environment variable URA_ACCESS_KEY
3. Run: python fetch_ura_data.py

The script fetches the last 5 years of transactions and filters for:
- Cluster houses (strata landed: strata terrace, strata semi-detached, strata bungalow)
- 4-bedroom condominium/apartment units
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Configuration ───────────────────────────────────────────────
URA_ACCESS_KEY = os.environ.get("URA_ACCESS_KEY", "YOUR_ACCESS_KEY_HERE")
TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
TRANSACTION_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Transaction&batch={batch}"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# URA returns data in batches (1-4)
BATCHES = [1, 2, 3, 4]

# Property types to filter
CLUSTER_TYPES = [
    "Strata Terrace House",
    "Strata Semi-detached House",
    "Strata Detached House",
    "Cluster House",
]

CONDO_TYPES = [
    "Condominium",
    "Apartment",
    "Executive Condominium",
]

# Approximate 4-bedroom size range in sqm (100-200 sqm / ~1076-2153 sqft)
FOUR_BED_MIN_SQM = 100
FOUR_BED_MAX_SQM = 220


def get_token(access_key):
    """Generate a daily token using the URA access key."""
    req = Request(TOKEN_URL, headers={"AccessKey": access_key})
    try:
        with urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            token = data.get("Result", "")
            if not token:
                print(f"Error: No token returned. Response: {data}")
                sys.exit(1)
            print(f"✓ Token generated successfully")
            return token
    except HTTPError as e:
        print(f"Error getting token: {e.code} {e.reason}")
        sys.exit(1)


def fetch_transactions(access_key, token, batch):
    """Fetch one batch of transaction data from URA API."""
    url = TRANSACTION_URL.format(batch=batch)
    req = Request(url, headers={"AccessKey": access_key, "Token": token})
    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("Result", [])
            print(f"  Batch {batch}: {len(results)} project groups")
            return results
    except HTTPError as e:
        print(f"  Batch {batch}: Error {e.code} {e.reason}")
        return []
    except URLError as e:
        print(f"  Batch {batch}: Network error - {e.reason}")
        return []


def is_cluster_house(property_type, project_name=""):
    """Check if the property type is a cluster/strata landed house."""
    pt = (property_type or "").lower()
    pn = (project_name or "").lower()
    for ct in CLUSTER_TYPES:
        if ct.lower() in pt:
            return True
    # Some cluster houses are listed under generic types but have keywords
    cluster_keywords = ["cluster", "strata landed", "townhouse"]
    for kw in cluster_keywords:
        if kw in pt or kw in pn:
            return True
    return False


def is_4bed_condo(property_type, area_sqm):
    """Check if the transaction is likely a 4-bedroom condo."""
    pt = (property_type or "").lower()
    is_condo = any(ct.lower() in pt for ct in CONDO_TYPES)
    if not is_condo:
        return False
    try:
        area = float(area_sqm)
        return FOUR_BED_MIN_SQM <= area <= FOUR_BED_MAX_SQM
    except (ValueError, TypeError):
        return False


def parse_transaction(project, txn, category):
    """Parse a single transaction record into a flat dictionary."""
    area_sqm = txn.get("area", 0)
    try:
        area_sqft = round(float(area_sqm) * 10.7639, 1)
    except (ValueError, TypeError):
        area_sqft = 0

    price = txn.get("price", 0)
    try:
        price_val = float(price)
        psf = round(price_val / area_sqft, 2) if area_sqft > 0 else 0
    except (ValueError, TypeError):
        price_val = 0
        psf = 0

    return {
        "category": category,
        "project": project.get("project", ""),
        "street": project.get("street", ""),
        "marketSegment": project.get("marketSegment", ""),
        "propertyType": txn.get("propertyType", project.get("propertyType", "")),
        "tenure": txn.get("tenure", ""),
        "floorRange": txn.get("floorRange", ""),
        "area_sqm": float(area_sqm) if area_sqm else 0,
        "area_sqft": area_sqft,
        "price": price_val,
        "psf": psf,
        "contractDate": txn.get("contractDate", ""),
        "typeOfSale": txn.get("typeOfSale", ""),
        "district": project.get("district", ""),
        "typeOfArea": txn.get("typeOfArea", ""),
        "noOfUnits": txn.get("noOfUnits", ""),
    }


def main():
    print("=" * 60)
    print("URA Property Transaction Data Fetcher")
    print("=" * 60)

    if URA_ACCESS_KEY == "YOUR_ACCESS_KEY_HERE":
        print("\n⚠ No URA access key configured!")
        print("Register at https://www.ura.gov.sg/maps/api/ to get one.")
        print("Then set URA_ACCESS_KEY environment variable or edit this script.")
        sys.exit(1)

    # Step 1: Get token
    print("\n[1/3] Generating API token...")
    token = get_token(URA_ACCESS_KEY)
    time.sleep(1)

    # Step 2: Fetch all batches
    print("\n[2/3] Fetching transaction data...")
    all_projects = []
    for batch in BATCHES:
        projects = fetch_transactions(URA_ACCESS_KEY, token, batch)
        all_projects.extend(projects)
        time.sleep(1)  # Rate limiting

    print(f"\nTotal project groups fetched: {len(all_projects)}")

    # Step 3: Filter and categorize
    print("\n[3/3] Filtering transactions...")
    cluster_txns = []
    condo_4bed_txns = []
    total_txns = 0

    for project in all_projects:
        transactions = project.get("transaction", [])
        for txn in transactions:
            total_txns += 1
            prop_type = txn.get("propertyType", project.get("propertyType", ""))
            area = txn.get("area", 0)

            if is_cluster_house(prop_type, project.get("project", "")):
                record = parse_transaction(project, txn, "Cluster House")
                cluster_txns.append(record)
            elif is_4bed_condo(prop_type, area):
                record = parse_transaction(project, txn, "4-Bed Condo")
                condo_4bed_txns.append(record)

    print(f"  Total transactions scanned: {total_txns}")
    print(f"  Cluster house transactions: {len(cluster_txns)}")
    print(f"  4-bedroom condo transactions: {len(condo_4bed_txns)}")

    # Save outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cluster_path = os.path.join(OUTPUT_DIR, "ura_cluster_houses.json")
    with open(cluster_path, "w") as f:
        json.dump({
            "source": "URA API",
            "fetchedAt": datetime.now().isoformat(),
            "description": "Cluster house (strata landed) transactions from URA",
            "count": len(cluster_txns),
            "transactions": cluster_txns,
        }, f, indent=2)
    print(f"\n✓ Saved {len(cluster_txns)} cluster house records → {cluster_path}")

    condo_path = os.path.join(OUTPUT_DIR, "ura_4bed_condos.json")
    with open(condo_path, "w") as f:
        json.dump({
            "source": "URA API",
            "fetchedAt": datetime.now().isoformat(),
            "description": "4-bedroom condo/apartment transactions from URA",
            "count": len(condo_4bed_txns),
            "transactions": condo_4bed_txns,
        }, f, indent=2)
    print(f"✓ Saved {len(condo_4bed_txns)} 4-bed condo records → {condo_path}")

    # Combined file for the dashboard
    combined_path = os.path.join(OUTPUT_DIR, "ura_combined.json")
    with open(combined_path, "w") as f:
        json.dump({
            "source": "URA API",
            "fetchedAt": datetime.now().isoformat(),
            "clusterHouses": cluster_txns,
            "fourBedCondos": condo_4bed_txns,
        }, f, indent=2)
    print(f"✓ Saved combined dataset → {combined_path}")


if __name__ == "__main__":
    main()
