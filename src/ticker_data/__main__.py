import financedatabase as fd
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

# 1. Fetch the data and tag them with their asset class
print("Fetching Equities from financedatabase...")
equities = fd.Equities().select()
equities['asset_class'] = 'Equity'

print("Fetching ETFs from financedatabase...")
etfs = fd.ETFs().select()
etfs['asset_class'] = 'ETF'

print("Fetching Funds from financedatabase...")
funds = fd.Funds().select()
funds['asset_class'] = 'Fund'

print("Fetching Cryptos from financedatabase...")
cryptos = fd.Cryptos().select()
cryptos['asset_class'] = 'Crypto'

print("Fetching Indices from financedatabase...")
indices = fd.Indices().select()
indices['asset_class'] = 'Index'

print("Fetching Currencies from financedatabase...")
currencies = fd.Currencies().select()
currencies['asset_class'] = 'Currency'

print("Fetching Money Markets from financedatabase...")
money_markets = fd.Moneymarkets().select()
money_markets['asset_class'] = 'Money Market'

# Combine all the fetched dataframes into one single dataframe
print("Combining datasets...")
df = pd.concat([equities, etfs, funds, cryptos, indices, currencies, money_markets])

# 2. Clean and format the DataFrame for PostgreSQL
# The ticker is currently the index, so we turn it into a regular column
df.reset_index(names='ticker', inplace=True)

# PostgreSQL strongly prefers lowercase column names without spaces
df.columns = df.columns.str.lower()
df.columns = df.columns.str.replace(' ', '_')

# Define the exact columns you requested, including the new 'asset_class'
columns_to_keep = [
    'ticker', 'asset_class', 'name', 'summary', 'currency', 'sector', 
    'industry_group', 'industry', 'exchange', 'market', 
    'country', 'website', 'market_cap'
]

# Keep only the columns that exist in the dataframe to avoid KeyError
existing_columns = [col for col in columns_to_keep if col in df.columns]
df_clean = df[existing_columns]

# 3. Connect to PostgreSQL and insert the data
load_dotenv()
DB_URL = os.getenv("DB_URL")
engine = create_engine(DB_URL)

# Write the data to the table
print("Writing data to PostgreSQL...")
# if_exists='replace' will drop the table and recreate it. 
# This means your PostgreSQL schema will automatically update to include the new 'asset_class' column!
df_clean.to_sql('financedatabase', engine, if_exists='replace', index=False)

print("Successfully loaded combined asset data into PostgreSQL!")
