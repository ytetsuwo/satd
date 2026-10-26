#!/usr/bin/env bash
#
# repos/ を Maldonado データセットの各プロジェクトの版に復元する。
#
#   ./setup_repos.sh                # すべて取得（約 1.9GB）
#   ./setup_repos.sh jruby-1.4.0    # 指定したものだけ
#   REPOS_ROOT=/path ./setup_repos.sh
#   FORCE=1 ./setup_repos.sh        # 既存の複製を消して取り直す
#
# 各リポジトリは全履歴を取得する（git blame に必要）。
# コミットはタグではなく SHA で固定している。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_ROOT="${REPOS_ROOT:-$ROOT/repos}"
FORCE="${FORCE:-0}"

# project_name|clone URL|commit|目安のref
PROJECTS=(
  "apache-ant-1.7.0|https://github.com/apache/ant.git|6bfe7759b0d7662f764a6efd97436b48aa74da2a|ANT_170"
  "apache-jmeter-2.10|https://github.com/apache/jmeter.git|c6184b5e7ffeb56364ed43074504f9539a3b9f01|v2_10"
  "argouml|https://github.com/argouml-tigris-org/argouml.git|809df978f10c3fde97d238b57abca8a7e5149a44|VERSION_0_35_1"
  "columba-1.4-src|https://github.com/RobertHSchmidt/columba.git|c2ab39e1eb4acc84ae0f85f7dcd51f973f110a2e|master"
  "emf-2.4.1|https://github.com/eclipse-emf/org.eclipse.emf.git|dae4755d3993f95322a07ab661e63f9d061a4217|R2_4_maintenance"
  "hibernate-distribution-3.3.2.GA|https://github.com/hibernate/hibernate-orm.git|6b66b08b88afb4c7219c603964e07be8df85a2ea|3.3"
  "jEdit-4.2|https://github.com/jEdit-editor/jEdit.git|9825b3ed1bc3a0f5a561df920e0ed18fbe29d3ff|v4.2final"
  "jfreechart-1.0.19|https://github.com/jfree/jfreechart.git|b3f5f21ba0fe32a8f7eccb6760a79df30628be3e|v1.0.19"
  "jruby-1.4.0|https://github.com/jruby/jruby.git|69fbfa336591fb1a65d4000556b3fedda30baf8f|1.4.0"
  "sql12|https://github.com/squirrel-sql-client/squirrel-sql-code.git|e619485ea0c760ef5083c34e931632440dd17f00|squirrel_3_0_branch"
)

selected=("$@")

is_selected() {
  ((${#selected[@]} == 0)) && return 0
  local name=$1 want
  for want in "${selected[@]}"; do
    [[ $name == "$want" ]] && return 0
  done
  return 1
}

mkdir -p "$REPOS_ROOT"

failed=()
matched=0

for spec in "${PROJECTS[@]}"; do
  IFS='|' read -r name url commit ref <<<"$spec"
  is_selected "$name" || continue
  matched=$((matched + 1))

  dest="$REPOS_ROOT/$name"
  echo "==> $name ($ref)"
  echo "    $url"
  echo "    $commit"

  if [[ -e "$dest" && $FORCE == 1 ]]; then
    echo "    FORCE=1: 既存の複製を削除します"
    rm -rf "$dest"
  fi

  if [[ -d "$dest/.git" ]]; then
    if [[ "$(git -C "$dest" rev-parse HEAD)" == "$commit" ]]; then
      echo "    取得済みのためスキップ"
      continue
    fi
    echo "    既存の複製を利用します（FORCE=1 で取り直せます）"
  else
    if [[ -e "$dest" ]]; then
      echo "    エラー: $dest は Git リポジトリではありません" >&2
      failed+=("$name")
      continue
    fi
    echo "    clone 中..."
    if ! git clone --quiet "$url" "$dest"; then
      echo "    エラー: clone に失敗しました" >&2
      failed+=("$name")
      continue
    fi
  fi

  if ! git -C "$dest" cat-file -e "$commit^{commit}" 2>/dev/null; then
    echo "    エラー: コミット $commit が見つかりません" >&2
    failed+=("$name")
    continue
  fi

  if ! git -C "$dest" -c advice.detachedHead=false checkout --quiet --detach "$commit"; then
    echo "    エラー: checkout に失敗しました" >&2
    failed+=("$name")
    continue
  fi

  actual="$(git -C "$dest" rev-parse HEAD)"
  if [[ "$actual" != "$commit" ]]; then
    echo "    エラー: HEAD が $actual になっています" >&2
    failed+=("$name")
    continue
  fi

  echo "    OK: $(git -C "$dest" log -1 --format='%h %ad %s' --date=short)"
done

echo
if ((matched == 0)); then
  echo "エラー: 該当するプロジェクトがありません: ${selected[*]}" >&2
  echo "利用可能: $(printf '%s ' "${PROJECTS[@]%%|*}")" >&2
  exit 1
fi
if ((${#failed[@]})); then
  echo "失敗: ${failed[*]}" >&2
  exit 1
fi
echo "完了: $REPOS_ROOT"
du -sh "$REPOS_ROOT" 2>/dev/null || true
