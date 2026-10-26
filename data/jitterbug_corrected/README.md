# Jitterbug 修正版データセット

Yu らによる Maldonado データセットの修正版。

- 取得元: <https://github.com/ai-se/tech-debt/tree/master/new_data/corrected>
  （リポジトリは `ai-se/Jitterbug`）
- 追加日: 2020-02-09（コミット `9f98ce5`）
- 取得日: 2026-10-26
- ファイル: プロジェクトごとに1つ、計10ファイル
- 列: `ID, projectname, classification, Abstract, label`（`label` は `yes` / `no`）
- 行数: 62,275、`label=yes` は 4,497

## `maldonado_corrected.csv` との関係

- 行順・行数は一致（62,275行）
- `satd=1` と `label=yes` の不一致は 0 件
- `comment_text` と `Abstract` は空白正規化後で 8 件のみ差異（文字コードと改行に由来）

Maldonado の原データで `WITHOUT_CLASSIFICATION` だった 426 件を SATD に修正したもので、
`maldonado_corrected.csv` の `satd` 列はこの修正版と同じ内容になっている。

## 出典

Z. Yu, F. Fahid, H. Tu, T. Menzies, "Identifying Self-Admitted Technical Debts with Jitterbug:
A Two-Step Approach," IEEE TSE, 2022.
