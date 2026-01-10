#!/usr/bin/env python3
"""
Streamlit Dashboard - Real-time Clickstream Analytics
"""

import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yaml

# Try to import deltalake for reading Delta tables
try:
    from deltalake import DeltaTable
    DELTA_AVAILABLE = True
except ImportError:
    DELTA_AVAILABLE = False
    st.warning("deltalake package not available, using fallback")

# Page configuration
st.set_page_config(
    page_title="Clickstream Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .big-number {
        font-size: 48px;
        font-weight: bold;
        color: #1f77b4;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

def load_config():
    """Load configuration from YAML file."""
    config_path = os.environ.get('CONFIG_PATH', '/app/config/config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {
            'delta': {
                'base_path': '/app/delta',
                'tables': {
                    'events_1min': '/app/delta/aggregations/events_1min',
                    'events_5min': '/app/delta/aggregations/events_5min',
                    'products': '/app/delta/aggregations/products',
                    'funnel': '/app/delta/aggregations/funnel'
                }
            },
            'dashboard': {
                'refresh_interval': 5
            }
        }

def read_delta_table(path):
    """Read Delta table into pandas DataFrame."""
    try:
        if DELTA_AVAILABLE and os.path.exists(path):
            dt = DeltaTable(path)
            return dt.to_pandas()
    except Exception as e:
        pass
    return pd.DataFrame()

def format_number(num):
    """Format large numbers for display."""
    if num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    return str(int(num))

def main():
    config = load_config()
    delta_config = config['delta']

    # Header
    st.title("📊 Real-time Clickstream Analytics")
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        refresh_rate = st.slider(
            "Refresh interval (seconds)",
            min_value=1,
            max_value=30,
            value=config['dashboard']['refresh_interval']
        )
        st.markdown("---")
        st.markdown(f"**Last updated:** {datetime.now().strftime('%H:%M:%S')}")

        # Auto-refresh
        if st.checkbox("Auto-refresh", value=True):
            time.sleep(refresh_rate)
            st.rerun()

    # Load data
    df_1min = read_delta_table(delta_config['tables']['events_1min'])
    df_5min = read_delta_table(delta_config['tables']['events_5min'])
    df_products = read_delta_table(delta_config['tables']['products'])
    df_funnel = read_delta_table(delta_config['tables']['funnel'])

    # Check if data is available
    has_data = not df_1min.empty or not df_5min.empty

    if not has_data:
        st.warning("⏳ Waiting for data... Make sure the producer and streaming jobs are running.")
        st.info("""
        **To start the pipeline:**
        ```bash
        make start          # Start infrastructure
        make streaming      # Start Spark Streaming
        make producer       # Start Kafka Producer
        ```
        """)

        # Show placeholder metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Active Sessions", "—")
        with col2:
            st.metric("Events/min", "—")
        with col3:
            st.metric("Conversion Rate", "—")
        with col4:
            st.metric("Revenue", "—")

        return

    # ==========================================
    # KEY METRICS
    # ==========================================
    st.header("📈 Key Metrics")

    # Get latest metrics
    if not df_1min.empty:
        latest_window = df_1min['window_end'].max()
        latest_data = df_1min[df_1min['window_end'] == latest_window]

        total_events = latest_data['event_count'].sum()
        unique_sessions = latest_data['unique_sessions'].sum()
        views = latest_data[latest_data['event_type'] == 'view']['event_count'].sum()
        purchases = latest_data[latest_data['event_type'] == 'purchase']['event_count'].sum()
        revenue = latest_data[latest_data['event_type'] == 'purchase']['total_revenue'].sum()

        conversion_rate = (purchases / views * 100) if views > 0 else 0
    else:
        total_events = unique_sessions = views = purchases = revenue = conversion_rate = 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Active Sessions",
            format_number(unique_sessions),
            delta=None
        )

    with col2:
        st.metric(
            "Events/min",
            format_number(total_events),
            delta=None
        )

    with col3:
        st.metric(
            "Conversion Rate",
            f"{conversion_rate:.2f}%",
            delta=None
        )

    with col4:
        st.metric(
            "Revenue",
            f"${revenue:,.2f}" if revenue else "$0",
            delta=None
        )

    st.markdown("---")

    # ==========================================
    # CHARTS ROW 1
    # ==========================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Events Over Time")

        if not df_1min.empty:
            # Prepare data for line chart
            chart_data = df_1min.groupby(['window_start', 'event_type'])['event_count'].sum().reset_index()

            if not chart_data.empty:
                fig = px.line(
                    chart_data,
                    x='window_start',
                    y='event_count',
                    color='event_type',
                    title='Events by Type (1-min windows)',
                    labels={'window_start': 'Time', 'event_count': 'Count', 'event_type': 'Event Type'}
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Waiting for aggregated data...")
        else:
            st.info("Waiting for data...")

    with col2:
        st.subheader("🎯 Conversion Funnel")

        if not df_funnel.empty:
            # Get latest funnel data
            latest_funnel = df_funnel[df_funnel['window_end'] == df_funnel['window_end'].max()].iloc[0] if not df_funnel.empty else None

            if latest_funnel is not None:
                funnel_data = pd.DataFrame({
                    'Stage': ['Views', 'Add to Cart', 'Purchases'],
                    'Count': [
                        latest_funnel['views'],
                        latest_funnel['add_to_cart'],
                        latest_funnel['purchases']
                    ]
                })

                fig = go.Figure(go.Funnel(
                    y=funnel_data['Stage'],
                    x=funnel_data['Count'],
                    textinfo="value+percent initial",
                    marker=dict(color=['#636EFA', '#EF553B', '#00CC96'])
                ))
                fig.update_layout(height=400, title='Conversion Funnel (5-min window)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Waiting for funnel data...")
        else:
            st.info("Waiting for funnel data...")

    st.markdown("---")

    # ==========================================
    # CHARTS ROW 2
    # ==========================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🛒 Event Distribution")

        if not df_1min.empty:
            # Pie chart of event types
            latest_window = df_1min['window_end'].max()
            event_dist = df_1min[df_1min['window_end'] == latest_window].groupby('event_type')['event_count'].sum()

            if not event_dist.empty:
                fig = px.pie(
                    values=event_dist.values,
                    names=event_dist.index,
                    title='Event Type Distribution',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Waiting for data...")
        else:
            st.info("Waiting for data...")

    with col2:
        st.subheader("🏆 Top Products")

        if not df_products.empty:
            # Get top 10 products by views
            latest_window = df_products['window_end'].max()
            top_products = df_products[df_products['window_end'] == latest_window] \
                .nlargest(10, 'views')[['product_id', 'brand', 'views', 'purchases', 'revenue']]

            if not top_products.empty:
                st.dataframe(
                    top_products.style.format({
                        'views': '{:,.0f}',
                        'purchases': '{:,.0f}',
                        'revenue': '${:,.2f}'
                    }),
                    use_container_width=True,
                    height=400
                )
            else:
                st.info("Waiting for product data...")
        else:
            st.info("Waiting for product data...")

    st.markdown("---")

    # ==========================================
    # DETAILED METRICS TABLE
    # ==========================================
    st.subheader("📋 Detailed Metrics (5-minute windows)")

    if not df_5min.empty:
        # Show aggregated table
        display_df = df_5min.sort_values('window_end', ascending=False).head(50)
        st.dataframe(
            display_df.style.format({
                'event_count': '{:,.0f}',
                'unique_sessions': '{:,.0f}',
                'unique_users': '{:,.0f}',
                'total_revenue': '${:,.2f}',
                'avg_price': '${:,.2f}'
            }),
            use_container_width=True
        )
    else:
        st.info("Waiting for aggregated data...")

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Real-time Clickstream Analytics Dashboard | Powered by Kafka, Spark & Delta Lake"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
