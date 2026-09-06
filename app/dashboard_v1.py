import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path

# 1. Page Config
st.set_page_config(page_title="Olist Analytics Hub", layout="wide", initial_sidebar_state="expanded")

# 2. Load Environment Variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# 3. Database Connection
@st.cache_resource
def init_connection():
    db_uri = os.getenv("INSFORGE_DB_URI")
    if not db_uri:
        st.error("Database connection string not found. Check your .env file.")
        st.stop()
    if db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg2://")
    return create_engine(db_uri)

engine = init_connection()

# 4. Sidebar Navigation & Filters
st.sidebar.title("Navigation")
page = st.sidebar.radio("", ["Sales & Marketplace", "Logistics & Delivery", "Seller Performance"])

st.sidebar.markdown("---")
st.sidebar.title("Filters")

@st.cache_data
def get_filter_bounds():
    date_query = "SELECT MIN(DATE(order_purchase_timestamp)) as min_date, MAX(DATE(order_purchase_timestamp)) as max_date FROM orders WHERE order_status = 'delivered'"
    state_query = "SELECT DISTINCT customer_state FROM customers ORDER BY customer_state"
    dates = pd.read_sql(date_query, engine)
    states = pd.read_sql(state_query, engine)['customer_state'].tolist()
    return dates['min_date'].iloc[0], dates['max_date'].iloc[0], states

min_date, max_date, all_states = get_filter_bounds()

# Date Range Slicer
date_range = st.sidebar.date_input("Year / Date Range", [min_date, max_date], min_value=min_date, max_value=max_date)
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# State Multi-Select Filter
selected_states = st.sidebar.multiselect("State", all_states, default=all_states)
if not selected_states:
    selected_states = all_states 
states_str = str(tuple(selected_states)) if len(selected_states) > 1 else f"('{selected_states[0]}')"

# 5. Core Data Loading Functions
@st.cache_data
def load_main_kpis(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        COUNT(DISTINCT i.seller_id) AS active_sellers,
        COUNT(DISTINCT o.order_id) AS total_orders,
        SUM(i.price) AS total_revenue,
        (SUM(i.price) / NULLIF(COUNT(DISTINCT o.order_id), 0)) AS avg_order_value
    FROM orders o
    JOIN order_items i ON o.order_id = i.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
      AND c.customer_state IN {states_formatted};
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_sales_trajectory(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        DATE_TRUNC('month', o.order_purchase_timestamp::timestamp) AS month,
        SUM(i.price) AS total_sales
    FROM orders o
    JOIN order_items i ON o.order_id = i.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
      AND c.customer_state IN {states_formatted}
    GROUP BY month
    ORDER BY month;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_geo_sales(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        c.customer_state AS state,
        SUM(i.price) AS total_sales
    FROM orders o
    JOIN order_items i ON o.order_id = i.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
      AND c.customer_state IN {states_formatted}
    GROUP BY state
    ORDER BY total_sales DESC
    LIMIT 10;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_seller_leaderboard(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        i.seller_id,
        ROUND(SUM(i.price)::numeric, 2) AS total_sales,
        COUNT(DISTINCT o.order_id) AS total_orders,
        ROUND((SUM(i.price) / COUNT(DISTINCT o.order_id))::numeric, 2) AS avg_order_value
    FROM orders o
    JOIN order_items i ON o.order_id = i.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
      AND c.customer_state IN {states_formatted}
    GROUP BY i.seller_id
    ORDER BY total_sales DESC
    LIMIT 15;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_delivery_impact():
    """Calculates average review score based on delivery punctuality."""
    query = """
    WITH delivery_status AS (
        SELECT 
            o.order_id,
            CASE 
                WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'Late Delivery'
                ELSE 'On Time / Early'
            END AS punctuality,
            r.review_score
        FROM orders o
        JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_status = 'delivered' 
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_estimated_delivery_date IS NOT NULL
    )
    SELECT 
        punctuality,
        ROUND(AVG(review_score)::numeric, 2) AS avg_review_score,
        COUNT(order_id) AS order_volume
    FROM delivery_status
    GROUP BY punctuality;
    """
    return pd.read_sql(query, engine)


# 6. UI Rendering based on Navigation
kpis = load_main_kpis(start_date, end_date, states_str)

# Global Top KPI Row ( card style display)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Sellers", f"{kpis['active_sellers'].iloc[0]:,}")
col2.metric("Avg Order Value", f"${kpis['avg_order_value'].iloc[0]:,.2f}")
col3.metric("Total Orders", f"{kpis['total_orders'].iloc[0]:,}")
col4.metric("Total Sales", f"${kpis['total_revenue'].iloc[0]:,.2f}")

st.divider()

if page == "Sales & Marketplace":
    row1_col1, row1_col2 = st.columns((2, 1))
    
    with row1_col1:
        st.subheader("Sales Growth Trajectory")
        sales_trend = load_sales_trajectory(start_date, end_date, states_str)
        if not sales_trend.empty:
            st.line_chart(data=sales_trend.set_index("month"), y="total_sales", use_container_width=True)
            
    with row1_col2:
        st.subheader("Geographical Sales Distribution")
        geo_data = load_geo_sales(start_date, end_date, states_str)
        if not geo_data.empty:
            st.bar_chart(data=geo_data.set_index("state"), y="total_sales", use_container_width=True)

elif page == "Logistics & Delivery":
    st.subheader("Logistics Performance Hub")
    st.markdown("Analyzing how shipping delays impact seller ratings[cite: 3].")
    try:
        delivery_data = load_delivery_impact()
        if not delivery_data.empty:
            col_chart, col_table = st.columns(2)
            with col_chart:
                st.bar_chart(data=delivery_data.set_index("punctuality"), y="avg_review_score")
            with col_table:
                st.dataframe(delivery_data, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Failed to load delivery impact data: {e}")

elif page == "Seller Performance":
    st.subheader("Seller Leaderboard: Revenue & Volume")
    leaderboard = load_seller_leaderboard(start_date, end_date, states_str)
    if not leaderboard.empty:
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)