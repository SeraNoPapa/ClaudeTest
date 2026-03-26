"""
app.py - BTC/USDT テクニカル分析ダッシュボード
起動: streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import indicators

# ─── ページ設定 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BTC/USDT 分析",
    layout="wide",
    page_icon="₿",
)

COINS = [
    "BTC/USDT", "ETH/USDT", "XRP/USDT", "SOL/USDT",
    "BNB/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT",
]
PLOTLY_CONFIG = {
    "modeBarButtonsToAdd": ["drawline", "drawopenpath", "drawrect", "eraseshape"],
    "scrollZoom": True,
}
FIB_COLORS = {
    "0.0%":   "#888888",
    "23.6%":  "#FFA500",
    "38.2%":  "#4444FF",
    "50.0%":  "#00AA00",
    "61.8%":  "#4444FF",
    "100.0%": "#888888",
}

# ─── キャッシュ付きデータ取得 ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def get_data(symbol: str, timeframe: str, limit: int):
    return indicators.fetch_ohlcv_df(symbol, timeframe, limit=limit)


@st.cache_data(ttl=3600)
def get_mayer_data(symbol: str):
    df = indicators.fetch_ohlcv_since_year(symbol, "1d", 2018)
    return indicators.calc_mayer_multiple(df)


@st.cache_data(ttl=60)
def get_usdjpy():
    return indicators.get_usdjpy_rate()


# ─── セッション状態初期化 ───────────────────────────────────────────────────────
if "hlines" not in st.session_state:
    st.session_state.hlines = []    # [{"price": float, "color": str, "label": str}]
if "channels" not in st.session_state:
    st.session_state.channels = []  # [{"upper": float, "lower": float, "color": str, "label": str}]


# ─── サイドバー ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 設定")
    symbol = st.selectbox("銘柄", COINS, index=0)
    st.divider()

    st.subheader("データ設定")
    timeframe = st.selectbox(
        "時間足",
        ["15m", "1h", "2h", "4h", "1d", "1w", "1M"],
        index=3,
    )
    limit = st.slider("表示本数", min_value=100, max_value=1000, value=300, step=50)

    st.subheader("オーバーレイ（メインチャート）")
    show_ma = st.checkbox("移動平均線", value=True)
    if show_ma:
        ma_pair_label = st.selectbox(
            "MAペア",
            ["5 / 25", "12 / 60", "25 / 75", "50 / 200"],
            index=0,
        )
        ma_short, ma_long = [int(x.strip()) for x in ma_pair_label.split("/")]

    show_bb = st.checkbox("ボリンジャーバンド (20, 2)", value=True)
    show_sar = st.checkbox("パラボリック SAR", value=False)

    show_fib = st.checkbox("フィボナッチ", value=False)
    if show_fib:
        fib_trend = st.radio("トレンド", ["上昇", "下降"], horizontal=True)
        fib_trend_key = "up" if fib_trend == "上昇" else "down"

    st.subheader("サブプロット")
    show_macd  = st.checkbox("MACD",           value=True)
    show_rsi   = st.checkbox("RSI",            value=True)
    show_stoch = st.checkbox("ストキャスティクス", value=False)
    show_atr   = st.checkbox("ATR",            value=False)
    show_obv   = st.checkbox("OBV",            value=False)
    show_adx   = st.checkbox("ADX / DMI",      value=False)

    st.subheader("その他")
    if symbol == "BTC/USDT":
        show_mayer = st.checkbox("メイヤーマルチプル（2018年〜）", value=False)
    else:
        show_mayer = False
    show_jpy   = st.checkbox("JPY表示", value=False)

    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("✏️ ライン管理")

    with st.expander("水平線を追加"):
        hl_price = st.number_input("価格", min_value=0.0, format="%.4f", key="hl_price_input")
        hl_color = st.color_picker("色", value="#FF4B4B", key="hl_color_input")
        hl_label = st.text_input("ラベル (任意)", key="hl_label_input")
        if st.button("追加", key="hl_add"):
            st.session_state.hlines.append({"price": hl_price, "color": hl_color, "label": hl_label})

    with st.expander("チャンネルを追加"):
        ch_upper = st.number_input("上限価格", min_value=0.0, format="%.4f", key="ch_upper_input")
        ch_lower = st.number_input("下限価格", min_value=0.0, format="%.4f", key="ch_lower_input")
        ch_color = st.color_picker("色", value="#4B9FFF", key="ch_color_input")
        ch_label = st.text_input("ラベル (任意)", key="ch_label_input")
        if st.button("追加", key="ch_add"):
            st.session_state.channels.append({"upper": ch_upper, "lower": ch_lower, "color": ch_color, "label": ch_label})

    if st.session_state.hlines or st.session_state.channels:
        st.markdown("**登録済みライン**")
        for i, hl in enumerate(st.session_state.hlines):
            col_l, col_d = st.columns([4, 1])
            col_l.markdown(
                f"<span style='color:{hl['color']}'>━</span> "
                f"{hl['label'] or '水平線'} @ {hl['price']:.4f}",
                unsafe_allow_html=True,
            )
            if col_d.button("✕", key=f"del_hl_{i}"):
                st.session_state.hlines.pop(i)
                st.rerun()
        for i, ch in enumerate(st.session_state.channels):
            col_l, col_d = st.columns([4, 1])
            col_l.markdown(
                f"<span style='color:{ch['color']}'>▬</span> "
                f"{ch['label'] or 'チャンネル'} "
                f"{ch['lower']:.4f} – {ch['upper']:.4f}",
                unsafe_allow_html=True,
            )
            if col_d.button("✕", key=f"del_ch_{i}"):
                st.session_state.channels.pop(i)
                st.rerun()


# ─── データ取得・インジケーター計算 ────────────────────────────────────────────
try:
    df_raw = get_data(symbol, timeframe, limit)
except Exception as e:
    st.error(f"データ取得エラー: {e}")
    st.stop()

df = df_raw.copy()

if show_ma:
    df = indicators.calc_ma(df, ma_short, ma_long)
if show_bb:
    df = indicators.calc_bb(df)
if show_sar:
    df = indicators.calc_sar(df)
if show_fib:
    fib_levels = indicators.calc_fibonacci(df, fib_trend_key)
if show_macd:
    df = indicators.calc_macd(df)
if show_rsi:
    df = indicators.calc_rsi(df)
if show_stoch:
    df = indicators.calc_stochastic(df)
if show_atr:
    df = indicators.calc_atr(df)
if show_obv:
    df = indicators.calc_obv(df)
if show_adx:
    df = indicators.calc_adx(df)

usdjpy = get_usdjpy() if show_jpy else None

# ─── メトリクス行 ──────────────────────────────────────────────────────────────
current_price = df["close"].iloc[-1]
prev_price    = df["close"].iloc[-2]
price_change  = (current_price - prev_price) / prev_price * 100

price_label = f"${current_price:,.2f}"
if show_jpy and usdjpy:
    price_label += f"  /  ¥{current_price * usdjpy:,.0f}"

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"現在価格 ({symbol})", price_label)
col2.metric("前足比", f"{price_change:+.2f}%")
col3.metric("USD/JPY", f"¥{usdjpy}" if usdjpy else "取得失敗")
col4.metric("直近高値", f"${df['high'].max():,.2f}")


# ─── Plotlyチャート構築 ────────────────────────────────────────────────────────
subplot_list = []
if show_macd:  subplot_list.append("MACD")
if show_rsi:   subplot_list.append("RSI")
if show_stoch: subplot_list.append("Stochastic")
if show_atr:   subplot_list.append("ATR")
if show_obv:   subplot_list.append("OBV")
if show_adx:   subplot_list.append("ADX/DMI")

n_sub  = len(subplot_list)
n_rows = 2 + n_sub  # row1=ローソク, row2=出来高, row3+= サブプロット

# 高さの比率
if n_sub > 0:
    sub_height = 0.4 / n_sub
    row_heights = [0.5, 0.1] + [sub_height] * n_sub
else:
    row_heights = [0.85, 0.15]

subplot_titles = ["", "Volume"] + subplot_list

fig = make_subplots(
    rows=n_rows,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.03,
    row_heights=row_heights,
    subplot_titles=subplot_titles,
)

# ── Row 1: ローソク足 ──────────────────────────────────────────────────────────
fig.add_trace(
    go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name=symbol,
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ),
    row=1, col=1,
)

# 移動平均線
if show_ma:
    fig.add_trace(
        go.Scatter(x=df.index, y=df[f"MA{ma_short}"],
                   line=dict(color="#FF9800", width=1),
                   name=f"MA{ma_short}"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df[f"MA{ma_long}"],
                   line=dict(color="#2196F3", width=1.5),
                   name=f"MA{ma_long}"),
        row=1, col=1,
    )

# ボリンジャーバンド
if show_bb:
    fig.add_trace(
        go.Scatter(x=df.index, y=df["BB_UPPER"],
                   line=dict(color="rgba(0,150,200,0.4)", width=1),
                   name="BB Upper", showlegend=False),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["BB_LOWER"],
                   fill="tonexty",
                   fillcolor="rgba(0,150,200,0.07)",
                   line=dict(color="rgba(0,150,200,0.4)", width=1),
                   name="Bollinger Bands"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["BB_MIDDLE"],
                   line=dict(color="rgba(150,150,150,0.7)", width=1, dash="dash"),
                   name="BB Mid", showlegend=False),
        row=1, col=1,
    )

# パラボリック SAR
if show_sar:
    fig.add_trace(
        go.Scatter(x=df.index, y=df["PSAR"],
                   mode="markers",
                   marker=dict(size=3, color="#9C27B0", symbol="circle"),
                   name="SAR"),
        row=1, col=1,
    )

# フィボナッチ水平線
if show_fib:
    for label, price in fib_levels.items():
        fig.add_hline(
            y=price,
            line_dash="dot",
            line_color=FIB_COLORS.get(label, "#888888"),
            line_width=1,
            annotation_text=f"Fib {label} ${price:,.0f}",
            annotation_position="left",
            row=1, col=1,
        )

# ── Row 2: 出来高 ──────────────────────────────────────────────────────────────
vol_colors = [
    "#26a69a" if c >= o else "#ef5350"
    for o, c in zip(df["open"], df["close"])
]
fig.add_trace(
    go.Bar(x=df.index, y=df["volume"],
           marker_color=vol_colors,
           name="Volume", showlegend=False),
    row=2, col=1,
)

# ── Row 3+: サブプロット ────────────────────────────────────────────────────────
for idx, name in enumerate(subplot_list, start=3):
    if name == "MACD":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["MACD"],
                       line=dict(color="#2196F3", width=1.2),
                       name="MACD"),
            row=idx, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["SIGNAL"],
                       line=dict(color="#FF9800", width=1.2),
                       name="Signal"),
            row=idx, col=1,
        )
        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["HISTOGRAM"]]
        fig.add_trace(
            go.Bar(x=df.index, y=df["HISTOGRAM"],
                   marker_color=hist_colors,
                   name="Histogram", showlegend=False),
            row=idx, col=1,
        )

    elif name == "RSI":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["RSI"],
                       line=dict(color="#9C27B0", width=1.2),
                       name="RSI (14)"),
            row=idx, col=1,
        )
        for level, color in [(70, "red"), (50, "gray"), (30, "green")]:
            fig.add_hline(y=level, line_dash="dot",
                          line_color=color, line_width=0.8,
                          row=idx, col=1)

    elif name == "Stochastic":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["slow_k"],
                       line=dict(color="#2196F3", width=1.2),
                       name="Slow %K"),
            row=idx, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["slow_d"],
                       line=dict(color="#FF9800", width=1.2, dash="dash"),
                       name="Slow %D"),
            row=idx, col=1,
        )
        for level, color in [(80, "red"), (20, "green")]:
            fig.add_hline(y=level, line_dash="dot",
                          line_color=color, line_width=0.8,
                          row=idx, col=1)

    elif name == "ATR":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["ATR"],
                       line=dict(color="#00BCD4", width=1.2),
                       name="ATR (14)"),
            row=idx, col=1,
        )

    elif name == "OBV":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["OBV"],
                       line=dict(color="#4CAF50", width=1.2),
                       name="OBV"),
            row=idx, col=1,
        )

    elif name == "ADX/DMI":
        fig.add_trace(
            go.Scatter(x=df.index, y=df["ADX"],
                       line=dict(color="#E91E63", width=1.5),
                       name="ADX"),
            row=idx, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["PDI"],
                       line=dict(color="#2196F3", width=1),
                       name="+DI"),
            row=idx, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["MDI"],
                       line=dict(color="#ef5350", width=1),
                       name="-DI"),
            row=idx, col=1,
        )
        fig.add_hline(y=25, line_dash="dot",
                      line_color="gray", line_width=0.8,
                      row=idx, col=1)

# ── レイアウト設定 ──────────────────────────────────────────────────────────────
chart_height = 300 + 400 + 150 * n_sub

fig.update_layout(
    height=chart_height,
    template="plotly_dark",
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
    legend=dict(orientation="h", y=1.02, x=0),
    margin=dict(l=60, r=40, t=60, b=40),
    title=dict(
        text=f"{symbol}  {timeframe}  ({limit}本)",
        font=dict(size=16),
    ),
)

# 週末ギャップ除去（日足以上のみ）
if timeframe in ("1d", "1w", "1M"):
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])]
    )

# ── ユーザー定義ライン ──────────────────────────────────────────────────────────
for hl in st.session_state.hlines:
    fig.add_hline(
        y=hl["price"],
        line_color=hl["color"],
        line_width=1.5,
        line_dash="dot",
        annotation_text=hl["label"] if hl["label"] else None,
        annotation_position="top right",
    )

for ch in st.session_state.channels:
    fig.add_hrect(
        y0=ch["lower"], y1=ch["upper"],
        fillcolor=ch["color"], opacity=0.08, line_width=0,
    )
    fig.add_hline(
        y=ch["upper"], line_color=ch["color"], line_width=1, line_dash="dash",
        annotation_text=(ch["label"] + " 上限") if ch["label"] else None,
        annotation_position="top right",
    )
    fig.add_hline(
        y=ch["lower"], line_color=ch["color"], line_width=1, line_dash="dash",
        annotation_text=(ch["label"] + " 下限") if ch["label"] else None,
        annotation_position="bottom right",
    )

st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
st.caption(f"データ最終時刻: {df.index[-1].strftime('%Y-%m-%d %H:%M UTC')}")


# ─── メイヤーマルチプルセクション ────────────────────────────────────────────────
if show_mayer:
    with st.expander("メイヤーマルチプル（2018年〜）", expanded=True):
        with st.spinner("2018年〜のデータを取得中..."):
            try:
                df_m = get_mayer_data(symbol)
            except Exception as e:
                st.error(f"データ取得エラー: {e}")
                st.stop()

        latest_mm = df_m["Mayer_Multiple"].iloc[-1]
        latest_price = df_m["close"].iloc[-1]
        col1, col2 = st.columns(2)
        col1.metric("メイヤーマルチプル（最新）", f"{latest_mm:.4f}")
        col2.metric("BTC価格（最新）", f"${latest_price:,.2f}")

        fig_m = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.6, 0.4],
            subplot_titles=["BTC Price & SMA200", "Mayer Multiple"],
        )

        # 価格ライン
        fig_m.add_trace(
            go.Scatter(x=df_m.index, y=df_m["close"],
                       line=dict(color="#FF9800", width=1),
                       name="BTC Price"),
            row=1, col=1,
        )
        fig_m.add_trace(
            go.Scatter(x=df_m.index, y=df_m["SMA200"],
                       line=dict(color="#2196F3", width=1.5),
                       name="SMA 200"),
            row=1, col=1,
        )

        # メイヤーマルチプル
        fig_m.add_trace(
            go.Scatter(x=df_m.index, y=df_m["Mayer_Multiple"],
                       line=dict(color="#9C27B0", width=1.2),
                       name="Mayer Multiple"),
            row=2, col=1,
        )

        # 基準線
        ref_lines = [(1.5, "red"), (1.0, "gray"), (0.9, "green"), (0.7, "blue"), (0.5, "yellow")]
        for level, color in ref_lines:
            fig_m.add_hline(y=level, line_dash="dot",
                            line_color=color, line_width=0.8,
                            annotation_text=str(level),
                            annotation_position="right",
                            row=2, col=1)

        fig_m.update_layout(
            height=600,
            template="plotly_dark",
            hovermode="x unified",
            margin=dict(l=60, r=60, t=60, b=40),
            legend=dict(orientation="h", y=1.02),
        )
        if timeframe in ("1d", "1w", "1M"):
            fig_m.update_xaxes(
                rangebreaks=[dict(bounds=["sat", "mon"])]
            )

        st.plotly_chart(fig_m, use_container_width=True)
        st.caption("参考: MM 1.5↑=過熱, 1.0=公正価値, 0.9↓=割安, 0.7↓=強い割安, 0.5↓=極値")
