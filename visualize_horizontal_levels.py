import os
import sys
import argparse
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

try:
    import plotly.graph_objects as go
except ImportError:
    print(
        "Plotly is required for visualization. Please install it using: pip install plotly"
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize Support & Resistance Levels on a Candlestick Chart."
    )
    parser.add_argument(
        "--ticker",
        "-t",
        type=str,
        required=True,
        help="Specific ticker to visualize (e.g., AAPL)",
    )
    parser.add_argument(
        "--sql_file",
        "-s",
        type=str,
        default="sql/horizontal_levels.sql",
        help="Path to the horizontal levels SQL file",
    )
    args = parser.parse_args()

    ticker = args.ticker.upper()
    sql_file = args.sql_file

    if not os.path.exists(sql_file):
        print(f"Error: Could not find SQL file '{sql_file}'")
        sys.exit(1)

    load_dotenv()
    db_url = os.getenv("DB_URL")

    if not db_url:
        print("Error: Missing DB_URL in .env file.")
        sys.exit(1)

    engine = create_engine(db_url)

    # 1. Fetch the base OHLC price data for the candlestick chart
    print(f"Fetching recent price data for {ticker}...")
    ohlc_query = text("""
        SELECT market_date, open, high, low, close 
        FROM daily_market_data 
        WHERE ticker = :ticker
          AND market_date >= (
              SELECT MAX(market_date) - INTERVAL '90 days' 
              FROM daily_market_data 
              WHERE ticker = :ticker
          )
        ORDER BY market_date ASC
    """)

    try:
        ohlc_df = pd.read_sql(ohlc_query, engine, params={"ticker": ticker})
        if ohlc_df.empty:
            print(f"No price data found for {ticker}.")
            sys.exit(1)
    except Exception as e:
        print(f"Error fetching OHLC data:\n{e}")
        sys.exit(1)

    # 2. Fetch the Support / Resistance levels using the provided SQL file
    print(f"Executing {sql_file} to find horizontal levels...")
    with open(sql_file, "r") as file:
        query_text = file.read()

    try:
        levels_df = pd.read_sql(text(query_text), engine, params={"ticker": ticker})
    except Exception as e:
        print(f"Error running levels query:\n{e}")
        sys.exit(1)

    print(f"Found {len(levels_df)} horizontal levels. Generating chart...\n")

    # 3. Build the Plotly Candlestick Chart
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=ohlc_df["market_date"],
                open=ohlc_df["open"],
                high=ohlc_df["high"],
                low=ohlc_df["low"],
                close=ohlc_df["close"],
                name="Price Action",
            )
        ]
    )

    # 4. Overlay the Support and Resistance levels as line segments
    # We draw them starting from the date they were formed (swing high/low) to the latest date
    latest_date = ohlc_df["market_date"].max()

    for _, row in levels_df.iterrows():
        is_resistance = row["level_type"] == "Resistance"
        line_color = "rgba(255, 0, 0, 0.7)" if is_resistance else "rgba(0, 255, 0, 0.7)"

        # Add a line shape starting exactly on the market_date of the peak/trough
        fig.add_shape(
            type="line",
            x0=row["market_date"],
            y0=row["price_level"],
            x1=latest_date,
            y1=row["price_level"],
            line=dict(color=line_color, width=2, dash="dash"),
        )

        # Add an annotation label at the beginning of the line
        fig.add_annotation(
            x=row["market_date"],
            y=row["price_level"],
            text=f"{row['level_type']} (${row['price_level']})",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor=line_color,
            ax=0,
            ay=(
                -20 if is_resistance else 20
            ),  # Text above for Resistance, below for Support
            font=dict(color=line_color, size=11),
        )

    # Clean up the chart layout for a better financial look
    fig.update_layout(
        title=f"{ticker} - 2-Month Support & Resistance Levels",
        yaxis_title="Price ($)",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",  # Looks great for financial charts
        margin=dict(l=50, r=50, t=50, b=50),
    )

    # 5. Open the interactive HTML graph in the browser
    fig.show()


if __name__ == "__main__":
    main()
