# ewftools (libewf) 導入ガイド

MFEPS で E01 形式の証拠保全を行うには、libewf の `ewfacquire.exe` が必要です。

## 入手方法

### 方法 1: ビルド済みバイナリ

- https://github.com/libyal/libewf/releases から Windows ビルドを取得
- または libewf-legacy: https://github.com/libyal/libewf-legacy

### 方法 2: SIFT Workstation / Kali Linux からコピー

- 既にインストールされた環境から `ewfacquire`, `ewfverify` をコピー

### 方法 3: 自前ビルド (MSVC)

- https://github.com/libyal/libewf/wiki/Building の手順に従う

## 配置

```
mfeps/
  libs/
    ewfacquire.exe
    ewfverify.exe     (任意: 自動検証に使用)
    ewfinfo.exe       (任意: メタデータ確認用)
```

## .env 設定

```
EWFACQUIRE_PATH=./libs/ewfacquire.exe
EWFVERIFY_PATH=./libs/ewfverify.exe
```

## 動作確認

管理者権限のコマンドプロンプトで:

```
.\libs\ewfacquire.exe -V
.\libs\ewfverify.exe -V
```

バージョン情報が表示されれば OK です。

## ライセンス

libewf は **LGPL-3.0-or-later** です。
MFEPS は ewfacquire.exe を同梱せず、ユーザーが自身で配置する方式のため、
MFEPS 本体の MIT ライセンスとは競合しません。

詳細は THIRD_PARTY_LICENSES.md を参照してください。
