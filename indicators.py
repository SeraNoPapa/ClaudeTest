"""
indicators.py - データ取得とテクニカルインジケーター計算モジュール
UIやPlotlyへの依存なし。全関数はDataFrameを受け取りDataFrameを返す。
"""

import ccxt
import datetime
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from dateutil.relativedelta import relativedelta
from finta import TA


# ─── データ取得 ─────────────────────────────────────────────────────────────

def fetch_ohlcv_df(symbol: str, timeframe: str, since=None, limit: int = 500) -> pd.DataFrame:
    """BinanceからOHLCVデータを取得し、小文字カラム名のDataFrameで返す"""
    exchange = ccxt.binance()
    if since is not None:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
    else:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df


def fetch_ohlcv_since_year(symbol: str, timeframe: str, start_year: int) -> pd.DataFrame:
    """指定年からの全データをページングで取得する（メイヤーマルチプル用）"""
    exchange = ccxt.binance()
    since = exchange.parse8601(f"{start_year}-01-01T00:00:00Z")
    all_ohlcv = []

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            since = ohlcv[-1][0] + 1
            all_ohlcv += ohlcv
            if ohlcv[-1][0] > exchange.milliseconds() - 86400000:
                break
        except Exception as e:
            print(f"Error: {e}")
            break

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="first")]
    return df


def fetch_yahoo_ohlcv(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Yahoo FinanceからOHLCVデータを取得し、小文字カラム名のDataFrameで返す"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        df = df.rename(columns=str.lower)
        # yfinanceが返す余分な列(dividends, stock splits)を削除
        keep_cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in keep_cols if c in df.columns]]
        df.index.name = "timestamp"
        return df
    except Exception:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def get_usdjpy_rate() -> float:
    """yfinanceからUSD/JPYの最新レートを取得する"""
    try:
        ticker = yf.Ticker("JPY=X")
        data = ticker.history(period="1d", interval="1m")
        if data.empty:
            return None
        price = data["Close"].dropna().iloc[-1]
        return round(float(price), 3)
    except Exception:
        return None


# ─── インジケーター計算 ───────────────────────────────────────────────────────

def calc_ma(df: pd.DataFrame, short_period: int, long_period: int) -> pd.DataFrame:
    """移動平均線を計算して列を追加する"""
    df = df.copy()
    df[f"MA{short_period}"] = df["close"].rolling(window=short_period).mean()
    df[f"MA{long_period}"] = df["close"].rolling(window=long_period).mean()
    return df


def calc_bb(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """ボリンジャーバンドを計算して列を追加する（BB_UPPER, BB_MIDDLE, BB_LOWER）"""
    df = df.copy()
    bbands_df = TA.BBANDS(df, period=period)
    df = pd.concat([df, bbands_df], axis=1)
    return df


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACDを計算して列を追加する（MACD, SIGNAL, HISTOGRAM）"""
    df = df.copy()
    macd_df = TA.MACD(df, period_fast=fast, period_slow=slow, signal=signal)
    df = pd.concat([df, macd_df], axis=1)
    df["HISTOGRAM"] = df["MACD"] - df["SIGNAL"]
    return df


def calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSIを計算して列を追加する"""
    df = df.copy()
    df["RSI"] = TA.RSI(df, period=period)
    return df


def calc_stochastic(df: pd.DataFrame, k: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> pd.DataFrame:
    """スロー・ストキャスティクスを計算して列を追加する（slow_k, slow_d）"""
    df = df.copy()
    fast_k = TA.STOCH(df, period=k)
    df["slow_k"] = fast_k.rolling(window=smooth_k).mean()
    df["slow_d"] = df["slow_k"].rolling(window=smooth_d).mean()
    return df


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ATRを計算して列を追加する"""
    df = df.copy()
    df["ATR"] = TA.ATR(df, period=period)
    return df


def calc_obv(df: pd.DataFrame) -> pd.DataFrame:
    """OBVを計算して列を追加する"""
    df = df.copy()
    df["OBV"] = TA.OBV(df)
    return df


def calc_sar(df: pd.DataFrame) -> pd.DataFrame:
    """パラボリックSARを計算して列を追加する（PSAR）"""
    df = df.copy()
    psar_df = TA.PSAR(df)
    df["PSAR"] = psar_df["psar"]
    return df


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ADX/DMIを計算して列を追加する（ADX, PDI, MDI）"""
    df = df.copy()
    df["ADX"] = TA.ADX(df, period=period)
    dmi_df = TA.DMI(df, period=period)
    df["PDI"] = dmi_df["DI+"]
    df["MDI"] = dmi_df["DI-"]
    return df


def calc_fibonacci(df: pd.DataFrame, trend: str = "up") -> dict:
    """
    フィボナッチリトレースメントのレベル価格をdictで返す。
    trend="up": 上昇トレンド（高値から安値へのリトレース）
    trend="down": 下降トレンド（安値から高値へのリトレース）
    """
    period_high = df["high"].max()
    period_low = df["low"].min()
    period_range = period_high - period_low

    if trend == "up":
        return {
            "0.0%": period_high,
            "23.6%": period_high - period_range * 0.236,
            "38.2%": period_high - period_range * 0.382,
            "50.0%": period_high - period_range * 0.500,
            "61.8%": period_high - period_range * 0.618,
            "100.0%": period_low,
        }
    else:
        return {
            "0.0%": period_low,
            "23.6%": period_low + period_range * 0.236,
            "38.2%": period_low + period_range * 0.382,
            "50.0%": period_low + period_range * 0.500,
            "61.8%": period_low + period_range * 0.618,
            "100.0%": period_high,
        }


def calc_mayer_multiple(df: pd.DataFrame) -> pd.DataFrame:
    """メイヤーマルチプルを計算して列を追加する（SMA200, Mayer_Multiple）"""
    df = df.copy()
    df["SMA200"] = df["close"].rolling(window=200).mean()
    df["Mayer_Multiple"] = df["close"] / df["SMA200"]
    return df
