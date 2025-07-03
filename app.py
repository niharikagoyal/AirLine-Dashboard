import requests
import pandas as pd
from flask import Flask, render_template, request
import plotly.express as px
from datetime import datetime, timedelta
import random
# import openai  # For GPT integration (optional)

app = Flask(__name__)

# 🔐 Optional: Add your OpenAI key
# openai.api_key = "YOUR_OPENAI_API_KEY"

def fetch_live_data():
    url = "https://opensky-network.org/api/states/all"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        states = data.get('states', [])
        df = pd.DataFrame(states, columns=[
            'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
            'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity',
            'heading', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk',
            'spi', 'position_source'
        ])
        df = df[['callsign', 'origin_country', 'longitude', 'latitude', 'velocity']]
        df = df.dropna()

        # Mock timestamp and destinations
        df['timestamp'] = pd.to_datetime(datetime.utcnow()) - pd.to_timedelta(
            [random.randint(0, 3600) for _ in range(len(df))], unit='s'
        )
        destinations = ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide']
        df['destination'] = [random.choice(destinations) for _ in range(len(df))]
        df['price'] = df['velocity'] * random.uniform(0.8, 1.2)
        return df
    else:
        return pd.DataFrame()

# 🧠 Insight generator (ChatGPT API + fallback)
def generate_summary(df):
    top_dest = df['destination'].value_counts().idxmax()
    top_origin = df['origin_country'].value_counts().idxmax()
    avg_price = round(df['price'].mean(), 2)
    total_flights = len(df)

    prompt = (f"We have {total_flights} airline booking entries. "
              f"The top destination is {top_dest}, and the most frequent origin is {top_origin}. "
              f"The average simulated ticket price is ${avg_price}. Generate a market insight in 2 lines.")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return (f"Most bookings are headed to **{top_dest}**, with frequent departures from **{top_origin}**. "
                f"The average price is **${avg_price}**, indicating moderate demand.")

@app.route('/')
def index():
    df = fetch_live_data()
    if df.empty:
        return render_template("index.html", error="Failed to fetch flight data.")

    # 🔍 Get filters from query params
    origin_filter = request.args.get('origin')
    destination_filter = request.args.get('destination')

    if origin_filter:
        df = df[df['origin_country'].str.contains(origin_filter, case=False, na=False)]
    if destination_filter:
        df = df[df['destination'].str.contains(destination_filter, case=False, na=False)]

    # 📊 Popular Routes - Grouped bar chart
    top_routes_df = df.groupby(['origin_country', 'destination']).size().reset_index(name='count')
    top_routes = top_routes_df.sort_values('count', ascending=False).head(10)
    fig_routes = px.bar(top_routes, x='destination', y='count',
                        color='origin_country', barmode='group',
                        title='Top 10 Popular Routes')
    chart_routes = fig_routes.to_html(full_html=False)

    # 💰 Price Trends - Line chart of average price over time
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    price_trends = df.groupby(['destination', pd.Grouper(key='timestamp', freq='15Min')])['price'].mean().reset_index()
    fig_price = px.line(price_trends, x='timestamp', y='price', color='destination',
                        title='Price Trends Over Time by Destination',
                        labels={'timestamp': 'Time', 'price': 'Avg Price'})
    chart_price = fig_price.to_html(full_html=False)

    # ⏰ High-Demand Periods - Hourly demand per destination
    df['hour'] = df['timestamp'].dt.hour
    hourly_counts = df.groupby(['hour', 'destination']).size().reset_index(name='Flight Count')
    fig_demand = px.bar(hourly_counts, x='hour', y='Flight Count', color='destination',
                        barmode='group', title='Hourly Flight Demand by Destination')
    chart_demand = fig_demand.to_html(full_html=False)

    # 🧠 Insight Summary
    summary = generate_summary(df)

    return render_template("index.html",
                           chart_routes=chart_routes,
                           chart_price=chart_price,
                           chart_demand=chart_demand,
                           top_routes=top_routes.to_dict(orient='records'),
                           summary=summary)

if __name__ == "__main__":
    app.run(debug=True)
