# SATD Comment Locator

`maldonado_corrected.csv` の `comment_text` を、`project_name` に対応するソースコード中から探すためのスクリプト群です。

## 構成

- `find_comment_locations.py`
  `comment_text` の出現箇所をソースコードから検索し、CSVで出力します。
- `csv_summary.py`
  入力CSVの件数、欠損、代表的な値を確認するための補助スクリプトです。
- `repo_map.example.csv`
  `project_name` とローカルのリポジトリパスの対応表のサンプルです。
- `maldonado_corrected.csv`
  入力データセットです。

## 前提

- Python 3 が使えること
- 対象プロジェクトのソースコードがローカルにあること
- 入力CSVに少なくとも `project_name` と `comment_text` 列があること

## 使い方

### 1. リポジトリ対応表を用意する

`repo_map.example.csv` を参考に `repo_map.csv` を作成します。

```csv
project_name,repo_path
apache-ant-1.7.0,repos/ant
apache-jmeter-2.10,repos/jmeter
argouml,repos/argouml
```

### 2. コメント位置を検索する

```bash
python3 find_comment_locations.py maldonado_corrected.csv --mapping repo_map.csv
```

既定では `comment_locations.csv` に出力します。

標準出力へ出したい場合:

```bash
python3 find_comment_locations.py maldonado_corrected.csv --mapping repo_map.csv --output -
```

特定プロジェクトだけを対象にしたい場合:

```bash
python3 find_comment_locations.py maldonado_corrected.csv --mapping repo_map.csv --project apache-ant-1.7.0
```

`project_name` と同じディレクトリ名でリポジトリを並べている場合は、対応表の代わりに `--repos-root` も使えます。

```bash
python3 find_comment_locations.py maldonado_corrected.csv --repos-root repos
```

### 3. 入力CSVを要約する

```bash
python3 csv_summary.py maldonado_corrected.csv
```

任意の列で集計したい場合:

```bash
python3 csv_summary.py maldonado_corrected.csv --group-by classification --group-by satd
```

## `find_comment_locations.py` の引数

- `csv_path`
  入力CSVのパス
- `--mapping`
  `project_name,repo_path` を持つ対応表CSV
- `--repos-root`
  `project_name` と同名ディレクトリを持つ親ディレクトリ
- `--project`
  指定した `project_name` だけを処理。複数指定可
- `--mode rows`
  入力CSVの各行ごとに出力。既定値
- `--mode unique`
  `project_name + comment_text` 単位で重複をまとめて出力
- `--max-matches`
  1コメントあたりの最大出力件数。既定値は `5`
- `--output`
  出力先CSV。`-` を指定すると標準出力

## 入力仕様

### `find_comment_locations.py`

入力CSVには少なくとも次の列が必要です。

```csv
project_name,comment_text
```

実データでは以下のような列をそのまま扱えます。

```csv
project_name,classification,comment_text,satd_orig,satd
```

### `csv_summary.py`

ヘッダー行付きの一般的なCSVを対象にしています。

## 出力仕様

### `find_comment_locations.py`

既定の `--mode rows` では、入力CSVの各列を保持したまま検索結果を付与します。

主要な追加列:

- `input_row`
  入力CSV上の行番号。ヘッダーを1行目として数えます
- `repo_path`
  検索に使ったローカルリポジトリパス
- `match_status`
  `matched` / `not_found` / `repo_not_found`
- `match_type`
  どう一致したかを示す内部種別
- `file_path`
  リポジトリルートからの相対パス
- `start_line`
  コメント開始行
- `end_line`
  コメント終了行

出力例:

```csv
input_row,project_name,comment_text,repo_path,match_status,match_type,file_path,start_line,end_line
2,demo-project,// XXX: first line // second line // third line,/private/tmp/comment-repos/demo-project,matched,block_flat,src/Main.java,3,5
```

`--mode unique` では入力行ごとの情報ではなく、`project_name` と `comment_text` の組ごとに `input_count` を出力します。

### `csv_summary.py`

標準出力に次を表示します。

- ファイル名
- 行数
- 列数
- ヘッダー一覧
- 列ごとの欠損数
- 指定列の上位頻度

## 内部仕様

### 検索の流れ

`find_comment_locations.py` は次の順で処理します。

1. 入力CSVを `DictReader` で読み込みます
2. `project_name` から対象リポジトリを解決します
3. 対象リポジトリ配下のテキスト系ファイルを走査します
4. ソースコードからコメントブロックを抽出します
5. コメントを正規化して索引を作ります
6. `comment_text` を正規化し、索引に照合します
7. 見つかった場所をCSVへ書き出します

### リポジトリ解決

- `--mapping` があれば最優先で使います
- 対応表に無い場合だけ `--repos-root / project_name` を試します
- どちらでも見つからなければ `repo_not_found` になります

### 対象ファイル

以下の条件を満たすファイルだけを検索します。

- 拡張子が `TEXT_SUFFIXES` に含まれる
- サイズが 2MB 以下
- `.git`, `node_modules`, `build`, `dist`, `target` などの除外ディレクトリ配下ではない

### コメント抽出

抽出対象:

- `// ...`
- `/* ... */`
- `<!-- ... -->`
- 行頭の `--`, `#`, `;`

実装上のポイント:

- 連続した `//` コメントは1つのブロックとしてまとめます
- `// ... // ...` のように CSV 上で1行に潰れたコメントは復元候補を作って照合します
- 文字列リテラル中の `//` や `/*` はコメント開始として扱いません
- `//************************************************************************` のような記号列も `//` コメントとして扱います
- `//$NON-NLS-1$` のような行末コメントも抽出対象です

### 正規化

照合前に次の正規化を行います。

- 前後空白の除去
- 連続空白の1文字化
- 必要に応じてコメント接頭辞の除去
- 複数行コメントの1行結合

1つのコメントに対して、主に次のキーを作ります。

- 行単位キー
- 複数行を改行で連結したキー
- 複数行を空白1つで連結したキー

これにより、入力CSV側が改行付きでも1行に潰れていても一致しやすくしています。

### `match_type`

代表的な値:

- `line`
  単一行コメントに一致
- `block`
  ブロック単位の一致
- `block_flat`
  複数行コメントを1行に畳んだ形で一致
- `line_stripped`, `block_stripped`, `block_flat_stripped`
  コメント記号を除去した正規化後に一致

### 重複除去

同じ `file_path`, `start_line`, `end_line` を持つ候補は1件にまとめます。

## 制約

- コメント以外の文字列中に同じ文面があっても検出対象にはしません
- コメント抽出は完全な構文解析ではなく、テキストベースです
- 1つの `comment_text` が複数箇所に存在する場合、既定では先頭から最大 `5` 件まで出力します
- 対象リポジトリの版がCSVの `project_name` とずれていると、当然ながら見つからないことがあります

## 変更時の目安

- コメント種別を増やすなら `detect_single_line_comment` と `extract_comment_blocks`
- 正規化ルールを変えるなら `normalize_line`, `normalize_block`, `normalized_comment_variants`
- 検索対象拡張子や除外ディレクトリを変えるなら `TEXT_SUFFIXES`, `IGNORED_DIRS`
- 出力列を変えるなら `output_fieldnames`, `write_result_rows`
