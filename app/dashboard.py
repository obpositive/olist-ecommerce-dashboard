import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta, date 
import plotly.express as px
import plotly.graph_objects as go

# 1. Page Config & Custom CSS
st.set_page_config(page_title="Olist Analytics Hub", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        background-color: #1e2130;
        border: 1px solid #333a4d;
        padding: 24px 20px;
        border-radius: 12px;
        border-top: 4px solid #00cecb;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        text-align: center;
        margin-bottom: 1rem;
    }
    div[data-testid="metric-container"] label { font-size: 1.1rem !important; color: #a0aec0 !important; margin-bottom: 0.5rem; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { font-size: 2.4rem !important; font-weight: 700 !important; color: #ffffff !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricDelta"] { font-size: 1.1rem !important; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 95%; }
    h1 { margin-bottom: 0.5rem; }
    h3 { color: #e5e9f0; font-weight: 500; margin-bottom: 1rem; font-size: 1.4rem; }
    .stPlotlyChart { margin-bottom: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

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
        
    # pool_pre_ping=True automatically tests connections and rolls back invalid ones
    return create_engine(db_uri, pool_pre_ping=True)

engine = init_connection()

# 4. Sidebar Navigation & Filters
with st.sidebar:
    st.markdown("# <u> Olist Marketplace Intelligence</u>", unsafe_allow_html=True)
    st.markdown("---", unsafe_allow_html=True)
    st.markdown("## 🧭 Report Navigation")
    page = st.radio("", ["Sales & Marketplace", "Logistics & Delivery", "Seller Performance", "Customer Insights", "Product Quality"], label_visibility="collapsed")    
    st.markdown("---")
    st.markdown("## 🎛️ Filters")

    @st.cache_data
    def get_filter_bounds():
        date_query = "SELECT MIN(DATE(order_purchase_timestamp)) as min_date, MAX(DATE(order_purchase_timestamp)) as max_date FROM orders WHERE order_status = 'delivered'"
        state_query = "SELECT DISTINCT customer_state FROM customers ORDER BY customer_state"
        dates = pd.read_sql(date_query, engine)
        states = pd.read_sql(state_query, engine)['customer_state'].tolist()
        
        # Explicitly convert Pandas outputs to native Python datetime.date objects
        min_d = pd.to_datetime(dates['min_date'].iloc[0]).date()
        max_d = pd.to_datetime(dates['max_date'].iloc[0]).date()
        
        return min_d, max_d, states

    min_date, max_date, all_states = get_filter_bounds()

    
    # Use Pandas to pad the maximum selectable date to the end of the year
    padded_max_value = pd.to_datetime(f"{max_date.year}-12-31").date()
    
    # Pass the padded value to max_value, but keep the actual max_date in the value tuple
    date_range = st.date_input(
        "🗓️ Order Date Range", 
        value=(min_date, max_date), 
        min_value=min_date, 
        max_value=padded_max_value
    )
    
    # Handle Streamlit's state when a user has only clicked once
    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        # If they only clicked once, fall back to that single day for both bounds
        start_date = date_range[0]
        end_date = date_range[0]

    state_options = ["All"] + all_states
    selected_states = st.multiselect("📍 Customer State", state_options, default=["All"])
    
    if "All" in selected_states or not selected_states:
        final_states = all_states
    else:
        final_states = selected_states

    states_str = str(tuple(final_states)) if len(final_states) > 1 else f"('{final_states[0]}')"

# 5. Core Data Loading Functions
@st.cache_data
def load_main_kpis_with_deltas(start_d, end_d, states_formatted):
    """Calculates KPIs for the selected period and the immediately preceding period of equal length."""
    delta_days = (end_d - start_d).days
    prev_end = start_d - timedelta(days=1)
    prev_start = prev_end - timedelta(days=delta_days)

    query = f"""
    WITH current_period AS (
        SELECT 'Current' as period, COUNT(DISTINCT i.seller_id) AS active_sellers, COUNT(DISTINCT o.order_id) AS total_orders, COALESCE(SUM(i.price), 0) AS total_revenue, COALESCE((SUM(i.price) / NULLIF(COUNT(DISTINCT o.order_id), 0)), 0) AS avg_order_value
        FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered' AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s AND c.customer_state IN {states_formatted}
    ),
    previous_period AS (
        SELECT 'Previous' as period, COUNT(DISTINCT i.seller_id) AS active_sellers, COUNT(DISTINCT o.order_id) AS total_orders, COALESCE(SUM(i.price), 0) AS total_revenue, COALESCE((SUM(i.price) / NULLIF(COUNT(DISTINCT o.order_id), 0)), 0) AS avg_order_value
        FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered' AND DATE(o.order_purchase_timestamp::timestamp) >= %(p_start)s AND DATE(o.order_purchase_timestamp::timestamp) <= %(p_end)s AND c.customer_state IN {states_formatted}
    )
    SELECT * FROM current_period UNION ALL SELECT * FROM previous_period;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d, "p_start": prev_start, "p_end": prev_end})

@st.cache_data
def load_sales_trajectory(start_d, end_d, states_formatted):
    query = f"""
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp::timestamp) AS month, SUM(i.price) AS total_sales
    FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered' AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s AND c.customer_state IN {states_formatted}
    GROUP BY month ORDER BY month;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_geo_sales(start_d, end_d, states_formatted):
    query = f"""
    SELECT c.customer_state AS state, SUM(i.price) AS total_sales
    FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered' AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s AND c.customer_state IN {states_formatted}
    GROUP BY state ORDER BY total_sales DESC LIMIT 10;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_category_matrix(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        ct.product_category_name_english AS category, 
        COUNT(DISTINCT o.order_id) AS total_orders, 
        SUM(i.price) AS total_revenue, 
        AVG(i.price) AS avg_order_value
    FROM orders o 
    JOIN order_items i ON o.order_id = i.order_id 
    JOIN products p ON i.product_id = p.product_id 
    JOIN category_translation ct ON p.product_category_name = ct.product_category_name 
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered' 
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s 
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s 
      AND c.customer_state IN {states_formatted}
    GROUP BY category
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_top_categories_table(start_d, end_d, states_formatted):
    query = f"""
    SELECT 
        COALESCE(ct.product_category_name_english, 'Unknown') AS category, 
        COUNT(i.order_item_id) AS units_sold, 
        SUM(i.price) AS total_revenue
    FROM orders o 
    JOIN order_items i ON o.order_id = i.order_id 
    JOIN products p ON i.product_id = p.product_id 
    LEFT JOIN category_translation ct ON p.product_category_name = ct.product_category_name 
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered' 
      AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s 
      AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s 
      AND c.customer_state IN {states_formatted}
    GROUP BY category 
    ORDER BY total_revenue DESC 
    LIMIT 10
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_seller_leaderboard(start_d, end_d, states_formatted):
    query = f"""
    SELECT i.seller_id, ROUND(SUM(i.price)::numeric, 2) AS total_sales, COUNT(DISTINCT o.order_id) AS total_orders, ROUND((SUM(i.price) / COUNT(DISTINCT o.order_id))::numeric, 2) AS avg_order_value
    FROM orders o JOIN order_items i ON o.order_id = i.order_id JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered' AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s AND c.customer_state IN {states_formatted}
    GROUP BY i.seller_id ORDER BY total_sales DESC LIMIT 20;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_delivery_impact():
    query = """
    WITH delivery_status AS (
        SELECT o.order_id,
        CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 'Late Delivery' ELSE 'On Time / Early' END AS punctuality,
        r.review_score
        FROM orders o JOIN order_reviews r ON o.order_id = r.order_id
        WHERE o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL AND o.order_estimated_delivery_date IS NOT NULL
    )
    SELECT punctuality, ROUND(AVG(review_score)::numeric, 2) AS avg_review_score, COUNT(order_id) AS order_volume
    FROM delivery_status GROUP BY punctuality;
    """
    return pd.read_sql(query, engine)

@st.cache_data
def load_rfm_summary(start_d, end_d, states_formatted):
    query = f"""
    WITH rfm_base AS (
        SELECT 
            c.customer_unique_id,
            MAX(DATE(o.order_purchase_timestamp::timestamp)) AS last_purchase_date,
            COUNT(DISTINCT o.order_id) AS frequency,
            SUM(i.price) AS monetary
        FROM orders o
        JOIN order_items i ON o.order_id = i.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
          AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
          AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
          AND c.customer_state IN {states_formatted}
        GROUP BY c.customer_unique_id
    ),
    rfm_calc AS (
        SELECT 
            customer_unique_id,
            %(end)s - last_purchase_date AS recency,
            frequency,
            monetary
        FROM rfm_base
    ),
    rfm_segments AS (
        SELECT 
            customer_unique_id,
            recency,
            frequency,
            monetary,
            CASE 
                WHEN recency <= 30 AND frequency >= 2 THEN 'Champions'
                WHEN recency <= 90 AND frequency >= 2 THEN 'Loyal Customers'
                WHEN recency <= 90 AND frequency = 1 THEN 'Recent One-Time'
                WHEN recency > 90 AND recency <= 180 AND frequency >= 2 THEN 'At Risk (Loyal)'
                WHEN recency > 180 AND frequency >= 2 THEN 'Churned (Loyal)'
                ELSE 'Churned One-Time'
            END AS segment
        FROM rfm_calc
    )
    SELECT 
        segment,
        COUNT(customer_unique_id) AS total_customers,
        ROUND(AVG(monetary)::numeric, 2) AS avg_ltv,
        ROUND(SUM(monetary)::numeric, 2) AS total_revenue
    FROM rfm_segments
    GROUP BY segment
    ORDER BY total_revenue DESC;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_cohort_retention(start_d, end_d, states_formatted):
    query = f"""
    WITH first_purchase AS (
        SELECT 
            c.customer_unique_id,
            DATE_TRUNC('month', MIN(o.order_purchase_timestamp::timestamp)) AS cohort_month
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered' AND c.customer_state IN {states_formatted}
        GROUP BY c.customer_unique_id
    ),
    purchases AS (
        SELECT 
            c.customer_unique_id,
            DATE_TRUNC('month', o.order_purchase_timestamp::timestamp) AS purchase_month
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered' AND c.customer_state IN {states_formatted}
    ),
    cohort_data AS (
        SELECT 
            fp.cohort_month,
            EXTRACT(YEAR FROM p.purchase_month) * 12 + EXTRACT(MONTH FROM p.purchase_month) - 
            (EXTRACT(YEAR FROM fp.cohort_month) * 12 + EXTRACT(MONTH FROM fp.cohort_month)) AS month_index,
            fp.customer_unique_id
        FROM first_purchase fp
        JOIN purchases p ON fp.customer_unique_id = p.customer_unique_id
    ),
    cohort_sizes AS (
        SELECT cohort_month, COUNT(DISTINCT customer_unique_id) AS initial_size
        FROM first_purchase
        GROUP BY cohort_month
    ),
    retention_counts AS (
        SELECT cohort_month, month_index, COUNT(DISTINCT customer_unique_id) AS retained_customers
        FROM cohort_data
        GROUP BY cohort_month, month_index
    )
    SELECT 
        r.cohort_month,
        s.initial_size,
        r.month_index,
        r.retained_customers,
        ROUND((r.retained_customers::numeric / s.initial_size) * 100, 2) AS retention_rate
    FROM retention_counts r
    JOIN cohort_sizes s ON r.cohort_month = s.cohort_month
    WHERE DATE(r.cohort_month) >= %(start)s AND DATE(r.cohort_month) <= %(end)s
    ORDER BY r.cohort_month, r.month_index;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

@st.cache_data
def load_category_reviews(start_d, end_d, states_formatted):
    query = f"""
    WITH category_reviews AS (
        SELECT 
            ct.product_category_name_english AS category,
            r.review_score,
            o.order_id
        FROM orders o
        JOIN order_items i ON o.order_id = i.order_id
        JOIN products p ON i.product_id = p.product_id
        JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        JOIN order_reviews r ON o.order_id = r.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_status = 'delivered'
          AND ct.product_category_name_english IS NOT NULL
          AND DATE(o.order_purchase_timestamp::timestamp) >= %(start)s
          AND DATE(o.order_purchase_timestamp::timestamp) <= %(end)s
          AND c.customer_state IN {states_formatted}
    )
    SELECT 
        category,
        COUNT(DISTINCT order_id) AS total_orders,
        ROUND(AVG(review_score)::numeric, 2) AS avg_review_score,
        ROUND((SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END)::numeric / COUNT(DISTINCT order_id)) * 100, 2) AS negative_review_rate
    FROM category_reviews
    GROUP BY category
    HAVING COUNT(DISTINCT order_id) > 50
    ORDER BY negative_review_rate DESC
    LIMIT 15;
    """
    return pd.read_sql(query, engine, params={"start": start_d, "end": end_d})

# 6. Helper for KPI Deltas
def get_delta(curr, prev):
    if prev == 0 or pd.isna(prev): return None
    return f"{((curr - prev) / prev) * 100:.1f}%"

def format_currency(num):
    if pd.isna(num):
        return "$0.00"
    if num >= 1_000_000:
        return f"${num / 1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num / 1_000:.2f}K"
    return f"${num:,.2f}"

# 7. UI Rendering
st.markdown("# <u style='color:DodgerBlue;'> Olist Marketplace Intelligence </u>", unsafe_allow_html=True)
st.markdown("Monitor performance, optimize logistics, and analyze end-to-end analytical pipeline metrics.", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# Global Top KPI Row with Period-over-Period Deltas
kpis = load_main_kpis_with_deltas(start_date, end_date, states_str)
curr_kpi = kpis[kpis['period'] == 'Current'].iloc[0]
prev_kpi = kpis[kpis['period'] == 'Previous'].iloc[0]

col1, col2, col3, col4 = st.columns(4, gap="large")
col1.metric("Active Sellers", f"{int(curr_kpi['active_sellers']):,}", get_delta(curr_kpi['active_sellers'], prev_kpi['active_sellers']))
col2.metric("Avg Order Value", f"${curr_kpi['avg_order_value']:,.2f}", get_delta(curr_kpi['avg_order_value'], prev_kpi['avg_order_value']))
col3.metric("Total Orders", f"{int(curr_kpi['total_orders']):,}", get_delta(curr_kpi['total_orders'], prev_kpi['total_orders']))
# col4.metric("Total Sales", f"${curr_kpi['total_revenue']:,.2f}", get_delta(curr_kpi['total_revenue'], prev_kpi['total_revenue']))
col4.metric("Total Sales", format_currency(curr_kpi['total_revenue']), get_delta(curr_kpi['total_revenue'], prev_kpi['total_revenue']))

st.markdown("<hr style='border:1px solid #2e3440; margin-top:0.5rem; margin-bottom:2rem;'>", unsafe_allow_html=True)

if page == "Sales & Marketplace":
    # --- ROW 1: Trends and Geography ---
    row1_col1, row1_col2 = st.columns([6, 4], gap="large") 
    
    with row1_col1:
        st.markdown("### Sales Growth Trajectory")
        sales_trend = load_sales_trajectory(start_date, end_date, states_str)
        if not sales_trend.empty:
            fig = px.line(sales_trend, x='month', y='total_sales', template="plotly_dark", color_discrete_sequence=['#00cecb'])
            fig.update_xaxes(showgrid=False, title="")
            fig.update_yaxes(showgrid=False, visible=False)
            fig.update_traces(mode="lines+markers", hovertemplate="<b>%{x|%b %Y}</b><br>Revenue: %{y:$,.2f}<extra></extra>")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            
    with row1_col2:
        st.markdown("### Core Geographic Markets")
        geo_data = load_geo_sales(start_date, end_date, states_str)
        if not geo_data.empty:
            fig_geo = px.bar(geo_data.sort_values('total_sales', ascending=True), x='total_sales', y='state', orientation='h', template="plotly_dark", color_discrete_sequence=['#007bff'])
            fig_geo.update_xaxes(showgrid=False, visible=False)
            fig_geo.update_yaxes(showgrid=False, title="")
            fig_geo.update_traces(texttemplate='%{x:$,.2s}', textposition='outside', hovertemplate="<b>%{y}</b><br>Revenue: %{x:$,.2f}<extra></extra>")
            fig_geo.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_geo, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- ROW 2: Categories and Products ---
    row2_col1, row2_col2 = st.columns([6, 4], gap="large")
    
    with row2_col1:
        st.markdown("### Category Performance Matrix")
        cat_matrix = load_category_matrix(start_date, end_date, states_str)
        if not cat_matrix.empty:
            fig_scatter = px.scatter(
                cat_matrix, x='total_orders', y='total_revenue', size='avg_order_value', 
                color_discrete_sequence=['#00cecb'], hover_name='category', template="plotly_dark",
                labels={"total_orders": "Total Orders", "total_revenue": "Total Revenue ($)"}
            )
            fig_scatter.update_traces(hovertemplate="<b>%{hovertext}</b><br>Orders: %{x:,}<br>Revenue: %{y:$,.2f}<br>Avg Order Value: %{marker.size:$,.2f}<extra></extra>")
            fig_scatter.update_layout(height=450, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            fig_scatter.update_xaxes(showgrid=True, gridcolor='#333a4d')
            fig_scatter.update_yaxes(showgrid=True, gridcolor='#333a4d')
            st.plotly_chart(fig_scatter, use_container_width=True)
            
    with row2_col2:
        st.markdown("### Top Grossing Categories")
        top_categories = load_top_categories_table(start_date, end_date, states_str)
        if not top_categories.empty:
            fig_prod_table = go.Figure(data=[go.Table(
                columnwidth=[150, 100, 120],
                header=dict(values=['<b>&nbsp;&nbsp;Category</b>', '<b>Units Sold</b>', '<b>Revenue</b>'], 
                            fill_color='#1e2130', align=['left', 'right', 'right'], font=dict(color='white', size=14), height=25),
                cells=dict(values=[top_categories.category, top_categories.units_sold.apply(lambda x: f"{x:,}"), top_categories.total_revenue.apply(lambda x: f"${x:,.2f}")], 
                           fill_color='#0e1117', align=['left', 'right', 'right'], font=dict(color='#e5e9f0', size=13), height=40))
            ])
            fig_prod_table.update_layout(height=450, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_prod_table, use_container_width=True)

elif page == "Logistics & Delivery":
    col_chart, col_table = st.columns([4, 6], gap="large")
    
    with col_chart:
        st.markdown("### Logistics Impact on Satisfaction")
        delivery_data = load_delivery_impact()
        if not delivery_data.empty:
            # Semantic colors: Red for Late, Cyan for On-Time
            fig_del = px.bar(delivery_data, x='punctuality', y='avg_review_score', text='avg_review_score', template="plotly_dark", color='punctuality', color_discrete_map={'Late Delivery': '#ff4b4b', 'On Time / Early': '#00cecb'})
            fig_del.update_xaxes(showgrid=False, title="")
            fig_del.update_yaxes(showgrid=False, visible=False, range=[0, 5])
            fig_del.update_traces(texttemplate='%{text:.2f} ★', textposition='outside', textfont_size=14, hovertemplate="<b>%{x}</b><br>Avg Score: %{y:.2f} ★<extra></extra>")
            fig_del.update_layout(height=450, showlegend=False, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_del, use_container_width=True)
            
    with col_table:
        st.markdown("### Delivery Punctuality Volume")
        if not delivery_data.empty:
            fig_table = go.Figure(data=[go.Table(
                header=dict(values=['<b>Delivery Status</b>', '<b>Avg Review Score</b>', '<b>Total Orders</b>'], fill_color='#1e2130', align='left', font=dict(color='white', size=16), height=45),
                cells=dict(values=[delivery_data.punctuality, delivery_data.avg_review_score.apply(lambda x: f"{x:.2f} ★"), delivery_data.order_volume.apply(lambda x: f"{x:,}")], fill_color='#0e1117', align='left', font=dict(color='#e5e9f0', size=15), height=40))
            ])
            fig_table.update_layout(height=450, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_table, use_container_width=True)

elif page == "Seller Performance":
    st.markdown("### Seller Leaderboard (Top 20 by Revenue)")
    leaderboard = load_seller_leaderboard(start_date, end_date, states_str)
    
    if not leaderboard.empty:
        # Utilize Progressive Disclosure (Expander) to keep the main UI clean
        with st.expander("Expand to view Full Data Grid", expanded=True):
            fig_leaderboard = go.Figure(data=[go.Table(
                columnwidth=[150, 100, 100, 100],
                header=dict(values=['<b>Seller ID</b>', '<b>Total Sales ($)</b>', '<b>Total Orders</b>', '<b>Avg Order Value ($)</b>'],
                            fill_color='#1e2130', align=['left', 'right', 'right', 'right'], font=dict(color='white', size=16), height=45),
                cells=dict(values=[leaderboard.seller_id, leaderboard.total_sales.apply(lambda x: f"${x:,.2f}"), leaderboard.total_orders, leaderboard.avg_order_value.apply(lambda x: f"${x:,.2f}")],
                           fill_color='#0e1117', align=['left', 'right', 'right', 'right'], font=dict(color='#e5e9f0', size=15), height=40))
            ])
            fig_leaderboard.update_layout(height=600, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_leaderboard, use_container_width=True)


elif page == "Customer Insights":
    st.markdown("### RFM Customer Segmentation")
    st.markdown("Grouping customers by Recency, Frequency, and Monetary value to identify high-value cohorts and churn risk.")
    rfm_data = load_rfm_summary(start_date, end_date, states_str)
    
    if not rfm_data.empty:
        col_chart, col_table = st.columns([6, 4], gap="large")
        
        with col_chart:
            # Treemap visualizes the scale of revenue per segment, color-coded by Average Lifetime Value
            fig_rfm = px.treemap(
                rfm_data, 
                path=[px.Constant("All Customers"), 'segment'], 
                values='total_revenue',
                color='avg_ltv', 
                color_continuous_scale='Teal',
                custom_data=['total_customers', 'avg_ltv']
            )
            fig_rfm.update_traces(hovertemplate="<b>%{label}</b><br>Total Revenue: %{value:$,.2f}<br>Customers: %{customdata[0]:,}<br>Avg LTV: %{customdata[1]:$,.2f}<extra></extra>")
            fig_rfm.update_layout(height=500, margin=dict(t=0, l=0, r=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_rfm, use_container_width=True)
        
        with col_table:
            fig_table = go.Figure(data=[go.Table(
                header=dict(values=['<b>Segment</b>', '<b>Customers</b>', '<b>Avg LTV ($)</b>'], fill_color='#1e2130', align='left', font=dict(color='white', size=15), height=45),
                cells=dict(values=[rfm_data.segment, rfm_data.total_customers.apply(lambda x: f"{x:,}"), rfm_data.avg_ltv.apply(lambda x: f"${x:,.2f}")], fill_color='#0e1117', align='left', font=dict(color='#e5e9f0', size=14), height=40))
            ])
            fig_table.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_table, use_container_width=True)

    st.markdown("<hr style='border:1px solid #2e3440; margin-top:2rem; margin-bottom:2rem;'>", unsafe_allow_html=True)
    st.markdown("### Cohort Retention Heatmap")
    st.markdown("Tracking the percentage of customers who return to make a repeat purchase in the months following their initial order.")
    
    cohort_data = load_cohort_retention(start_date, end_date, states_str)
    
    if not cohort_data.empty:
        # Filter to 12 months for a clean view, excluding Month 0 (which is always 100%)
        cohort_filtered = cohort_data[(cohort_data['month_index'] > 0) & (cohort_data['month_index'] <= 12)]
        
        if not cohort_filtered.empty:
            pivot_data = cohort_filtered.pivot(index='cohort_month', columns='month_index', values='retention_rate')
            pivot_data.index = pd.to_datetime(pivot_data.index).strftime('%Y-%m')
            
            fig_cohort = px.imshow(
                pivot_data,
                text_auto='.1f',
                aspect="auto",
                color_continuous_scale='Teal',
                labels=dict(x="Months After First Purchase", y="Cohort (First Purchase Month)", color="Retention Rate (%)")
            )
            fig_cohort.update_xaxes(side="top", dtick=1)
            fig_cohort.update_layout(height=600, margin=dict(t=50, l=0, r=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_cohort, use_container_width=True)
        else:
            st.info("Insufficient repeat purchase data to generate retention heatmap for this timeframe.")


elif page == "Product Quality":
    st.markdown("### Product Category Dissatisfaction")
    st.markdown("Identifying product categories with the highest concentration of negative reviews (1-2 stars) to pinpoint supplier or quality control issues.")
    
    review_data = load_category_reviews(start_date, end_date, states_str)
    
    if not review_data.empty:
        col_chart, col_table = st.columns([5, 5], gap="large")
        
        with col_chart:
            # Sort descending for the bar chart display
            chart_data = review_data.sort_values('negative_review_rate', ascending=True)
            fig_reviews = px.bar(
                chart_data, 
                x='negative_review_rate', 
                y='category', 
                orientation='h', 
                template="plotly_dark", 
                color='negative_review_rate',
                color_continuous_scale='Reds'
            )
            fig_reviews.update_xaxes(showgrid=False, visible=False)
            fig_reviews.update_yaxes(showgrid=False, title="")
            
            # Use customdata to pass the avg_review_score into the hover template
            fig_reviews.update_traces(
                texttemplate='%{x:.1f}%', 
                textposition='outside', 
                customdata=chart_data[['avg_review_score']],
                hovertemplate="<b>%{y}</b><br>Negative Rate: %{x:.1f}%<br>Avg Score: %{customdata[0]:.2f} ★<extra></extra>"
            )
            fig_reviews.update_layout(height=500, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", coloraxis_showscale=False)
            st.plotly_chart(fig_reviews, use_container_width=True)
            
        with col_table:
            fig_table = go.Figure(data=[go.Table(
                header=dict(values=['<b>Category</b>', '<b>Total Orders</b>', '<b>Avg Score</b>', '<b>Negative Rate</b>'], fill_color='#1e2130', align='left', font=dict(color='white', size=15), height=25),
                cells=dict(values=[review_data.category, review_data.total_orders, review_data.avg_review_score.apply(lambda x: f"{x:.2f} ★"), review_data.negative_review_rate.apply(lambda x: f"{x:.1f}%")], fill_color='#0e1117', align='left', font=dict(color='#e5e9f0', size=14), height=40))
            ])
            fig_table.update_layout(height=500, margin=dict(l=0, r=0, t=20, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_table, use_container_width=True)

            

           
