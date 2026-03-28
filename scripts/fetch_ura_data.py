#!/usr/bin/env python3
"""
Fetch private residential property transaction data from URA API.

Data source: Urban Redevelopment Authority (URA) Singapore
API docs: https://eservice.ura.gov.sg/maps/api/

SETUP:
1. Register at https://eservice.ura.gov.sg/maps/api/reg.html for a free access key
2. Set your access key below or as environment variable URA_ACCESS_KEY
3. Run: python fetch_ura_data.py

The script fetches the last 5 years of transactions and filters for:
- Cluster houses (identified by known project names)
- 4-bedroom condominium/apartment units (identified by floor area 120-175 sqm)
"""

import json
import os
import sys
import time
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Configuration ───────────────────────────────────────────────
URA_ACCESS_KEY = os.environ.get("URA_ACCESS_KEY", "4521d34d-996d-41fc-ad93-fe58e34ab98f")
TOKEN_URL = "https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1"
TRANSACTION_URL = "https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Transaction&batch={batch}"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

# URA returns data in batches (1-4)
BATCHES = [1, 2, 3, 4]

# ─── Known cluster house (strata landed) projects in Singapore ───
# URA classifies these as "Condominium" or "Apartment" but they are
# actually strata-titled landed homes with shared facilities.
# This list uses EXACT project names as they appear in URA data.
CLUSTER_HOUSE_PROJECTS = [
    # Belgravia Collection (D28 - Ang Mo Kio / Seletar)
    "BELGRAVIA VILLAS",
    "BELGRAVIA GREEN",
    "BELGRAVIA ACE",
    # Luxus Hills (D28 - Seletar)
    "LUXUS HILLS",
    # Pollen & Nim (D28)
    "POLLEN COLLECTION",
    "POLLEN COLLECTION II",
    "NIM COLLECTION",
    # Seletar / Ang Mo Kio area (D28)
    "SELETAR HILLS ESTATE",
    "PAVILION PARK",
    "PARRY GREEN",
    "KEW GREEN",
    "CASHEW GREEN",
    "MIMOSA PARK",
    "CABANA",
    "SUNRISE TERRACE",
    # Yishun / Sembawang (D26-27)
    "THE SPRINGSIDE",
    "WATERCOVE",
    # Serangoon / Hougang (D19)
    "VERDANA VILLAS",
    "TERRA VILLAS",
    # East (D17)
    "ARCHIPELAGO",
    # Central (D09-11)
    "THE WHITLEY RESIDENCES",
    "THE TENERIFFE",
    "HILLCREST VILLA",
    "GREENWOOD MEWS",
    "THE CALROSE",
    "ENG KONG PARK",
    "TOMLINSON HEIGHTS",
]

# Condo/Apartment types
CONDO_TYPES = ["Condominium", "Apartment", "Executive Condominium"]

# 4-bedroom condo: 4 bedrooms typically above 1000 sqft (93 sqm)
# Upper limit set at 200 sqm (~2153 sqft) to exclude penthouses
FOUR_BED_MIN_SQM = 93    # 1000 sqft
FOUR_BED_MAX_SQM = 200   # ~2153 sqft


def get_token(access_key):
    """Generate a daily token using the URA access key."""
    req = Request(TOKEN_URL, headers={"AccessKey": access_key, "User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            print(f"  Token response status: {resp.status}")
            if not raw.strip():
                print("Error: Empty response from token endpoint.")
                print("  This may mean your access key hasn't been activated yet.")
                print("  Check your email for an activation link from URA.")
                sys.exit(1)
            data = json.loads(raw)
            token = data.get("Result", "")
            if not token:
                print(f"Error: No token returned. Response: {data}")
                sys.exit(1)
            print("✓ Token generated successfully")
            return token
    except HTTPError as e:
        print(f"Error getting token: {e.code} {e.reason}")
        if e.code == 401:
            print("  Your access key may be invalid or expired.")
        sys.exit(1)


def fetch_transactions(access_key, token, batch):
    """Fetch one batch of transaction data from URA API."""
    url = TRANSACTION_URL.format(batch=batch)
    req = Request(url, headers={"AccessKey": access_key, "Token": token, "User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                print(f"  Batch {batch}: Empty response (may need retry)")
                return []
            data = json.loads(raw)
            results = data.get("Result", [])
            if results is None:
                results = []
            print(f"  Batch {batch}: {len(results)} project groups")
            return results
    except HTTPError as e:
        print(f"  Batch {batch}: Error {e.code} {e.reason}")
        return []
    except URLError as e:
        print(f"  Batch {batch}: Network error - {e.reason}")
        return []
    except json.JSONDecodeError as e:
        print(f"  Batch {batch}: Invalid JSON response - {e}")
        return []


def is_cluster_house(project_name):
    """Check if the project is a known cluster house development."""
    pn = (project_name or "").upper().strip()
    for cluster_proj in CLUSTER_HOUSE_PROJECTS:
        # Exact match only to avoid false positives
        if pn == cluster_proj:
            return True
    return False


def is_4bed_condo(property_type, area_sqm, project_name):
    """Check if the transaction is likely a 4-bedroom condo (not a cluster house)."""
    # Must be condo/apartment type
    pt = (property_type or "").lower()
    is_condo = any(ct.lower() in pt for ct in CONDO_TYPES)
    if not is_condo:
        return False
    # Must NOT be a cluster house project
    if is_cluster_house(project_name):
        return False
    # Must be in 4-bedroom size range
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
        print("Register at https://eservice.ura.gov.sg/maps/api/reg.html to get one.")
        print("Then set URA_ACCESS_KEY environment variable or edit this script.")
        sys.exit(1)

    # Show current cluster house project list
    print(f"\nCluster house project list ({len(CLUSTER_HOUSE_PROJECTS)} projects):")
    for i, p in enumerate(CLUSTER_HOUSE_PROJECTS, 1):
        print(f"  {i:2d}. {p}")
    print(f"\nTo add/remove projects, edit CLUSTER_HOUSE_PROJECTS in this script.")

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
    cluster_projects_found = set()

    for project in all_projects:
        project_name = project.get("project", "")
        transactions = project.get("transaction", [])

        for txn in transactions:
            total_txns += 1
            prop_type = txn.get("propertyType", project.get("propertyType", ""))
            area = txn.get("area", 0)

            if is_cluster_house(project_name):
                record = parse_transaction(project, txn, "Cluster House")
                cluster_txns.append(record)
                cluster_projects_found.add(project_name)
            elif is_4bed_condo(prop_type, area, project_name):
                record = parse_transaction(project, txn, "4-Bed Condo")
                condo_4bed_txns.append(record)

    print(f"  Total transactions scanned: {total_txns}")
    print(f"  Cluster house transactions: {len(cluster_txns)}")
    print(f"  Cluster projects found: {len(cluster_projects_found)}")
    for p in sorted(cluster_projects_found):
        count = sum(1 for t in cluster_txns if t["project"] == p)
        print(f"    - {p}: {count} txns")
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
            "description": "4-bedroom condo/apartment transactions from URA (120-175 sqm)",
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
