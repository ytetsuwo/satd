# Legacy Eclipse comment extractor (Docker)

Maldonado らが使用した当時の Eclipse プラグイン
（`eclipse.commandline` + JDeodorant 5.0.22）を、Eclipse 4.4.2 /
OpenJDK 8 / PostgreSQL 12 のコンテナで動かすための環境です。

JDT で処理を書き直した `jdt_extractor/` とは別に、**当時のツール本体**を
そのまま実行してコメントを抽出します。

## 構成

- `Dockerfile`：Ubuntu 20.04、Eclipse 4.4.2 SDK、OpenJDK 8、PostgreSQL 12
- `entrypoint.sh`：PostgreSQL の起動、DB `comment_classification` の作成、
  Eclipse アプリケーションの実行
- `jars/`：ビルド済みプラグイン
  - `eclipse.commandline_1.0.0.jar`（抽出を有効化し、プロジェクト自動登録と
    `onlyProject` フィルタを追加した版）
  - `gr.uom.java.jdeodorant_5.0.22.jar`（NPE 回避パッチ入り）
  - `draw2d-3.8.1-fixed.jar`（Eclipse 4.4 の ICU 制約を外した版）
- `patches/`：変更したソース（`Application.java`、`ASTReader.java`、
  `AbstractMethodFragment.java`）
- `compare_with_dataset.py`：抽出結果とデータセットの比較

## ビルドと実行

Apple Silicon では `--platform linux/amd64` を指定します。QEMU ではなく
Rosetta を使うと JVM の SIGILL を避けられます。

```bash
docker build --platform linux/amd64 -t maldonado-eclipse docker_eclipse

docker run --rm --platform linux/amd64 \
    -v "$PWD/repos:/workspace" \
    maldonado-eclipse
```

`/workspace` 直下のディレクトリが Eclipse の Java プロジェクトとして
自動登録され、10プロジェクトの抽出とフィルタが順に実行されます。
`repos/` は `./setup_repos.sh` で用意してください。

特定のプロジェクトだけ実行する場合:

```bash
docker run --rm --platform linux/amd64 \
    -e JAVA_TOOL_OPTIONS=-DonlyProject=jEdit-4.2 \
    -v "$PWD/repos:/workspace" \
    maldonado-eclipse
```

## 結果の取り出し

`processed_comment` と `comment_class` を結合して CSV にします。

```bash
docker run -d --name maldonado-run --platform linux/amd64 \
    --entrypoint sleep \
    -v "$PWD/repos:/workspace" \
    maldonado-eclipse infinity

docker exec maldonado-run sh -c "PGPASSWORD='' psql -h 127.0.0.1 \
    -U evermal -d comment_classification -c \"\\copy ( \
    select c.projectname, c.filename, c.classname, p.location, \
           p.startline, p.endline, p.commenttext, p.type \
    from processed_comment p join comment_class c on p.commentclassid=c.id \
    order by c.projectname, c.filename, p.startline, p.endline) \
    to '/tmp/comments.csv' csv header\""

docker cp maldonado-run:/tmp/comments.csv data/legacy_tool_comments.csv
python3 docker_eclipse/compare_with_dataset.py
```

## 結果

全10プロジェクトを実行した結果です。`all` はプロジェクト内の全 Java
ファイル、`dataset files` は `data/comment_locations_all.csv` に現れる
ファイルだけに限定した件数です。

| プロジェクト | all | dataset files | データセット | 差（all） | 差（dataset files） |
|---|---:|---:|---:|---:|---:|
| apache-ant-1.7.0 | 4,399 | 4,249 | 4,098 | +7.35% | +3.68% |
| apache-jmeter-2.10 | 8,163 | 8,095 | 8,057 | +1.32% | +0.47% |
| argouml | 9,857 | 9,676 | 9,452 | +4.28% | +2.37% |
| columba-1.4-src | 7,668 | 6,462 | 6,468 | +18.55% | -0.09% |
| emf-2.4.1 | 7,899 | 4,409 | 4,390 | +79.93% | +0.43% |
| hibernate-3.3.2.GA | 4,369 | 2,959 | 2,968 | +47.20% | -0.30% |
| jEdit-4.2 | 10,317 | 10,308 | 10,322 | -0.05% | -0.14% |
| jfreechart-1.0.19 | 4,433 | 4,429 | 4,408 | +0.57% | +0.48% |
| jruby-1.4.0 | 4,925 | 4,907 | 4,897 | +0.57% | +0.20% |
| sql12 | 7,332 | 7,306 | 7,215 | +1.62% | +1.26% |
| **合計** | **69,362** | **62,800** | **62,275** | **+11.38%** | **+0.84%** |

- 全ファイルを対象にすると、データセットより 11.4% 多くなります。
  emf、hibernate、columba では plugins / tests / examples も解析されるため、
  差が大きくなります。
- データセットのファイル集合に限定すると +0.84% まで縮まります。
- 空白正規化した本文の一致（dataset files）は recall 99.82%、
  precision 98.94% です。
- jEdit は全ファイルでもデータセットとほぼ一致します（10,317 対 10,322）。

## 変更点

`patches/Application.java` は上流の `maldonado/eclipse.commandline` に
次の変更を加えたものです。

- `processOpenJavaProjects(root, true, true, false)` でコメント抽出を有効化
- `/workspace` のディレクトリを Java プロジェクトとして自動登録
- `.classpath` が無いプロジェクトだけを登録
- `-DonlyProject=<name>` で対象プロジェクトを限定
- ソースルートがプロジェクト直下になる場合に `project.getFullPath()` を使う

`patches/ASTReader.java` と `patches/AbstractMethodFragment.java` は
JDeodorant 5.0.22 のバインディング未解決による NPE を避けるための
null チェックと、コメント抽出に不要なメソッド本体の生成のスキップです。

上流:

- <https://github.com/maldonado/eclipse.commandline>
- <https://github.com/maldonado/jdeodorant>
- <https://archive.eclipse.org/eclipse/downloads/drops4/R-4.4.2-201502041700/>

## 注意

- `jars/` はビルド済みです。再ビルドする場合は上流を clone し、
  `patches/` の3ファイルを置き換えて `javac --release 8` でコンパイルします。
- Eclipse 4.4.2 は GTK2 を前提とするため、Ubuntu 20.04 の GTK2 を
  インストールしています。
- x86_64 エミュレーションで JVM が SIGILL になる場合は、Colima の
  VZ + Rosetta プロファイルを使ってください。
