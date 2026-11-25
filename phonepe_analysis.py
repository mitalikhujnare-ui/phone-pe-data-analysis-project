import os
import json
import sqlite3

import pandas as pd
from git import Repo


REPOSITORY_URL = "https://github.com/PhonePe/pulse.git"
DESTINATION = "phonepe_pulse_data"
CSV_FILE = "aggregated_transaction.csv"
DATABASE_FILE = "phonepe_pulse.db"


# Clone or update the repository
if not os.path.exists(DESTINATION):
    print("Cloning PhonePe Pulse repository...")
    Repo.clone_from(REPOSITORY_URL, DESTINATION)
else:
    print("Updating PhonePe Pulse repository...")
    repo = Repo(DESTINATION)
    repo.remotes.origin.pull()


transaction_path = os.path.join(
    DESTINATION,
    "data",
    "aggregated",
    "transaction",
    "country",
    "india",
    "state",
)

transactions = []

for state_name in os.listdir(transaction_path):
    state_path = os.path.join(transaction_path, state_name)

    if not os.path.isdir(state_path):
        continue

    for year_name in os.listdir(state_path):
        year_path = os.path.join(state_path, year_name)

        if not os.path.isdir(year_path) or not year_name.isdigit():
            continue

        for filename in os.listdir(year_path):
            if not filename.endswith(".json"):
                continue

            file_path = os.path.join(year_path, filename)

            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)
            except (json.JSONDecodeError, OSError) as error:
                print(f"Skipping {file_path}: {error}")
                continue

            quarter = filename.replace(".json", "")
            quarter = quarter if quarter.startswith("Q") else f"Q{quarter}"

            transaction_data = data.get("data", {}).get("transactionData", [])

            for item in transaction_data:
                instruments = item.get("paymentInstruments", {})

                transaction_count = 0
                transaction_amount = 0

                if isinstance(instruments, dict):
                    transaction_count = instruments.get("count", 0)
                    transaction_amount = instruments.get("amount", 0)

                elif isinstance(instruments, list):
                    for instrument in instruments:
                        transaction_count += instrument.get("count", 0)
                        transaction_amount += instrument.get("amount", 0)

                transactions.append({
                    "State": state_name.replace("-", " ").title(),
                    "Year": int(year_name),
                    "Quarter": quarter,
                    "Transaction_Type": item.get("name", "Unknown"),
                    "Transaction_Count": transaction_count,
                    "Transaction_Amount": transaction_amount,
                })


df = pd.DataFrame(transactions)

if df.empty:
    raise RuntimeError("No aggregated transaction data was extracted.")

df.to_csv(CSV_FILE, index=False)

# SQLite database setup
connection = sqlite3.connect(DATABASE_FILE)

connection.execute("""
CREATE TABLE IF NOT EXISTS aggregated_transaction (
    State VARCHAR(100),
    Year INTEGER,
    Quarter VARCHAR(10),
    Transaction_Type VARCHAR(100),
    Transaction_Count BIGINT,
    Transaction_Amount NUMERIC(18, 2)
);
""")

connection.execute("DELETE FROM aggregated_transaction")

df.to_sql(
    "aggregated_transaction",
    connection,
    if_exists="append",
    index=False,
)

top_states = pd.read_sql_query(
    """
    SELECT
        State,
        SUM(Transaction_Amount) AS Total_Revenue,
        SUM(Transaction_Count) AS Total_Volume
    FROM aggregated_transaction
    GROUP BY State
    ORDER BY Total_Revenue DESC
    LIMIT 5;
    """,
    connection,
)

connection.close()

print(f"\nExtracted {len(df):,} transaction records.")
print(f"CSV created: {CSV_FILE}")
print(f"SQLite database created: {DATABASE_FILE}")
print("\nTop 5 states by transaction amount:")
print(top_states.to_string(index=False))
