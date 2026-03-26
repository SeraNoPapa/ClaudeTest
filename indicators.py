"""
indicators.py - データ取得とテクニカルインジケーター計算モジュール
UIやPlotlyへの依存なし。全関数はDataFrameを受け取りDataFrameを返す。
"""

import ccxt
import datetime
import requests
import pandas as pd
import numpy as np
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


def get_usdjpy_rate() -> float:
    """Yahoo Finance APIからUSD/JPYレートを取得する"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/JPY=X"
    params = {"range": "1d", "interval": "1m"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            quotes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            valid = [q for q in quotes if q is not None]
            price = valid[-1] if valid else None
        return round(price, 3) if price else None
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
