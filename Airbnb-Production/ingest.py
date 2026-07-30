import requests
import os

# ---- CONFIG ----
CITY = "new-york-city"
SNAPSHOT_DATE = "2026-06-14"  # the date in the URL, from Inside Airbnb

BASE_URL = f"https://data.insideairbnb.com/united-states/ny/{CITY}/{SNAPSHOT_DATE}/data"

FILES = {
    "listings": f"{BASE_URL}/listings.csv.gz",
    "calendar": f"{BASE_URL}/calendar.csv.gz",
    "reviews": f"{BASE_URL}/reviews.csv.gz",
}

# Local folder to store raw downloaded files (like a "landing zone")
RAW_DIR = "raw_data"
os.makedirs(RAW_DIR, exist_ok=True)

def download_file(url, save_path):
    print(f"Downloading {url} ...")
    response = requests.get(url)
    response.raise_for_status()  # crashes loudly if download failed, instead of silently continuing
    with open(save_path, "wb") as f:
        f.write(response.content)
    print(f"Saved to {save_path}")

import pandas as pd

# def inspect_data():
#     listings = pd.read_csv(os.path.join(RAW_DIR, "listings.csv.gz"), compression="gzip")
#     calendar = pd.read_csv(os.path.join(RAW_DIR, "calendar.csv.gz"), compression="gzip")
#     reviews = pd.read_csv(os.path.join(RAW_DIR, "reviews.csv.gz"), compression="gzip")

#     print("\n--- LISTINGS ---")
#     print("Shape:", listings.shape)
#     print("Columns:", listings.columns.tolist())
#     print(listings.head(3))

#     print("\n--- CALENDAR ---")
#     print("Shape:", calendar.shape)
#     print("Columns:", calendar.columns.tolist())
#     print(calendar.head(3))

#     print("\n--- REVIEWS ---")
#     print("Shape:", reviews.shape)
#     print("Columns:", reviews.columns.tolist())
#     print(reviews.head(3))

# if __name__ == "__main__":
#     for name, url in FILES.items():
#         save_path = os.path.join(RAW_DIR, f"{name}.csv.gz")
#         download_file(url, save_path)

#     inspect_data()

def clean_listings(df):
    keep_cols = [
        "id", "name", "host_id", "host_name", "host_is_superhost",
        "neighbourhood_cleansed", "neighbourhood_group_cleansed", "latitude", "longitude",
        "property_type", "room_type", "accommodates", "bedrooms", "beds",
        "price", "minimum_nights", "maximum_nights", "availability_365",
        "number_of_reviews", "review_scores_rating",
        "estimated_occupancy_l365d", "estimated_revenue_l365d"
    ]
    df = df[keep_cols].copy()

    df["price"] = (
        df["price"]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    df["snapshot_date"] = SNAPSHOT_DATE

    return df

def clean_calendar(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["available"] = df["available"].map({"t": True, "f": False})
    df["snapshot_date"] = SNAPSHOT_DATE
    return df

def clean_reviews(df):
    keep_cols = ["listing_id", "id", "date"]  # drop reviewer_name and comments - not needed for metrics
    df = df[keep_cols].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["snapshot_date"] = SNAPSHOT_DATE
    return df

def run_cleaning():
    listings = pd.read_csv(os.path.join(RAW_DIR, "listings.csv.gz"), compression="gzip")
    calendar = pd.read_csv(os.path.join(RAW_DIR, "calendar.csv.gz"), compression="gzip")
    reviews = pd.read_csv(os.path.join(RAW_DIR, "reviews.csv.gz"), compression="gzip")

    listings_clean = clean_listings(listings)
    calendar_clean = clean_calendar(calendar)
    reviews_clean = clean_reviews(reviews)

    print("Listings cleaned:", listings_clean.shape)
    print(listings_clean.dtypes)
    print("\nCalendar cleaned:", calendar_clean.shape)
    print("\nReviews cleaned:", reviews_clean.shape)

    # --- TEMP DIAGNOSTIC - remove after checking ---
    print("\nhost_since nulls:", listings_clean["host_since"].isna().sum(), "/", len(listings_clean))
    print("instant_bookable value counts:\n", listings["instant_bookable"].value_counts(dropna=False).head())
    print("Raw host_since sample:\n", listings["host_since"].head(5).tolist())

    return listings_clean, calendar_clean, reviews_clean

# if __name__ == "__main__":
#     for name, url in FILES.items():
#         save_path = os.path.join(RAW_DIR, f"{name}.csv.gz")
#         download_file(url, save_path)

#     listings_clean, calendar_clean, reviews_clean = run_cleaning()


from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()  # reads the .env file

PROJECT_ID = "airbnb-dashboard-prod"   # your GCP project ID
DATASET_ID = "airbnb_raw"              # the dataset you created in Step 3c

def get_bigquery_client():
    credentials = service_account.Credentials.from_service_account_file("gcp-key.json")
    client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
    return client

def load_to_bigquery(df, table_name, client):
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # replaces the table each run, for now
    )

    print(f"Loading {len(df)} rows into {table_id} ...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # waits for the load to finish
    print(f"Done. {table_id} now has {client.get_table(table_id).num_rows} rows.")

if __name__ == "__main__":
    for name, url in FILES.items():
        save_path = os.path.join(RAW_DIR, f"{name}.csv.gz")
        download_file(url, save_path)

    listings_clean, calendar_clean, reviews_clean = run_cleaning()

    client = get_bigquery_client()
    load_to_bigquery(listings_clean, "listings", client)
    load_to_bigquery(calendar_clean, "calendar", client)
    load_to_bigquery(reviews_clean, "reviews", client)










