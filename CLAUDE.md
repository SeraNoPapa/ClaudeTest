# CLAUDE.md

このファイルは、リポジトリで作業する際にClaude Code (claude.ai/code) へのガイダンスを提供します。

## プロジェクト概要

StreamlitとPlotlyで構築したテクニカル分析ダッシュボード。CCXTを通じてBinanceからリアルタイムの暗号通貨OHLCVデータを取得し、yfinanceで参照アセット（日経225、S&P500、USD/JPY、Gold）を表示。複数のテクニカル指標を切り替えられるインタラクティブなローソク足チャートと描画ツール（水平ライン、トレンドライン、並行チャネル、ピッチフォーク）を備える。UIのラベルとコメントは日本語。

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

- **`indicators.py`** — 純粋なデータ層。BinanceからのOHLCV取得（ccxt）、Yahoo Financeからの参照アセットデータ取得（yfinance）、Fintaを使った指標計算を担当。すべての関数はDataFrameを受け取り、新しい列を追加したDataFrameを返す。UIやPlotlyへの依存はない。
- **`app.py`** — プレゼンテーション層。サイドバーのUI制御、Plotlyサブプロットのチャート構築、`@st.cache_data` キャッシュを担当。

### データフロー

1. サイドバーで設定 → 2. `fetch_ohlcv_df()` または `fetch_ohlcv_since_year()` でBinanceからデータ取得 → 3. `indicators.py` の指標計算関数を適用 → 4. Plotlyマルチ行サブプロット（行1: ローソク足＋オーバーレイ、行2: 出来高、行3以降: オシレーター系）
5. 参照アセット: `fetch_yahoo_ohlcv()` でYahoo Financeからデータ取得 → タブ形式で個別チャート表示
6. 描画ツール: サイドバーから座標入力 → セッションステートに保存 → Plotly図形としてレンダリング

### キャッシュ

| キャッシュ対象関数 | TTL |
|---|---|
| `get_data()` 直近OHLCVデータ | 5分 |
| `get_mayer_data()` 2018年以降の履歴データ | 1時間 |
| `get_usdjpy()` USD/JPYレート | 60秒 |
| `get_reference_data()` 参照アセットOHLCV | 10分 |

サイドバーの「データ更新」ボタンで手動クリア可能。

### 主な依存ライブラリ

- **ccxt** — Binance公開API（認証不要）
- **yfinance** — Yahoo Finance API（日経225、S&P500、USD/JPY、Gold）
- **finta** — テクニカル指標計算（MACD、RSI、BB、ストキャスティクス、ATR、OBV、ADX）
- **streamlit** — リアクティブなWebUI＆キャッシュ
- **plotly** — インタラクティブなサブプロット

### 新しい指標を追加する手順

1. `indicators.py` にDataFrameを受け取って新しい列を追加して返す計算関数を追加
2. `app.py` のサイドバーにトグルを追加
3. `app.py` のPlotlyチャート構築部分に新しいサブプロット行を追加
