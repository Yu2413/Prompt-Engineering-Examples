import pandas as pd
from pandasgui import show

# Load the dataset
file_path = r"C:\VS Code Repo\Python\my_venv\CSV\orders.csv"
orders1 = pd.read_csv(file_path)

# --- Quick Exploratory Checks ---
print("\n📄 Columns:")
print(orders1.columns)

print("\n📊 Summary Statistics:")
print(orders1.describe())

print("\n🌍 Unique Countries:")
print(orders1["Country"].unique())

# --- Examples of useful filters ---
query_products = orders1[orders1["Product"] == "Laptop"]
query_large_orders = orders1[orders1["Quantity"] > 10]
query_select_countries = orders1[orders1["Country"].isin(["USA", "UK", "Germany"])]

# --- Show GUI (optional) ---
# show(orders1)