# SATD Comment Locator

`maldonado_corrected.csv` の `comment_text` を、`project_name` に対応するソースコード中から探すためのスクリプト群です。

## 構成

- `find_comment_locations.py`
  `comment_text` の出現箇所をソースコードから検索し、CSVで出力します。
- `csv_summary.py`
  入力CSVの件数、欠損、代表的な値を確認するための補助スクリプトです。
- `repo_map.example.csv`
  `project_name` とローカルのリポジトリパスの対応表のサンプルです。
- `setup_repos.sh`
  `repos/` を10プロジェクト分復元します（全履歴、約1.9GB）。
- `maldonado_corrected.csv`
  入力データセットです。出所は「データの出所」を参照してください。

## データの出所

`maldonado_corrected.csv` は、Maldonado らが公開している SATD データセットから作成した派生ファイルです。

- 原データ: `maldonado/tse.satd.data` リポジトリの `dataset/technical_debt_dataset.zip` に含まれる `technical_debt_dataset.csv`
- 取得元 URL: <https://github.com/maldonado/tse.satd.data>（zip は <https://raw.githubusercontent.com/maldonado/tse.satd.data/master/dataset/technical_debt_dataset.zip>）
- 原データの列: `projectname,classification,commenttext`、62,275 行、10 プロジェクト
- 出典論文:
  - E. da S. Maldonado and E. Shihab, "Detecting and Quantifying Different Types of Self-Admitted Technical Debt," MTD 2015.
  - E. da S. Maldonado, E. Shihab, and N. Tsantalis, "Using Natural Language Processing to Automatically Detect Self-Admitted Technical Debt," IEEE TSE, 43(11), 2017.
  - 論文では 62,566 コメントと報告されていますが、公開されている CSV は 62,275 行です。

`maldonado_corrected.csv` は原データと行単位・行順で一致しており、差分は次の列だけです。

| 列 | 内容 |
| --- | --- |
| `project_name` / `comment_text` | 原データの `projectname` / `commenttext` を改名 |
| `satd_orig` | 原データの `classification` が `WITHOUT_CLASSIFICATION` 以外なら `1`（4,071 件） |
| `satd` | 修正後のラベル（4,497 件）。`satd_orig` の 4,071 件に 426 件を追加し、削除はなし |

追加された 426 件は、原データで `WITHOUT_CLASSIFICATION` だったコメントのうち、TODO、FIXME、XXX、HACK、workaround などの語を含むものです。追加分の `classification` は `WITHOUT_CLASSIFICATION` のままです。

再取得する場合:

```bash
curl -LO https://raw.githubusercontent.com/maldonado/tse.satd.data/master/dataset/technical_debt_dataset.zip
unzip technical_debt_dataset.zip
```

`satd` 列の 426 件の追加はこのリポジトリの CSV にのみ含まれ、上記の公開データには含まれていません。

## 前提

- Python 3 が使えること
- 対象プロジェクトのソースコードがローカルにあること
- `--blame` を使う場合は対象リポジトリが Git 管理されていること
- 入力CSVに少なくとも `project_name` と `comment_text` 列があること

## リポジトリの取得

`repos/` が無い場合は、次のスクリプトで10プロジェクト分を復元できます。

```bash
./setup_repos.sh
```

各リポジトリを全履歴付きで clone し、データセットの版（`PROJECTS` に SHA で記載）に checkout します。約1.9GB が必要です。

一部だけ取得する場合:

```bash
./setup_repos.sh jruby-1.4.0
```

保存先を変える場合は `REPOS_ROOT`、既存の複製を取り直す場合は `FORCE=1` を指定します。

```bash
REPOS_ROOT=/path/to/repos FORCE=1 ./setup_repos.sh
```

## 使い方

### 1. リポジトリ対応表を用意する

`repo_map.csv` に10プロジェクト分の対応を用意しています。別の場所に置く場合は `repo_map.example.csv` を参考に作成します。

`repo_path` には、通常は `src` や `test` の親を含むリポジトリルートを指定します。例えば JMeter のテストコードも検索したい場合は `repos/apache-jmeter-2.10` を指定します。

ディレクトリ名は `maldonado_corrected.csv` の `project_name` と一致させています。

```csv
project_name,repo_path
apache-ant-1.7.0,repos/apache-ant-1.7.0
apache-jmeter-2.10,repos/apache-jmeter-2.10
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

一致したコメント行の `git blame` を取り、対応コミットの内容と差分も保存したい場合:

```bash
python3 find_comment_locations.py \
  maldonado_corrected.csv \
  --mapping repo_map.csv \
  --blame \
  --artifacts-dir comment_git_artifacts
```

`--blame` を付けると、マッチした行範囲に対して `git blame` を実行し、対応するコミット ID を出力 CSV に追加します。

一致したコメントの前後にあるコードも出力したい場合:

```bash
python3 find_comment_locations.py \
  maldonado_corrected.csv \
  --mapping repo_map.csv \
  --context-lines 3
```

`--context-lines N` を付けると、コメントの開始行より前と終了行より後の `N` 行を、それぞれ `code_before` / `code_after` として出力 CSV に追加します。`--blame` と併用できます。

`--artifacts-dir` 配下には次を保存します。

- `commits/<project_name>/<commit_id>/commit.txt`
  コミットのメタデータとメッセージ
- `commits/<project_name>/<commit_id>/diff.patch`
  そのコミットの差分
- `matches/<project_name>/*.json`
  コメント範囲の各行がどのコミットに対応するか、および保存済みコミットファイルへの参照

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
  入力CSVの各行ごとに出力。既定値。各入力行につき出力は最大1件
- `--mode unique`
  `project_name + comment_text` 単位で重複をまとめて出力
- `--max-matches`
  主に `--mode unique` での1コメントあたりの最大出力件数。既定値は `5`
- `--output`
  出力先CSV。`-` を指定すると標準出力
- `--blame`
  マッチしたコメント行に対して `git blame` を実行し、コミット情報を出力に追加
- `--context-lines`
  マッチしたコメントの開始行の前と終了行の後から、指定した行数を `code_before` / `code_after` として出力に追加。既定値は `0`（無効）
- `--artifacts-dir`
  `--blame` で取得したコミット情報、差分、行単位 blame レポートの保存先。既定値は `comment_git_artifacts`

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

`--context-lines` を付けた場合は、さらに次の列が追加されます。

- `code_before`
  コメント開始行の直前 `N` 行のコード
- `code_after`
  コメント終了行の直後 `N` 行のコード

`--blame` を付けた場合は、さらに次の列が追加されます。

- `blame_status`
  `blamed` / `not_git_repo` / `blame_failed` など
- `blame_commit_ids`
  コメント範囲に対応するコミット ID の一覧
- `blame_line_commits`
  行番号ごとのコミット対応。例: `188-190=<sha>;191=<sha>`
- `blame_report_path`
  保存した行単位 blame レポート JSON のパス
- `blame_error`
  `git blame` や `git show` が失敗した場合のエラー内容

`--mode rows` では、各入力行につき出力は最大1件です。

同じ `project_name` と `comment_text` の行が複数ある場合は、同じ位置を使い回しません。1件目は最初の一致箇所、2件目以降は既に出力した位置を除いた次の一致箇所を1件ずつ割り当てます。候補を使い切った行は `not_found` になります。

出力例:

```csv
input_row,project_name,comment_text,repo_path,match_status,match_type,file_path,start_line,end_line
2,demo-project,// XXX: first line // second line // third line,/private/tmp/comment-repos/demo-project,matched,block_flat,src/Main.java,3,5
```

`--mode unique` では入力行ごとの情報ではなく、`project_name` と `comment_text` の組ごとに `input_count` を出力します。

`--mode unique` では、同じコメントに複数の一致箇所があれば `--max-matches` 件まで出力します。

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
- `//` のようにコメント記号しか無く、実質的な本文を持たないコメントは検索対象から除外します

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

複数の `match_type` で同じ `comment_text` に一致する場合は、次の優先順位で最も強い1種類だけを残します。

- `block`
- `block_flat`
- `block_stripped`
- `block_flat_stripped`
- `line`
- `line_stripped`

### 重複除去

同じ `file_path`, `start_line`, `end_line` を持つ候補は1件にまとめます。さらに、同じ入力行に対して複数の候補が見つかっても、`--mode rows` では最終的に1件だけを出力します。

### 前後コードの取得

`--context-lines N`（`N > 0`）を指定したときだけ、一致したファイルを読み込みます。

- `code_before` は `start_line` の直前 `N` 行
- `code_after` は `end_line` の直後 `N` 行

複数行コメントでは、`code_after` はコメントの終了行を基準にします。読み込んだファイルは行単位でキャッシュし、同じ `file_path` / `start_line` / `end_line` の結果も再利用します。ファイルが読めない場合は空文字を出力します。

## 制約

- コメント以外の文字列中に同じ文面があっても検出対象にはしません
- コメント抽出は完全な構文解析ではなく、テキストベースです
- `--mode rows` では、1つの入力行に対して複数箇所が見つかっても1件だけを出力します
- `--mode unique` では、1つの `comment_text` が複数箇所に存在する場合、既定では先頭から最大 `5` 件まで出力します
- 対象リポジトリの版がCSVの `project_name` とずれていると、当然ながら見つからないことがあります

## 変更時の目安

- コメント種別を増やすなら `detect_single_line_comment` と `extract_comment_blocks`
- 正規化ルールを変えるなら `normalize_line`, `normalize_block`, `normalized_comment_variants`
- 検索対象拡張子や除外ディレクトリを変えるなら `TEXT_SUFFIXES`, `IGNORED_DIRS`
- 出力列を変えるなら `output_fieldnames`, `write_result_rows`
