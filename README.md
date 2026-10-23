# LocalTranslater

ローカルの Ollama で動く Gemma 4 を使った、LAN 内向けの翻訳 Web アプリです。
Linux サーバー上で動かし、LAN 内の PC・スマホのブラウザから使います。

## 機能

- 翻訳元 / 翻訳先の言語を指定して翻訳(翻訳元は「自動検出」も可)
- 38 言語に対応(日本語・英語・中国語(簡体字/繁体字)を先頭に表示)
- 翻訳結果のストリーミング表示、途中停止
- 任意の「追加の指示」(例: 「ですます調で」「専門用語は英語のまま」)
- 言語の入れ替え、結果のコピー、言語選択と指示の記憶(ブラウザに保存)
- パスワードによるログイン(5 回失敗すると 5 分ロック)
- UI 表示言語は OS / ブラウザの言語に自動で合わせる(日本語・英語・中国語。手動でも切り替え可、該当なしは日本語)
- スマホ表示対応、ダークモード対応
- 同時に送る翻訳の数を制限し、超えた分は順番待ち
- ショートカット: 入力欄で Ctrl+Enter(Mac は ⌘+Enter)で翻訳

## 構成

```
[LAN 内の端末のブラウザ] ──HTTP:8000──> [LocalTranslater (FastAPI)] ──localhost:11434──> [Ollama (gemma4:26b)]
```

Ollama は localhost のままで、LAN には公開しません。

## セットアップ

### 1. Ollama の準備

```bash
ollama pull gemma4:26b      # 未取得なら
ollama list                 # モデル名を確認
```

複数人で同時に使うなら、Ollama 側の並列数を設定しておきます(DGX Spark 128GB なら 3〜4 程度で十分足ります)。

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_NUM_PARALLEL=3"
```

```bash
sudo systemctl restart ollama
```

### 2. インストール

```bash
sudo apt install -y python3-venv git    # 未インストールなら
git clone https://github.com/kannlight/LocalTranslater.git
cd LocalTranslater
sudo ./deploy/install.sh
```

スクリプトは次のことを行います。

- システムユーザー `localtranslater` の作成
- アプリを `/opt/localtranslater` にコピーし、Python の仮想環境と依存パッケージをインストール
- 設定ファイル `/etc/localtranslater.env` の作成(初回のみ。ログインパスワードを聞かれます)
- systemd サービス `localtranslater` の登録・起動(OS 起動時に自動起動)

### 3. ファイアウォール(ufw を使っている場合)

```bash
sudo ufw allow from 192.168.0.0/16 to any port 8000 proto tcp   # LAN のアドレス帯に合わせて変更
```

### 4. アクセス

LAN 内の端末のブラウザで `http://<サーバーのIPアドレス>:8000/` を開きます。
スマホでは、ブラウザの「ホーム画面に追加」を使うとアプリのように開けます。

## 運用

```bash
sudo systemctl status localtranslater       # 状態
sudo journalctl -u localtranslater -f       # ログ
sudo systemctl restart localtranslater      # 再起動
```

### 更新

```bash
cd LocalTranslater
git pull
sudo ./deploy/install.sh      # 既存の /etc/localtranslater.env はそのまま使います
```

### 設定変更

`/etc/localtranslater.env` を編集し、`sudo systemctl restart localtranslater` で反映します。

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `LT_HOST` / `LT_PORT` | `0.0.0.0` / `8000` | 待ち受けアドレスとポート |
| `LT_PASSWORD` | (必須) | ログインパスワード。変更すると全端末がログアウトします |
| `LT_SECRET_KEY` | (自動生成) | ログイン Cookie の署名鍵 |
| `LT_SESSION_DAYS` | `30` | ログインの有効日数 |
| `LT_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama の URL |
| `LT_MODEL` | `gemma4:26b` | 使用するモデル |
| `LT_MAX_CONCURRENT` | `3` | Ollama に同時に送る翻訳数(`OLLAMA_NUM_PARALLEL` 以下にする) |
| `LT_NUM_CTX` | `32768` | コンテキスト長(トークン)。入力+出力が収まる大きさにする |
| `LT_TEMPERATURE` | `0.2` | 生成の温度。低いほど訳が安定します |
| `LT_THINK` | (空) | 思考モード。空ならモデルの既定、`true` / `false` で明示 |
| `LT_KEEP_ALIVE` | `30m` | 最後のリクエストの後、モデルをメモリに置いておく時間 |
| `LT_REQUEST_TIMEOUT` | `600` | 翻訳 1 件のタイムアウト(秒) |
| `LT_MAX_INPUT_CHARS` | `20000` | 入力の最大文字数 |
| `LT_MAX_INSTRUCTION_CHARS` | `1000` | 追加の指示の最大文字数 |

パスワードには引用符(`"` `'`)とバックスラッシュを使わないでください(systemd の設定ファイルで別の意味になるため)。

## トラブルシューティング

- **「Cannot connect to Ollama」と出る**: `systemctl status ollama` と `curl http://127.0.0.1:11434/api/tags` で Ollama が動いているか確認してください。
- **「model 'gemma4:26b' not found」と出る**: `ollama list` で表示される名前を `LT_MODEL` に設定してください。
- **最初の翻訳だけ遅い**: モデルの読み込みに時間がかかっています。`LT_KEEP_ALIVE` を長くすると、読み込み直しが減ります。
- **翻訳に思考過程が混ざる / 出力が始まるまで遅い**: `LT_THINK=false` を試してください。
- **他の端末から開けない**: ファイアウォールの設定と、`LT_HOST=0.0.0.0` になっているかを確認してください。

## セキュリティについて

通信は HTTP(暗号化なし)なので、LAN 内での利用を前提にしています。インターネットには公開しないでください。
外から使いたい場合は、Tailscale などの VPN を使うか、HTTPS 対応のリバースプロキシ(Caddy など)を前に置いてください。

## 開発

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
LT_PASSWORD=dev .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### ファイル構成

```
app/
  main.py        # FastAPI アプリ(ログイン、Ollama へのストリーミング中継、順番待ち)
  config.py      # 環境変数から読む設定
  auth.py        # パスワード認証と Cookie 署名、ログイン試行の制限
  prompt.py      # 翻訳用プロンプト
  languages.py   # 対応言語の一覧
  static/        # フロントエンド(HTML / CSS / JS、ビルド不要)
deploy/
  install.sh                    # インストール・更新スクリプト
  localtranslater.service       # systemd ユニット
  localtranslater.env.example   # 設定ファイルの雛形
tests/
```
