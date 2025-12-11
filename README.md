# Valorant Tracker

Valorantの試合データとボイスチャット（VC）を統合的にトラッキング・分析するシステム。

## 機能

- **マッチトラッキング**: Valorant APIと連携し、試合情報を自動記録
- **VC録音・同期**: マッチ開始と同時に音声録音を開始し、イベントと同期
- **音声認識**: Faster-Whisperによる日本語音声認識（Valorant用語最適化）
- **2Dリプレイ**: マップ上でのプレイヤー位置とVCの同期再生
- **統計分析**: プレイヤー/マップ/エージェント別の統計
- **AI評価**: コミュニケーションの質をAIが評価

## セットアップ

### 前提条件

- Python 3.10以上
- Windows 10/11
- Valorantクライアント（起動中）
- LM Studio（AI評価機能使用時）

### インストール

```powershell
# リポジトリのクローン
cd D:\python
git clone <repository-url> valorant_tracker
cd valorant_tracker

# 仮想環境の作成
python -m venv .venv
.\.venv\Scripts\Activate

# 依存関係のインストール
pip install -e .

# 開発用依存関係（オプション）
pip install -e ".[dev]"
```

### 環境設定

```powershell
# .envファイルを作成
copy .env.example .env

# .envを編集して必要な設定を行う
```

## 使い方

### CLIコマンド

```powershell
# ヘルスチェック
python -m src.main --health

# マッチトラッキング開始
python -m src.main --track

# ダッシュボード起動
streamlit run dashboard/app.py
```

### ダッシュボード

```powershell
streamlit run dashboard/app.py
```

ブラウザで http://localhost:8501 にアクセス。

## プロジェクト構成

```
valorant_tracker/
├── config/               # 設定ファイル
├── src/
│   ├── api/              # Valorant API連携
│   ├── audio/            # 音声録音・認識
│   ├── db/               # データベース
│   ├── sync/             # タイムライン同期
│   ├── services/         # ビジネスロジック
│   ├── vision/           # 画像認識
│   ├── intelligence/     # AI評価
│   ├── replay/           # 2Dリプレイ
│   └── main.py
├── dashboard/            # Streamlit UI
├── data/
│   ├── recordings/       # 音声ファイル
│   └── output/           # 出力JSON
├── tests/
├── REQUIREMENTS.md       # 要件定義書
└── README.md
```

## 統合元プロジェクト

このプロジェクトは以下の2つのプロジェクトを統合したものです：

- **comms_tracker** (Tactical Echo): 音声認識・AI評価
- **tracker** (VRYJS): Valorant API連携・統計

## ライセンス

MIT License

## 将来的な統合予定

このプロジェクトは将来的に **KPI** (Valorant KPI管理Webアプリ) に統合される予定です。

