
import pyodbc
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation


# --------------------------------------------------
# 1. FILE LOCATION
# --------------------------------------------------

file_path = r"D:\Project\Spice_Board\IndianSpices_Cardamon_Daily_Prices.txt"


# --------------------------------------------------
# 2. CLEAN PRICE
# --------------------------------------------------

def clean_price(price):

    if not price or not price.strip():
        return None

    price = price.strip()

    # Handle No Trade records, including *No Trade*
    if "no trade" in price.lower():
        return None

    # Remove currency formatting
    price = price.replace("/-", "")
    price = price.replace(",", "")
    price = price.replace("₹", "")
    price = price.strip()

    try:
        return Decimal(price)

    except InvalidOperation:
        raise ValueError(f"Unexpected price format: {price}")


# --------------------------------------------------
# 3. CONNECT TO SQL SERVER
# --------------------------------------------------

connection = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=Spices;"
    "Trusted_Connection=yes;"
)

cursor = connection.cursor()

print("Connected to SQL Server successfully!")


# --------------------------------------------------
# 4. SQL QUERIES
# --------------------------------------------------

# Check whether the auction record already exists

select_query = """
SELECT
    sno,
    price_per_kg,
    ip_address,
    cache_name
FROM dbo.auction_prices
WHERE
    auction_date = ?
    AND market = ?
    AND cardamom_type = ?
"""


# Insert a completely new record

insert_query = """
INSERT INTO dbo.auction_prices
(
    production_datetime,
    sno,
    auction_date,
    market,
    cardamom_type,
    price_per_kg,
    ip_address,
    cache_name
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


# Update an existing record if its data has changed

update_query = """
UPDATE dbo.auction_prices
SET
    sno = ?,
    price_per_kg = ?,
    ip_address = ?,
    cache_name = ?
WHERE
    auction_date = ?
    AND market = ?
    AND cardamom_type = ?
"""


# --------------------------------------------------
# 5. COUNTERS
# --------------------------------------------------

total_inserted = 0
total_updated = 0
total_unchanged = 0
total_processed = 0


# --------------------------------------------------
# 6. READ TEXT FILE AND PROCESS RECORDS
# --------------------------------------------------

try:

    with open(file_path, "r", encoding="utf-8-sig") as file:

        reader = csv.DictReader(file, delimiter="\t")

        # Validate file headers
        required_columns = [
            "Date of Production",
            "S.NO",
            "Date of Auction",
            "Market",
            "Type",
            "Price Per Kg",
            "IP Address",
            "Cache Name"
        ]

        if not reader.fieldnames or not all(
            column in reader.fieldnames
            for column in required_columns
        ):
            raise ValueError("Text file headers do not match expected columns.")

        for row in reader:

            # Skip completely empty lines
            if not row.get("Date of Auction") or not row.get("Market"):
                continue

            # Convert source data
            production_datetime = datetime.strptime(
                row["Date of Production"].strip(),
                "%Y-%m-%d %H:%M:%S"
            )

            sno = int(row["S.NO"].strip())

            auction_date = datetime.strptime(
                row["Date of Auction"].strip(),
                "%d-%b-%Y"
            ).date()

            market = row["Market"].strip()
            cardamom_type = row["Type"].strip()

            price = clean_price(row["Price Per Kg"])

            ip_address = row["IP Address"].strip()
            cache_name = row["Cache Name"].strip()

            # Natural key for this auction record
            key = (
                auction_date,
                market,
                cardamom_type
            )

            # Check whether this record already exists
            cursor.execute(select_query, key)

            existing_record = cursor.fetchone()

            if existing_record is None:

                # ----------------------------------
                # NEW RECORD: INSERT
                # ----------------------------------

                data = (
                    production_datetime,
                    sno,
                    auction_date,
                    market,
                    cardamom_type,
                    price,
                    ip_address,
                    cache_name
                )

                cursor.execute(insert_query, data)

                total_inserted += 1

                print(
                    f"INSERTED: {auction_date} | "
                    f"{market} | {cardamom_type}"
                )

            else:

                # ----------------------------------
                # EXISTING RECORD: CHECK FOR CHANGES
                # ----------------------------------

                old_sno = existing_record.sno
                old_price = existing_record.price_per_kg
                old_ip = existing_record.ip_address
                old_cache = existing_record.cache_name

                new_values = (
                    sno,
                    price,
                    ip_address,
                    cache_name
                )

                old_values = (
                    old_sno,
                    old_price,
                    old_ip,
                    old_cache
                )

                if new_values != old_values:

                    # ----------------------------------
                    # CHANGED RECORD: UPDATE
                    # ----------------------------------

                    update_data = (
                        sno,
                        price,
                        ip_address,
                        cache_name,
                        auction_date,
                        market,
                        cardamom_type
                    )

                    cursor.execute(update_query, update_data)

                    total_updated += 1

                    print(
                        f"UPDATED: {auction_date} | "
                        f"{market} | {cardamom_type}"
                    )

                else:

                    # ----------------------------------
                    # NO CHANGE: SKIP
                    # ----------------------------------

                    total_unchanged += 1

            total_processed += 1

    # ----------------------------------
    # 7. COMMIT ALL CHANGES
    # ----------------------------------

    connection.commit()

    print("\n================================")
    print("DAILY DATA IMPORT COMPLETED")
    print("================================")

    print("Total records processed :", total_processed)
    print("New records inserted    :", total_inserted)
    print("Existing records updated:", total_updated)
    print("Unchanged records skipped:", total_unchanged)

    print("================================")


except Exception as error:

    # Roll back all changes if an error occurs
    connection.rollback()

    print("\nERROR OCCURRED!")
    print("All database changes rolled back.")
    print("Error details:", error)


finally:

    cursor.close()
    connection.close()

    print("\nSQL Server connection closed.")
