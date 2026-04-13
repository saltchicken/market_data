import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def visualize_atr():
    # Load environment variables (DB_URL)
    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        print("Error: Missing DB_URL environment variable.")
        return

    # Create the database connection
    engine = create_engine(db_url)

    # Query the data for the past 1 month for IONR
    query = text("""
        SELECT market_date, atr_14
        FROM daily_indicators
        WHERE ticker = 'IONR'
          AND market_date >= (CURRENT_DATE - INTERVAL '1 month')
        ORDER BY market_date ASC;
    """)

    # Read the query results into a pandas DataFrame
    print("Fetching data from the database...")
    df = pd.read_sql(query, engine)

    if df.empty:
        print(
            "No data found for IONR in the past month. Ensure your database is updated."
        )
        return

    # Ensure market_date is treated as a datetime object for better plotting
    df["market_date"] = pd.to_datetime(df["market_date"])

    # --- Plotting with Seaborn ---
    print(f"Plotting {len(df)} data points...")

    # Apply a custom Dark Theme using Seaborn
    sns.set_theme(
        style="darkgrid",
        rc={
            "figure.facecolor": "#121212",
            "axes.facecolor": "#1e1e1e",
            "axes.edgecolor": "#333333",
            "grid.color": "#333333",
            "text.color": "#ffffff",
            "axes.labelcolor": "#ffffff",
            "xtick.color": "#ffffff",
            "ytick.color": "#ffffff",
        },
    )

    # Remove the default Matplotlib toolbar at the bottom
    plt.rcParams["toolbar"] = "None"

    plt.figure(figsize=(10, 6))

    # Create a line plot with markers using a neon color that pops on dark backgrounds
    sns.lineplot(
        data=df, x="market_date", y="atr_14", marker="o", color="#00e5ff", linewidth=2
    )

    # Formatting the chart
    plt.title(
        "IONR - Average True Range (14-Day) Over the Past Month",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Market Date", fontsize=12)
    plt.ylabel("ATR 14", fontsize=12)
    plt.xticks(rotation=45)
    plt.tight_layout()  # Adjusts layout to prevent clipping of tick labels

    # Display the chart
    plt.show()


if __name__ == "__main__":
    visualize_atr()
