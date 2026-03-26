# CLAUDE.md

このファイルは、リポジトリで作業する際にClaude Code (claude.ai/code) へのガイダンスを提供します。

## プロジェクト概要

StreamlitとPlotlyで構築したBTC/USDT テクニカル分析ダッシュボード。CCXTを通じてBinanceからリアルタイムのOHLCVデータを取得し、複数のテクニカル指標を切り替えられるインタラクティブなローソク足チャートを表示する。UIのラベルとコメントは日本語。

## コマンド

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# アプリの起動（http://localhost:8501 で開く）
streamlit run app.py
```

自動テストはない。指標を単体で試す場合は `researchB.ipynb` を使って動作確認してから `app.py` に組み込む。

## アーキテクチャ

2モジュール構成：

- **`indicators.py`** — 純粋なデータ層。BinanceからのOHLCV取得とFintaを使った指標計算を担当。すべての関数はDataFrameを受け取り、新しい列を追加したDataFrameを返す。UIやPlotlyへの依存はない。
- **`app.py`** — プレゼンテーション層。サイドバーのUI制御、Plotlyサブプロットのチャート構築、`@st.cache_data` キャッシュを担当。

### データフロー

1. サイドバーで設定 → 2. `fetch_ohlcv_df()` または `fetch_ohlcv_since_year()` でBinanceからデータ取得 → 3. `indicators.py` の指標計算関数を適用 → 4. Plotlyマルチ行サブプロット（行1: ローソク足＋オーバーレイ、行2: 出来高、行3以降: オシレーター系）

### キャッシュ

| キャッシュ対象関数 | TTL |
|---|---|
| `get_data()` 直近OHLCVデータ | 5分 |
| `get_mayer_data()` 2018年以降の履歴データ | 1時間 |
| `get_usdjpy()` USD/JPYレート | 60秒 |

サイドバーの「データ更新」ボタンで手動クリア可能。

### 主な依存ライブラリ

- **ccxt** — Binance公開API（認証不要）
- **finta** — テクニカル指標計算（MACD、RSI、BB、ストキャスティクス、ATR、OBV、ADX）
- **streamlit** — リアクティブなWebUI＆キャッシュ
- **plotly** — インタラクティブなサブプロット

### 新しい指標を追加する手順

1. `indicators.py` にDataFrameを受け取って新しい列を追加して返す計算関数を追加
2. `app.py` のサイドバーにトグルを追加
3. `app.py` のPlotlyチャート構築部分に新しいサブプロット行を追加
