"""
Streamlit dashboard for the Fintech Market Data Pipeline.

Run with:
    streamlit run src/dashboard/app.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import text

from src.db.engine import engine

st.set_page_config(
    page_title="Fintech Market Data Pipeline",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Fintech Market Data Pipeline")
st.caption("End-of-day analytics powered by yfinance → PostgreSQL")


# ─── Data loaders ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_symbols() -> list[str]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol FROM symbols ORDER BY symbol")).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=60)
def load_data_range() -> tuple[pd.Timestamp, pd.Timestamp]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MIN(trade_date), MAX(trade_date) FROM stg_market_prices")
        ).fetchone()
    if row and row[0]:
        return pd.Timestamp(row[0]), pd.Timestamp(row[1])
    today = pd.Timestamp.today().normalize()
    return today - pd.DateOffset(months=6), today


@st.cache_data(ttl=60)
def load_staging(symbol: str, start: str, end: str) -> pd.DataFrame:
    sql = text("""
        SELECT s.symbol, p.trade_date,
               p.open_price, p.high_price, p.low_price, p.close_price, p.volume
        FROM stg_market_prices p
        JOIN symbols s ON s.id = p.symbol_id
        WHERE s.symbol = :symbol
          AND p.trade_date BETWEEN :start AND :end
        ORDER BY p.trade_date
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn,
                           params={"symbol": symbol, "start": start, "end": end},
                           parse_dates=["trade_date"])


@st.cache_data(ttl=60)
def load_mart(symbol: str, start: str, end: str) -> pd.DataFrame:
    sql = text("""
        SELECT s.symbol, m.trade_date,
               m.close_price, m.daily_return, m.ma_7, m.ma_30,
               m.rolling_volatility_30, m.volume, m.volume_change
        FROM mart_daily_symbol_metrics m
        JOIN symbols s ON s.id = m.symbol_id
        WHERE s.symbol = :symbol
          AND m.trade_date BETWEEN :start AND :end
        ORDER BY m.trade_date
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn,
                           params={"symbol": symbol, "start": start, "end": end},
                           parse_dates=["trade_date"])


@st.cache_data(ttl=30)
def load_quality_results() -> pd.DataFrame:
    sql = text("""
        SELECT r.check_name, r.table_name, r.status, r.failed_count, r.checked_at,
               p.pipeline_name, p.started_at
        FROM data_quality_results r
        JOIN pipeline_runs p ON p.id = r.pipeline_run_id
        ORDER BY r.checked_at DESC
        LIMIT 50
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, parse_dates=["checked_at", "started_at"])


@st.cache_data(ttl=30)
def load_pipeline_runs() -> pd.DataFrame:
    sql = text("""
        SELECT id::text, pipeline_name, status, started_at, finished_at,
               EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duration_sec,
               error_message
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 20
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, parse_dates=["started_at", "finished_at"])


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    try:
        symbols = load_symbols()
    except Exception:
        symbols = []

    if not symbols:
        st.warning(
            "No data found. Run the pipeline first:\n\n"
            "`python -m src.pipeline --symbols AAPL MSFT TSLA`\n"
            "`--start 2024-01-01 --end 2024-12-31`"
        )
        st.stop()

    selected_symbol = st.selectbox("Symbol", symbols)
    db_start, db_end = load_data_range()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=db_start, min_value=db_start, max_value=db_end)
    with col2:
        end_date = st.date_input("To", value=db_end, min_value=db_start, max_value=db_end)

    st.divider()
    st.markdown("**Source:** yfinance")
    st.markdown("**DB:** PostgreSQL 16")

start_str = str(start_date)
end_str = str(end_date)

# ─── Tabs ────────────────────────────────────────────────────────────────────
tab_price, tab_analytics, tab_quality, tab_runs = st.tabs(
    ["📊 Price Chart", "📉 Analytics", "✅ Data Quality", "🔁 Pipeline Runs"]
)

# ── Tab 1: Price Chart ───────────────────────────────────────────────────────
with tab_price:
    st.subheader(f"{selected_symbol} — OHLCV Candlestick + Moving Averages")
    df_stg = load_staging(selected_symbol, start_str, end_str)
    df_mart = load_mart(selected_symbol, start_str, end_str)

    if df_stg.empty:
        st.info("No price data for the selected range.")
    else:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.75, 0.25],
            vertical_spacing=0.05,
        )
        fig.add_trace(
            go.Candlestick(
                x=df_stg["trade_date"],
                open=df_stg["open_price"],
                high=df_stg["high_price"],
                low=df_stg["low_price"],
                close=df_stg["close_price"],
                name="OHLC",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ),
            row=1, col=1,
        )
        if not df_mart.empty:
            fig.add_trace(
                go.Scatter(x=df_mart["trade_date"], y=df_mart["ma_7"],
                           name="MA 7", line=dict(color="#ffa726", width=1.5)),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=df_mart["trade_date"], y=df_mart["ma_30"],
                           name="MA 30", line=dict(color="#ab47bc", width=1.5)),
                row=1, col=1,
            )
        colors = [
            "#26a69a" if c >= o else "#ef5350"
            for c, o in zip(df_stg["close_price"], df_stg["open_price"])
        ]
        fig.add_trace(
            go.Bar(x=df_stg["trade_date"], y=df_stg["volume"],
                   name="Volume", marker_color=colors, opacity=0.7),
            row=2, col=1,
        )
        fig.update_layout(
            height=600,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02),
            margin=dict(l=0, r=0, t=30, b=0),
            template="plotly_dark",
        )
        fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)

        latest = df_stg.iloc[-1]
        first = df_stg.iloc[0]
        pct = (latest["close_price"] - first["close_price"]) / first["close_price"] * 100
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Last Close", f"${latest['close_price']:.2f}")
        m2.metric("Period Return", f"{pct:+.2f}%")
        m3.metric("Period High", f"${df_stg['high_price'].max():.2f}")
        m4.metric("Period Low", f"${df_stg['low_price'].min():.2f}")

# ── Tab 2: Analytics ─────────────────────────────────────────────────────────
with tab_analytics:
    st.subheader(f"{selected_symbol} — Analytics")
    df_mart = load_mart(selected_symbol, start_str, end_str)

    if df_mart.empty:
        st.info("No analytics data. Run the pipeline to build the mart.")
    else:
        colors_ret = [
            "#26a69a" if v >= 0 else "#ef5350"
            for v in df_mart["daily_return"].fillna(0)
        ]
        fig_ret = go.Figure(go.Bar(
            x=df_mart["trade_date"],
            y=(df_mart["daily_return"] * 100).round(4),
            marker_color=colors_ret,
            name="Daily Return %",
        ))
        fig_ret.update_layout(title="Daily Return (%)", template="plotly_dark",
                              height=300, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_ret, use_container_width=True)

        col_vol, col_vc = st.columns(2)
        with col_vol:
            fig_vol = go.Figure(go.Scatter(
                x=df_mart["trade_date"],
                y=df_mart["rolling_volatility_30"],
                fill="tozeroy",
                line=dict(color="#ab47bc", width=2),
                name="30d Volatility",
            ))
            fig_vol.update_layout(title="30-Day Rolling Volatility", template="plotly_dark",
                                  height=280, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_vol, use_container_width=True)

        with col_vc:
            colors_vc = [
                "#26a69a" if v >= 0 else "#ef5350"
                for v in df_mart["volume_change"].fillna(0)
            ]
            fig_vc = go.Figure(go.Bar(
                x=df_mart["trade_date"],
                y=(df_mart["volume_change"] * 100).round(2),
                marker_color=colors_vc,
                name="Volume Change %",
            ))
            fig_vc.update_layout(title="Volume Change (%)", template="plotly_dark",
                                 height=280, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_vc, use_container_width=True)

        st.subheader("Summary Statistics")
        stats = df_mart[["daily_return", "rolling_volatility_30", "volume"]].describe().T
        stats.index = ["Daily Return", "30d Volatility", "Volume"]
        st.dataframe(stats.style.format("{:.6f}"), use_container_width=True)

# ── Tab 3: Data Quality ───────────────────────────────────────────────────────
with tab_quality:
    st.subheader("Data Quality Results")
    df_q = load_quality_results()

    if df_q.empty:
        st.info("No quality results yet.")
    else:
        latest_time = df_q["checked_at"].max()
        latest = df_q[df_q["checked_at"] == latest_time].copy()
        st.markdown(f"**Latest check:** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Checks Run", len(latest))
        c2.metric("✅ Passed", (latest["status"] == "pass").sum())
        c3.metric("❌ Failed", (latest["status"] == "fail").sum())
        st.divider()

        def _style_status(val: str) -> str:
            if val == "pass":
                return "background-color:#1b5e20;color:#a5d6a7;font-weight:bold"
            return "background-color:#b71c1c;color:#ef9a9a;font-weight:bold"

        display = latest[["check_name", "table_name", "status", "failed_count"]].copy()
        display.columns = ["Check", "Table", "Status", "Failed Rows"]
        st.dataframe(
            display.style.map(_style_status, subset=["Status"]),
            use_container_width=True, hide_index=True,
        )
        with st.expander("Full history (last 50)"):
            st.dataframe(df_q, use_container_width=True, hide_index=True)

# ── Tab 4: Pipeline Runs ─────────────────────────────────────────────────────
with tab_runs:
    st.subheader("Pipeline Run History")
    df_runs = load_pipeline_runs()

    if df_runs.empty:
        st.info("No pipeline runs recorded.")
    else:
        avg_dur = df_runs["duration_sec"].mean()
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Total Runs", len(df_runs))
        r2.metric("✅ Successful", (df_runs["status"] == "success").sum())
        r3.metric("❌ Failed", (df_runs["status"] == "failed").sum())
        r4.metric("Avg Duration", f"{avg_dur:.0f}s" if pd.notna(avg_dur) else "—")
        st.divider()

        def _style_run(val: str) -> str:
            if val == "success":
                return "background-color:#1b5e20;color:#a5d6a7;font-weight:bold"
            if val == "failed":
                return "background-color:#b71c1c;color:#ef9a9a;font-weight:bold"
            return "background-color:#e65100;color:#ffcc80;font-weight:bold"

        display = df_runs[["id", "pipeline_name", "status", "started_at",
                            "duration_sec", "error_message"]].copy()
        display.columns = ["Run ID", "Pipeline", "Status", "Started At", "Duration (s)", "Error"]
        st.dataframe(
            display.style.map(_style_run, subset=["Status"]),
            use_container_width=True, hide_index=True,
        )
