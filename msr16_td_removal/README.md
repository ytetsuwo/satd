# Maldonado らの削除研究データ（位置情報付き）

Maldonado 自身の後続リポジトリ [maldonado/msr16_td_removal](https://github.com/maldonado/msr16_td_removal) の
`datasets/CSV/` から取得した。`maldonado_corrected.csv` の SATD コメントのうち、
3プロジェクト（apache-ant 1.7.0、apache-jmeter 2.10、jruby 1.4.0）については
ファイル名と行番号が分かる。

## ファイル

| ファイル | 内容 |
|---|---|
| `technical_debt_summary.csv` | 上流の元ファイル（無改変）。1,127行 |
| `file_directory_per_version.csv` | 上流の元ファイル（無改変）。パス解決用。32,322行 |
| `satd_locations.csv` | 上記2ファイルを結合し、相対パスを付与した派生ファイル。1,127行 |

取得日: 2026-10-26

## satd_locations.csv

`technical_debt_summary.csv` の各行に、`file_directory_per_version.csv` を
`(project_name, version_name, file_name)` で結合して `file_path`（`repository_directory`）を付けたもの。

- 1,127行 = `maldonado_corrected.csv` の `satd_orig=1` のうち、この3プロジェクト分の全行
  （apache-ant 131、apache-jmeter 374、jruby 622）
- コメント本文は `maldonado_corrected.csv` とユニーク904件すべて一致
- 結合は 1,127/1,127 成功。ファイル名だけでは一意にならない5行は、
  リポジトリ内の該当行と本文を照合してパスを決定した

列:

| 列 | 内容 |
|---|---|
| `project_name` | 上流でのプロジェクト名（`apache-ant` など） |
| `version_name` | リリース版（`ANT_170`、`v2_10`、`1.4.0`） |
| `version_hash` | その版のコミット |
| `file_path` | リポジトリからの相対パス |
| `file_name` | ファイル名（上流の値） |
| `comment_location` | `CLASS` / `METHOD` / `INLINE` |
| `function_signature` | 所属メソッド（不明なら空） |
| `comment_start_line` / `comment_end_line` | リリース版ファイル上の行番号 |
| `comment_classification` | DESIGN / DEFECT / IMPLEMENTATION / TEST / DOCUMENTATION |
| `comment_text` | コメント本文 |

## 注意

- 対象は SATD コメントのみ。`WITHOUT_CLASSIFICATION` の58,204行は含まない。
- 対象プロジェクトは10中3つ。argouml、columba、emf、hibernate、jedit、jfreechart、sql12 は無い。
- 行番号は各リリース版のファイル基準。行内コメントでは `comment_start_line` の行に
  コメント前のコードが含まれる。
- コメント本文は、間にコードを挟む複数のコメント片を1つに連結している場合がある
  （jmeter で26/374行）。その場合、行範囲の文字列と本文は完全一致しない。
- 行番号の照合: apache-ant は 131/131 行、apache-jmeter は 348/374 行で
  本文が該当行に含まれることを確認（残りは上記の連結ケース）。
