# JDT-based comment extractor (reimplementation)

Maldonado らのコメント抽出・フィルタ処理を、Eclipse JDT の AST を使って
Java で再実装したものです。当時の Eclipse プラグインを動かさずに、
データセットと同じファイル集合からコメントを再抽出できます。

## 対象処理

`maldonado/eclipse.commandline` と `maldonado/jdeodorant` の処理を
次の順で再現します。

1. トップレベルの型（クラス・列挙）ごとにコメントを収集
2. Javadoc は `TODO:` / `XXX` / `FIXME` を含むものだけ残す
3. クラス宣言より前のコメントは `TODO:` / `XXX` / `FIXME` を含むものだけ残す
4. クラス内の `copyright` を含むコメントを除く
5. 内部クラスのコメントを除く
6. 隣接する行コメントを連結する
7. `else {`、`if (`、`System.out.` などを含むコメントを除く

## 必要なもの

- Java 17 以上、Maven
- `repos/`（`./setup_repos.sh` で取得）
- `maldonado_corrected.csv`、`data/comment_locations_all.csv`

## 使い方

リポジトリのルートで実行します。

```bash
# データセットのコメントが存在するファイルだけを列挙
python3 jdt_extractor/make_files.py

# コンパイルして実行
mvn -q -f jdt_extractor/pom.xml compile \
    dependency:build-classpath -Dmdep.outputFile=target/cp.txt
java -cp "jdt_extractor/target/classes:$(cat jdt_extractor/target/cp.txt)" \
    JdtExtract repo_map.csv jdt_files.csv jdt_out.csv

# データセットと比較
python3 jdt_extractor/compare_with_dataset.py \
    --report jdt_out.csv \
    --comments jdt_out.csv.comments.csv \
    --output data/jdt_extractor_counts.csv
```

`JdtExtract` の引数は `repo_map.csv`、ファイル一覧、出力 CSV、Java
コンプライアンス（省略時 `1.8`）です。入力ファイルは
`project, repo-relative-path` の2列で、先頭行は読み飛ばされます。

## 出力

- `jdt_out.csv`：ファイルごとの段階別件数
  `project,file,raw,javadoc,license,inner,merge,source,final`
- `jdt_out.csv.comments.csv`：抽出コメント
  `project,file,start,end,text_b64`
- `data/jdt_extractor_counts.csv`：プロジェクト別の比較

## 結果

データセットの `file_path` を持つファイル（`.java` 6,832件）を対象に
実行した結果です。

| プロジェクト | 抽出 | データセット | 差 | 差率 | recall | precision |
|---|---:|---:|---:|---:|---:|---:|
| apache-ant-1.7.0 | 4,314 | 4,098 | +216 | +5.27% | 99.87% | 95.72% |
| apache-jmeter-2.10 | 8,095 | 8,057 | +38 | +0.47% | 99.98% | 98.01% |
| argouml | 9,549 | 9,452 | +97 | +1.03% | 99.84% | 98.35% |
| columba-1.4-src | 6,476 | 6,468 | +8 | +0.12% | 100.00% | 99.67% |
| emf-2.4.1 | 4,380 | 4,390 | -10 | -0.23% | 99.96% | 97.76% |
| hibernate-3.3.2.GA | 2,958 | 2,968 | -10 | -0.34% | 99.69% | 100.00% |
| jEdit-4.2 | 10,051 | 10,322 | -271 | -2.63% | 99.73% | 99.98% |
| jfreechart-1.0.19 | 4,426 | 4,408 | +18 | +0.41% | 99.89% | 99.62% |
| jruby-1.4.0 | 4,815 | 4,897 | -82 | -1.67% | 99.97% | 99.95% |
| sql12 | 7,260 | 7,215 | +45 | +0.62% | 99.94% | 99.67% |
| **合計** | **62,324** | **62,275** | **+49** | **+0.08%** | **99.89%** | **98.93%** |

- 行数の差は合計 +0.08% です。
- jEdit と jruby の不足は、データセット側の重複行が主因です。
  jEdit のユニーク本文の欠落は13件、jruby は1件です。
- ant の超過は `proposal/` 配下のコメントをデータセットが一部しか
  含まないためです。

この実装は、データセットのファイル集合に限定した場合の比較用です。
プロジェクト全体を対象にした当時のツールの結果は
`docker_eclipse/` を参照してください。
