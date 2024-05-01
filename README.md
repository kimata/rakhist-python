# rakhist-python

rakhist-python は，楽天の購入履歴を収集し，
サムネイル付きの Excel 形式で出力するソフトウェアです．

## 動作環境

基本的には，Python と Selenium が動作する環境であれば動作します．
下記の環境での動作を確認しています．

- Linux (Ubuntu 22.04)
- Windows 11

## 設定

同封されている `config.example.yaml` を `config.yaml` に名前変更して，下記の部分を書き換えます．

```yaml:config.yaml
  user: 楽天のユーザ名
  pass: 楽天のパスワード
```

## Linux での動かし方

### 必要なパッケージのインストール

実行に際して `docker-compose` を使用しますので，インストールします．
Ubuntu の場合，以下のようにします．

```
sudo apt install docker-compose
```
### 実行

以下のようにします．`build` は一回だけ実行すればOKです．

```
docker-compose build
docker-compose run --rm rakhist
```

取引履歴の数が沢山ある場合，1時間以上がかかりますので，放置しておくのがオススメです．

なお，何らかの事情で中断した場合，再度実行することで，途中から再開できます．
コマンドを実行した後に注文履歴が増えた場合も，再度実行することで前回以降のデータからデータ収集を再開できます．

### Docker を使いたくない場合

[Poetry](https://python-poetry.org/) と Google Chrome がインストールされた環境であれば，
下記のようにして Docker を使わずに実行することもできます．

```
poetry install
poetry run app/rakhist.py
```

## Windows での動かし方

### 準備

[リリースページ](https://github.com/kimata/rakhist-python/releases) から「rakhist-windows_x64-binary-*.zip」を
ダウンロードします．

#### 注意

環境によってはファイルがウィルス判定されることがあります．
これは，Python スクリプトを [Nuitka](https://nuitka.net/) を使って実行ファイルを生成していることが原因です．

ウィルス判定されてしまった場合は，検疫されないように Windows Defender の設定を一時的に変更お願いします．

### 実行

`rakhist.exe` をダブルクリックすればOKです．

## ライセンス

Apache License Version 2.0 を適用します．
