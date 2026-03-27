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
REFERENCE_ASSETS = {
    "日経225":  {"symbol": "^N225",  "currency": "JPY"},
    "S&P 500": {"symbol": "^GSPC",  "currency": "USD"},
    "USD/JPY": {"symbol": "JPY=X",  "currency": "JPY"},
    "Gold":    {"symbol": "GC=F",   "currency": "USD"},
}
PLOTLY_CONFIG = {
    "modeBarButtonsToAdd": ["drawline", "drawrect", "eraseshape"],
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


@st.cache_data(ttl=600)
def get_reference_data(symbol: str, period: str, interval: str = "1d"):
    return indicators.fetch_yahoo_ohlcv(symbol, period, interval)


# ─── セッション状態初期化 ───────────────────────────────────────────────────────
if "drawings" not in st.session_state:
    st.session_state.drawings = []  # [{"type": str, "params": dict, "color": str, "label": str}]


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

    st.subheader("参照アセット")
    ref_selected = []
    for name in REFERENCE_ASSETS:
        if st.checkbox(name, value=False, key=f"ref_{name}"):
            ref_selected.append(name)
    ref_period = st.selectbox(
        "期間", ["1mo", "3mo", "6mo", "1y"], index=2, key="ref_period",
    ) if ref_selected else "6mo"

    if st.button("データ更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("描画ツール")
    st.caption("ツールバーのペンでトレンドライン描画（一時的）")

    draw_type = st.selectbox(
        "描画タイプ",
        ["水平ライン", "トレンドライン", "並行チャネル", "ピッチフォーク"],
        key="draw_type",
    )
    draw_color = st.color_picker("線の色", value="#FF4B4B", key="draw_color")
    draw_label = st.text_input("ラベル (任意)", key="draw_label")

    if draw_type == "水平ライン":
        hl_price = st.number_input("価格", min_value=0.0, format="%.2f", key="draw_hl_price")
        if st.button("追加", key="draw_add"):
            st.session_state.drawings.append({
                "type": "hline", "color": draw_color, "label": draw_label,
                "params": {"price": hl_price},
            })
            st.rerun()

    elif draw_type == "トレンドライン":
        st.caption("開始点と終了点の日時・価格を入力")
        tl_start_date = st.date_input("開始日", key="draw_tl_sd")
        tl_start_time = st.time_input("開始時刻", key="draw_tl_st")
        tl_start_price = st.number_input("開始価格", min_value=0.0, format="%.2f", key="draw_tl_sp")
        tl_end_date = st.date_input("終了日", key="draw_tl_ed")
        tl_end_time = st.time_input("終了時刻", key="draw_tl_et")
        tl_end_price = st.number_input("終了価格", min_value=0.0, format="%.2f", key="draw_tl_ep")
        if st.button("追加", key="draw_add"):
            st.session_state.drawings.append({
                "type": "trendline", "color": draw_color, "label": draw_label,
                "params": {
                    "x0": datetime.datetime.combine(tl_start_date, tl_start_time).isoformat(),
                    "y0": tl_start_price,
                    "x1": datetime.datetime.combine(tl_end_date, tl_end_time).isoformat(),
                    "y1": tl_end_price,
                },
            })
            st.rerun()

    elif draw_type == "並行チャネル":
        ch_upper = st.number_input("上限価格", min_value=0.0, format="%.2f", key="draw_ch_upper")
        ch_lower = st.number_input("下限価格", min_value=0.0, format="%.2f", key="draw_ch_lower")
        if st.button("追加", key="draw_add"):
            st.session_state.drawings.append({
                "type": "channel", "color": draw_color, "label": draw_label,
                "params": {"upper": ch_upper, "lower": ch_lower},
            })
            st.rerun()

    elif draw_type == "ピッチフォーク":
        st.caption("ピボット(P)、翼A、翼Bの3点を入力")
        pf_p_date = st.date_input("P 日付", key="draw_pf_pd")
        pf_p_time = st.time_input("P 時刻", key="draw_pf_pt")
        pf_p_price = st.number_input("P 価格", min_value=0.0, format="%.2f", key="draw_pf_pp")
        pf_a_date = st.date_input("A 日付", key="draw_pf_ad")
        pf_a_time = st.time_input("A 時刻", key="draw_pf_at")
        pf_a_price = st.number_input("A 価格", min_value=0.0, format="%.2f", key="draw_pf_ap")
        pf_b_date = st.date_input("B 日付", key="draw_pf_bd")
        pf_b_time = st.time_input("B 時刻", key="draw_pf_bt")
        pf_b_price = st.number_input("B 価格", min_value=0.0, format="%.2f", key="draw_pf_bp")
        if st.button("追加", key="draw_add"):
            st.session_state.drawings.append({
                "type": "pitchfork", "color": draw_color, "label": draw_label,
                "params": {
                    "px": datetime.datetime.combine(pf_p_date, pf_p_time).isoformat(),
                    "py": pf_p_price,
                    "ax": datetime.datetime.combine(pf_a_date, pf_a_time).isoformat(),
                    "ay": pf_a_price,
                    "bx": datetime.datetime.combine(pf_b_date, pf_b_time).isoformat(),
                    "by": pf_b_price,
                },
            })
            st.rerun()

    # 登録済み描画の一覧と削除
    if st.session_state.drawings:
        st.markdown("**登録済み描画**")
        type_labels = {"hline": "水平線", "trendline": "トレンド", "channel": "チャネル", "pitchfork": "PF"}
        for i, d in enumerate(st.session_state.drawings):
            col_l, col_d = st.columns([4, 1])
            tl = type_labels.get(d["type"], d["type"])
            col_l.markdown(
                f"<span style='color:{d['color']}'>━</span> "
                f"**{tl}** {d['label'] or ''}",
                unsafe_allow_html=True,
            )
            if col_d.button("X", key=f"del_draw_{i}"):
                st.session_state.drawings.pop(i)
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

# ── ユーザー描画のレンダリング ────────────────────────────────────────────────────
for d in st.session_state.drawings:
    if d["type"] == "hline":
        fig.add_hline(
            y=d["params"]["price"],
            line_color=d["color"], line_width=1.5, line_dash="dot",
            annotation_text=d["label"] if d["label"] else None,
            annotation_position="top right",
        )
    elif d["type"] == "trendline":
        p = d["params"]
        fig.add_trace(
            go.Scatter(
                x=[datetime.datetime.fromisoformat(p["x0"]),
                   datetime.datetime.fromisoformat(p["x1"])],
                y=[p["y0"], p["y1"]],
                mode="lines",
                line=dict(color=d["color"], width=1.5),
                name=d["label"] or "トレンドライン",
                showlegend=False,
            ),
            row=1, col=1,
        )
    elif d["type"] == "channel":
        p = d["params"]
        fig.add_hrect(
            y0=p["lower"], y1=p["upper"],
            fillcolor=d["color"], opacity=0.08, line_width=0,
        )
        fig.add_hline(
            y=p["upper"], line_color=d["color"], line_width=1, line_dash="dash",
            annotation_text=(d["label"] + " 上限") if d["label"] else None,
            annotation_position="top right",
        )
        fig.add_hline(
            y=p["lower"], line_color=d["color"], line_width=1, line_dash="dash",
            annotation_text=(d["label"] + " 下限") if d["label"] else None,
            annotation_position="bottom right",
        )
    elif d["type"] == "pitchfork":
        p = d["params"]
        px_dt = datetime.datetime.fromisoformat(p["px"])
        ax_dt = datetime.datetime.fromisoformat(p["ax"])
        bx_dt = datetime.datetime.fromisoformat(p["bx"])
        py_, ay_, by_ = p["py"], p["ay"], p["by"]

        # 中点M = A,Bの中点
        mx_ts = ax_dt.timestamp() + (bx_dt.timestamp() - ax_dt.timestamp()) / 2
        mx_dt = datetime.datetime.fromtimestamp(mx_ts)
        my_ = (ay_ + by_) / 2

        # 中央線の傾きを使って延長（表示範囲の右端まで）
        dx_sec = mx_dt.timestamp() - px_dt.timestamp()
        dy = my_ - py_
        if dx_sec != 0:
            # 中央線をチャート右端まで延長
            last_ts = df.index[-1].timestamp()
            extend_sec = last_ts - px_dt.timestamp()
            slope = dy / dx_sec
            end_y_median = py_ + slope * extend_sec
            end_dt = datetime.datetime.fromtimestamp(last_ts)

            # 中央線: P → 延長点
            fig.add_trace(
                go.Scatter(
                    x=[px_dt, end_dt], y=[py_, end_y_median],
                    mode="lines", line=dict(color=d["color"], width=1.5),
                    name=d["label"] or "PF中央線", showlegend=False,
                ),
                row=1, col=1,
            )
            # 上プロング: Aを通り中央線に平行
            end_y_upper = ay_ + slope * (last_ts - ax_dt.timestamp())
            fig.add_trace(
                go.Scatter(
                    x=[ax_dt, end_dt], y=[ay_, end_y_upper],
                    mode="lines", line=dict(color=d["color"], width=1, dash="dash"),
                    name="PF上", showlegend=False,
                ),
                row=1, col=1,
            )
            # 下プロング: Bを通り中央線に平行
            end_y_lower = by_ + slope * (last_ts - bx_dt.timestamp())
            fig.add_trace(
                go.Scatter(
                    x=[bx_dt, end_dt], y=[by_, end_y_lower],
                    mode="lines", line=dict(color=d["color"], width=1, dash="dash"),
                    name="PF下", showlegend=False,
                ),
                row=1, col=1,
            )

st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
st.caption(f"データ最終時刻: {df.index[-1].strftime('%Y-%m-%d %H:%M UTC')}")


# ─── 参照アセットセクション ──────────────────────────────────────────────────────
if ref_selected:
    ref_tabs = st.tabs(ref_selected)
    for tab, name in zip(ref_tabs, ref_selected):
        with tab:
            asset_info = REFERENCE_ASSETS[name]
            try:
                df_ref = get_reference_data(asset_info["symbol"], ref_period)
            except Exception as e:
                st.warning(f"{name} のデータ取得に失敗しました: {e}")
                continue

            if df_ref.empty:
                st.warning(f"{name} のデータがありません（市場休場中の可能性）")
                continue

            # メトリクス
            ref_current = df_ref["close"].iloc[-1]
            ref_prev = df_ref["close"].iloc[-2] if len(df_ref) >= 2 else ref_current
            ref_change = (ref_current - ref_prev) / ref_prev * 100
            currency_sym = "\u00a5" if asset_info["currency"] == "JPY" else "$"

            rc1, rc2, rc3 = st.columns(3)
            rc1.metric(f"{name} 現在価格", f"{currency_sym}{ref_current:,.2f}")
            rc2.metric("前日比", f"{ref_change:+.2f}%")
            rc3.metric("データ最終", df_ref.index[-1].strftime("%Y-%m-%d"))

            # ローソク足 + 出来高チャート
            fig_ref = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.05, row_heights=[0.75, 0.25],
                subplot_titles=[name, "Volume"],
            )
            fig_ref.add_trace(
                go.Candlestick(
                    x=df_ref.index,
                    open=df_ref["open"], high=df_ref["high"],
                    low=df_ref["low"], close=df_ref["close"],
                    name=name,
                    increasing_line_color="#26a69a",
                    decreasing_line_color="#ef5350",
                ),
                row=1, col=1,
            )
            ref_vol_colors = [
                "#26a69a" if c >= o else "#ef5350"
                for o, c in zip(df_ref["open"], df_ref["close"])
            ]
            fig_ref.add_trace(
                go.Bar(x=df_ref.index, y=df_ref["volume"],
                       marker_color=ref_vol_colors,
                       name="Volume", showlegend=False),
                row=2, col=1,
            )
            fig_ref.update_layout(
                height=450,
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                hovermode="x unified",
                legend=dict(orientation="h", y=1.02, x=0),
                margin=dict(l=60, r=40, t=60, b=40),
            )
            fig_ref.update_xaxes(
                rangebreaks=[dict(bounds=["sat", "mon"])]
            )
            st.plotly_chart(fig_ref, use_container_width=True, config=PLOTLY_CONFIG)


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
