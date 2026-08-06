# otobanana-downloader

OTOBANANA（オトバナナ）の音声投稿（キャスト）を保存・ダウンロードするためのPythonツールです。  
単音声の保存に加え、ユーザーの全投稿（一般・Deep/R18問わず）の一括ダウンロード、マルチスレッド並列処理に対応しています。

---

## 機能一覧
まぁなんか一個音声ダウンロードできたりユーザーの音声ぜんぶダウンロードできたりああああ。

---

## 使い方

### Python環境で実行する場合

```bash
python main.py
```

### 実行ファイル (.exe) で実行する場合

1. [Releases](../../releases) ページから `otobanana-downloader.exe` をダウンロードします。
2. 実行ファイルを開いて利用します。

---

## 保存フォルダ構造

```text
保存先フォルダ/
  └── ユーザー名/
        ├── 一般/
        │     └── 音声タイトル.mp3
        └── R18/
              └── 音声タイトル.mp3
```

---

## 検索用キーワード

OTOBANANA, オトバナナ, OTOBANANA ダウンローダー, オトバナナ 保存, OTOBANANA 音声保存, OTOBANANA mp3, OTOBANANA ユーザー一括ダウンロード, オトバナナ ボイス 保存, otobanana-downloader, otobanana-saver, audio-downloader

---

## 免責事項

本ツールは個人の学習および私的利用の目的で作成されています。著作権法および利用規約を遵守してご使用ください。

## ライセンス

[GPL v3 License](LICENSE) (by wploits)
