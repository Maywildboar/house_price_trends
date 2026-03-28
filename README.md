# SG Property Compare: Cluster Houses vs 4-Bed Condos

Interactive dashboard comparing Singapore cluster house prices against 4-bedroom condominium prices, using official URA data and property portal data.

**Live site:** `https://<your-username>.github.io/sg-property-dashboard/`

## Features

- **KPI Summary**: Average PSF, price premium, total price comparison
- **Interactive Charts**: PSF trends, price distributions, district comparisons, scatter plots
- **Filterable Tables**: Sort and filter by year, district, segment, tenure, sale type
- **Dual Data Sources**: URA official data + property portal exports (separate files)

## Quick Start

### 1. Deploy to GitHub Pages

```bash
# Create a new repo on GitHub, then:
cd sg-property-dashboard
git init
git add .
git commit -m "Initial dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/sg-property-dashboard.git
git push -u origin main
```

Then go to **Settings → Pages → Source: Deploy from branch → main → / (root)** and save. Your site will be live in ~1 minute.

### 2. Update with Real Data

#### Option A: URA API (official government data)

1. Register for a free API key at https://www.ura.gov.sg/maps/api/
2. Run the fetcher script:

```bash
export URA_ACCESS_KEY="your-key-here"
python scripts/fetch_ura_data.py
```

This saves JSON files to `data/` which the dashboard auto-loads.

#### Option B: Property Portal CSV Import

1. Download transaction CSVs from:
   - [EdgeProp](https://www.edgeprop.sg/transaction-search) — filter by Cluster House or 4-Bed Condo
   - [URA PMI](https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch) — free official search
   - [99.co](https://www.99.co) or [PropertyGuru](https://www.propertyguru.com.sg)

2. Import the CSV:

```bash
python scripts/fetch_portal_data.py import cluster_data.csv --type cluster
python scripts/fetch_portal_data.py import condo_4bed_data.csv --type condo4
```

### 3. Commit & Push Updated Data

```bash
git add data/
git commit -m "Update property data"
git push
```

## Project Structure

```
sg-property-dashboard/
├── index.html              # Main dashboard (single-page app)
├── data/
│   ├── sample_data.json    # Demo data (replace with real data)
│   ├── ura_cluster_houses.json    # URA API output
│   ├── ura_4bed_condos.json       # URA API output
│   ├── ura_combined.json          # URA API combined
│   ├── portal_cluster_houses.json # Portal CSV import
│   └── portal_4bed_condos.json    # Portal CSV import
├── scripts/
│   ├── fetch_ura_data.py   # URA API fetcher
│   └── fetch_portal_data.py # Portal CSV importer
└── README.md
```

## Data Sources

| Source | Type | Access | Update Frequency |
|--------|------|--------|-----------------|
| [URA API](https://eservice.ura.gov.sg/maps/api/) | Official govt transactions | Free (API key required) | Tues & Fri |
| [data.gov.sg](https://data.gov.sg/datasets/d_7c69c943d5f0d89d6a9a773d2b51f337/view) | Quarterly aggregates | Free (no key) | Quarterly |
| [EdgeProp](https://www.edgeprop.sg) | Transactions + analytics | Free (registration) | Daily |
| [99.co](https://www.99.co) | Listings + transactions | Free | Daily |
| [PropertyGuru](https://www.propertyguru.com.sg) | Listings + transactions | Free | Daily |
| [URA PMI Search](https://eservice.ura.gov.sg/property-market-information/pmiResidentialTransactionSearch) | Individual transactions | Free (no key) | Tues & Fri |

## Property Type Definitions

- **Cluster House** (Strata Landed): Strata-titled landed homes with shared facilities (pool, gym, security). Includes strata terrace, semi-detached, and detached houses.
- **4-Bed Condo**: Non-landed condominium or apartment units with 4 bedrooms, typically 100-220 sqm (1,076-2,368 sqft).

## Disclaimer

This dashboard is for informational and research purposes only. It is not financial advice. Always verify data with official URA sources before making property decisions.
