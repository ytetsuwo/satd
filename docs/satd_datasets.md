# SATD データセット一覧

最終更新: 2026-10-26

## はじめに

- 対象は Self-Admitted Technical Debt（SATD）の研究用データセットです。
- Maldonado et al.（TSE 2017）のデータセット（10プロジェクト、62,566コメント、修正版の SATD は4,497件）は、本リポジトリの基準データとして先頭に置いています。
- SATD データセットにはコードコメント、コミットメッセージ、Issue、Pull Request、削除・返済履歴など、複数の種類があります。
- 公開状況は **○（公開） / △（一部公開・要確認） / −（非公開）** で示します。
- 「位置情報」とはファイルパスや行番号など、コメントの位置を再特定するために使える情報の有無を指します。
- 同じ由来のデータを再ラベル付けした派生版が多いため、学習・評価に使うときは系譜（Maldonado 由来か）を確認してください。

## データセット一覧

| データセット | 年 | 対象 | 規模 | 位置情報 | 公開 | 主な引用論文（代表例） |
|---|---|---|---|---|---|---|
| Maldonado et al. | 2017 | Apache 10プロジェクト | 62,566コメント / SATD 4,497件（修正版） | − | ○ | Huang et al. (2017) / Ren et al. (2019) |
| Potdar & Shihab | 2014 | Eclipse、Chromium OS、ArgoUML、Apache httpd | 101,762コメント / 62パターン | △ | △ | Maldonado et al. (2017) / Huang et al. (2017) |
| Bavota & Russo | 2016 | Java 159プロジェクト | 600Kコミット / 2Bコメント / 273 SATD | − | △ | Maldonado et al. (2017) / Huang et al. (2017) |
| Wehaibi et al. | 2016 | オープンソース5プロジェクト | SATD と変更・欠陥の対応 | △ | −/△ | Maldonado et al. (2017) / Huang et al. (2017) |
| Zampetti et al. | 2018 | Java 5プロジェクト | メソッド単位の削除事例 | ○ | △ | Zampetti et al. (2021) / Li et al. (2023) |
| Fucci et al. | 2020 | Java 5プロジェクト | SATD の導入者・所有権 | △ | ○ | Zampetti et al. (2021) / Fucci et al. (2021) |
| Li et al.（Issue） | 2022 | Apache / Google 7プロジェクト | 4,200 Issue / 3,277 SATD セクション | − | ○ | Li et al. (2023) / Sheikhaei et al. (2024) |
| Li et al.（4 sources） | 2023 | Apache 103プロジェクト | 5,000コミット + 5,000 PR / 95,455 NL サンプル | − | ○ | Sheikhaei et al. (2024) / Biazotto et al. (2023) |
| CppSATD | 2025 | C++ 5リポジトリ | 531K+コメント / 13,069 SATD | ○ | ○ | Topalidi (2026) / Melin et al. (2026) |
| Scientific Software | 2024/2025 | 科学ソフト9プロジェクト | 28,680コメント | △ | ○ | — |
| R Packages | 2021/2022 | R 503パッケージ | 146,583コメント | △ | ○ | Sharma et al. (2022) / Ebrahimi et al. (2023) |
| ML SATD | 2022/2023 | ML 2,641リポジトリ / ML・非ML 各318プロジェクト | 68,820 SATD | △ | ○ | Sheikhaei et al. (2024) / Pepe et al. (2024) |
| Tesoro | 2026 | Java 974リポジトリ | 4,981コメント / 1,255関数 | ○ | ○ | Yu et al. (2026) |
| Test Code SATD | 2026 | テストコード | 615 SATD / 14カテゴリ | △ | △ | Islam et al. (2026) / Neto et al. (2026) |
| LLM Software | 2026 | LLM 159 / ML 159 / 非ML 159リポジトリ | 500万+コメントイベント | △ | ○ | — |
| Jitterbug corrected | 2022 | Maldonado の10プロジェクト | 62,275コメント / 4,497 SATD | − | ○ | Wang et al. (2020) / Sheikhaei et al. (2024) |
| MSR16 removal | — | Ant 1.7.0、JMeter 2.10、JRuby 1.4.0 | 1,127レコード | ○ | ○ | Yan et al. (2018) / Digkas et al. (2018) |

TDD（2019）は SATD コメントのデータセットではないため、この表には含めていません。Issue / PR / コードレビュー中の SATD は第4.2節を参照してください。

主な引用論文（代表例）は、OpenAlex の引用関係から選んだものです。引用はデータセットの利用を保証するものではありません。全件は [引用論文一覧](satd_dataset_citations.md) を参照してください。

## 0. 基準データセット: Maldonado et al. (2017)

- 論文: E. da S. Maldonado, E. Shihab, N. Tsantalis, "Using Natural Language Processing to Automatically Detect Self-Admitted Technical Debt," IEEE TSE, 43(11), pp. 1044–1062, 2017.
- 対象: 10の Apache プロジェクト（Ant、JMeter、ArgoUML、Columba、JFreeChart、Hibernate、JEdit、JRuby、SQuirreL、EMF）。
- 規模: 62,566コメント。SATD は原データで4,071件、修正版で4,497件。
- ラベル: SATD / 非 SATD、SATD タイプ（Code/Design、Requirement、Defect、Test、Documentation）。
- 公開: ○（GitHub）。
- 位置情報: −（プロジェクト名とコメントテキストのみで、ファイル名や行番号はありません）。
- 特徴: SATD 検出の事実上の標準ベンチマークです。本リポジトリの `maldonado_corrected.csv` もこのデータを基にしています。
- データ: <https://github.com/maldonado/tse.satd.data>

## 1. 定番・最初期のデータセット

### 1.1 Potdar & Shihab (2014)

- 論文: A. Potdar, E. Shihab, "An Exploratory Study on Self-Admitted Technical Debt," ICSME 2014, pp. 91–100.
- 対象: Eclipse、Chromium OS、ArgoUML、Apache httpd の4プロジェクト。
- 規模: 101,762コメント、62の SATD パターン。
- ラベル: SATD / 非 SATD（パターンと手動分類）。
- 公開: △（62パターンとデータ配布ページ。現在の取得可否は要確認）。
- 位置情報: △（ファイル単位。行番号は限定的）。
- 特徴: SATD 研究の出発点となったデータセットです。最初のベンチマークとして引用されますが、現在の検出研究では Maldonado が主に使われます。
- 配布ページ: <https://users.encs.concordia.ca/~eshihab/data/ICSME2014/satd.html>（要確認）

### 1.2 Bavota & Russo (2016)

- 論文: G. Bavota, B. Russo, "A Large-Scale Empirical Study on Self-Admitted Technical Debt," MSR 2016, pp. 315–326.
- 対象: 159の Java プロジェクト。
- 規模: 600Kコミット、2Bコメント、273件の手動ラベル付き SATD。
- ラベル: SATD / 非 SATD、SATD タイプ。
- 公開: △（Replication Package。大規模で、再構築が必要です）。
- 位置情報: −（コミット・コメント単位が中心）。
- 特徴: SATD の普及・進化・品質への影響を大規模に分析した代表的な研究です。Maldonado 以前の大規模ベースラインにあたります。
- DOI: <https://doi.org/10.1145/2901739.2901742>

### 1.3 Wehaibi et al. (2016)

- 論文: S. Wehaibi, E. Shihab, L. Guerrouj, "Examining the Impact of Self-Admitted Technical Debt on Software Quality," SANER 2016, pp. 179–188.
- 対象: 5つのオープンソースプロジェクト。
- 規模: SATD コメントを、その後の変更や欠陥に対応付けています。
- 公開: −/△（論文のみ。データ配布は限定的です）。
- 位置情報: △（SATD と変更の対応）。
- 特徴: SATD が品質・変更コストに与える影響を調べた初期研究です。検出用ベンチマークというより、影響分析向けです。

### 1.4 Zampetti et al. (2018)

- 論文: F. Zampetti, A. Serebrenik, M. Di Penta, "Was Self-Admitted Technical Debt Removal a Real Removal? An In-Depth Perspective," MSR 2018, pp. 526–536.
- 対象: 5つの Java プロジェクト。
- 規模: メソッドレベルの SATD 削除事例。SATD の20–50%が削除されることを報告しています。
- 公開: △（Replication Package）。
- 位置情報: ○（メソッド・行レベル）。
- 特徴: SATD の「削除」を詳しく分析し、6種類の削除パターンを提示しています。返済・削除研究の定番です。
- DOI: <https://doi.org/10.1145/3196398.3196423>

### 1.5 Fucci et al. (2020)

- 論文: G. Fucci, F. Zampetti, A. Serebrenik, M. Di Penta, "Who (Self) Admits Technical Debt?" ICSME 2020, pp. 672–676.
- 対象: 5つの Java プロジェクト。
- 規模: SATD コメントを、その導入者やコード所有権に対応付けています。
- 公開: ○（Zenodo）。
- 位置情報: △（コメントとコードの対応）。
- 特徴: 「誰が SATD を書いたか」を分析しています。Maldonado のデータをキュレーションした派生版です。
- DOI: <https://doi.org/10.5281/zenodo.3984829>

## 2. 大規模・多言語・新しいデータセット

### 2.1 Li et al. (2022): Issue Tracking Systems

- 論文: Y. Li, M. Soliman, P. Avgeriou, "Identifying self-admitted technical debt in issue tracking systems using machine learning," Empirical Software Engineering, 27(131), 2022.
- 対象: Apache と Google の7プロジェクト。
- 規模: 4,200 Issue、23,180 Issue セクション、3,277 SATD セクション。
- ラベル: SATD / 非 SATD、SATD タイプ。
- 公開: ○（GitHub）。
- 位置情報: −（テキスト単位）。
- 特徴: コードコメント以外の SATD を扱う代表例です。Issue トラッカー版のベンチマークにあたります。
- DOI: <https://doi.org/10.1007/s10664-022-10128-3>
- データ: <https://github.com/yikun-li/satd-issue-tracker-data>

### 2.2 Li et al. (2023): Four Sources

- 論文: Y. Li, M. Soliman, P. Avgeriou, "Automatic identification of self-admitted technical debt from four different sources," Empirical Software Engineering, 28(65), 2023.
- 対象: 103の Apache プロジェクト。
- 規模: 5,000コミットメッセージと5,000 Pull Request セクションを手動でラベル付けしています。背景データとして23.7Mコメント、1.3Mコミット、0.3M PR、0.6M Issue を含みます。NL サンプルは95,455件です。
- ラベル: SATD / 非 SATD、SATD タイプ。
- 公開: ○（GitHub）。
- 位置情報: −（テキスト単位）。
- 特徴: コードコメント・コミット・PR・Issue の4ソースを横断できる、現在もっとも使いやすい大規模データセットの一つです。
- DOI: <https://doi.org/10.1007/s10664-023-10297-9>
- データ: <https://github.com/yikun-li/satd-different-sources-data>

### 2.3 CppSATD (2025)

- 論文: P. Pham, M. Sridharan, M. Esposito, V. Lenarduzzi, "C++ Self-Admitted Technical Debt Dataset (CppSATD)," 2025（arXiv:2505.01136）。
- 対象: 5つの C++ リポジトリ。
- 規模: 531,000以上のコメント、13,069件の手動分類 SATD。周辺コード（文脈）付き。
- ラベル: SATD / 非 SATD、SATD タイプ（Design/Code、Requirement、Defect、Test、Documentation）。
- 公開: ○（Zenodo、約5.4GB）。
- 位置情報: ○（ファイル・コード文脈付き）。
- 特徴: C++ に特化した最大級のデータセットです。コード文脈を含むため、位置特定や文脈利用の研究に向きます。
- DOI: <https://doi.org/10.5281/zenodo.15562944>

### 2.4 Scientific Software (2024/2025)

- 論文: "Self-Admitted Technical Debt in Scientific Software"（Zenodo 版は2024年7月）。
- 対象: Astropy、Biopython、CESM、Firedrake、MOOSE、GROMACS、Elmer、Athena、Root の9プロジェクト。
- 規模: 28,680コメント。
- ラベル: SATD / 非 SATD、Code/Design、Scientific Debt など。
- 公開: ○（Zenodo、15MB）。
- 位置情報: △（ファイルパス、導入・削除日。行番号は要確認）。
- 特徴: 科学ソフトウェア特有の「Scientific Debt」を追加した専門データセットです。
- DOI: <https://doi.org/10.5281/zenodo.13174322>

### 2.5 R Packages (2021/2022)

- 論文: M. Vidoni, "Self-Admitted Technical Debt in R Packages: An Exploratory Study," MSR 2021. R. Sharma et al., "Self-admitted technical debt in R: detection and causes," Automated Software Engineering, 29(53), 2022.
- 対象: 503の R パッケージ。
- 規模: 146,583コメント。
- ラベル: SATD / 非 SATD、SATD タイプ。
- 公開: ○（Zenodo、2.3GB）。
- 位置情報: △（コメント単位。ファイル情報は要確認）。
- 特徴: R 言語に特化したデータセットです。SATD はコメントの約3%という報告があります。
- DOI: <https://doi.org/10.5281/zenodo.4558220>

### 2.6 ML SATD (2022/2023)

- 論文: D. O'Brien et al., "23 Shades of Self-Admitted Technical Debt: An Empirical Study on Machine Learning Software," ESEC/FSE 2022. A. Bhatia et al., "An Empirical Study of Self-Admitted Technical Debt in Machine Learning Software," 2023（arXiv:2311.12019）。
- 対象: O'Brien らは2,641の ML リポジトリ。Bhatia らは318の ML プロジェクトと318の非 ML プロジェクト。
- 規模: 68,820 SATD（O'Brien ら）。Bhatia らのデータは ML / 非 ML の比較用です。
- ラベル: SATD / 非 SATD、ML 特有のタイプ。
- 公開: ○（GitHub の Replication Package）。
- 位置情報: △（コメント単位。ファイル・履歴情報は一部）。
- 特徴: ML ソフトウェアにおける SATD の分類・導入・除去を扱っています。Python を中心としています。
- データ: <https://github.com/Aaditya-Bhatia/Self-Admitted-Technical-Debt-in-Machine-Learning-Software>

### 2.7 Tesoro (2026)

- 論文: N. Le Hai et al., "Detection of Technical Debt in Java Source Code," ACM TOSEM, 2026.
- 対象: 974の Java リポジトリ。
- 規模: Tesoro_comment は4,981件のコメントサンプル、Tesoro_code は1,255件の Java 関数。
- ラベル: SATD / 非 SATD、TD タイプ。コード側のラベルもあり。
- 公開: ○（GitHub）。
- 位置情報: ○（関数・コード文脈付き）。
- 特徴: コメントだけでなくコード自体にも TD ラベルを付けた新しいデータセットです。位置特定・コード文脈の研究に向きます。
- DOI: <https://doi.org/10.1145/3801745>
- データ: <https://github.com/NamCyan/tesoro>

### 2.8 Test Code SATD (2026)

- 論文: I. Nakamura, Y. Kashiwa, B. Lin, H. Iida, "Understanding Self-Admitted Technical Debt in Test Code: An Empirical Study," ACM TOSEM, 2026.
- 対象: テストコード。
- 規模: 615件の SATD コメント、14カテゴリ。
- 公開: △（Replication Package の有無は要確認）。
- 位置情報: △。
- 特徴: テストコードに限定して SATD を分類したデータセットです。通常のコードコメントとは異なる種類の負債を扱います。
- DOI: <https://doi.org/10.1145/3786791>

### 2.9 LLM Software (2026)

- 論文: "Self-Admitted Technical Debt in LLM Software: An Empirical Comparison with ML and Non-ML Software," 2026（arXiv:2601.06266）。
- 対象: 159の LLM リポジトリ（比較用に ML 159、非 ML 159）。
- 規模: 500万以上のコメントイベントを分析しています。
- 公開: ○（GitHub の Replication Package）。
- 位置情報: △（コメント・履歴単位）。
- 特徴: LLM 時代の SATD を ML・非 ML と比較しています。最新のドメイン特化データセットです。
- データ: <https://github.com/Niruthiha/satd-llm-ml-nonml>

## 3. Maldonado 系の派生（比較用）

Maldonado を修正・拡張した事実上の標準ベンチマークなので、別枠で載せます。

### 3.1 Jitterbug corrected (2022)

- 論文: Z. Yu, F. Fahid, H. Tu, T. Menzies, "Identifying Self-Admitted Technical Debts with Jitterbug: A Two-Step Approach," IEEE TSE, 2022.
- 内容: Maldonado の10プロジェクト・62,275コメントのラベルを修正しています。SATD は4,497件です。
- 公開: ○（GitHub）。
- 位置情報: −（コメントテキストとプロジェクト名。行番号なし）。
- 特徴: Maldonado のラベルノイズを修正した版です。現在の検出研究では、この修正版を「Maldonado」として使うことが多いです。
- データ: <https://github.com/ai-se/tech-debt/tree/master/new_data/corrected>

### 3.2 MSR16 removal（位置情報付き）

- 論文: E. da S. Maldonado et al., "An Empirical Study on the Removal of Self-Admitted Technical Debt"（Maldonado らの削除研究）。
- 内容: Apache Ant 1.7.0、Apache JMeter 2.10、JRuby 1.4.0 の3プロジェクトについて、SATD コメントのファイル名・行番号を提供しています。1,127件のレコードです。
- 公開: ○（GitHub）。
- 位置情報: ○（`comment_start_line` / `comment_end_line`）。
- 特徴: コメント位置の正解データとして貴重です。本リポジトリの `data/msr16_td_removal/` にも収録済みです。
- データ: <https://github.com/maldonado/msr16_td_removal>

## 4. 隣接データセット

### 4.1 The Technical Debt Dataset（TDD, 2019）

- 論文: V. Lenarduzzi, N. Saarimäki, D. Taibi, "The Technical Debt Dataset," PROMISE 2019.
- 内容: 31–32の Apache プロジェクトについて、SonarQube の TD 項目、コードスメル、コミット、Jira Issue、SZZ の欠陥情報を収録しています。
- 公開: ○（GitHub、SQLite）。
- 特徴: SATD コメントのデータセットではありませんが、TD の時系列・修復分析用の定番データセットです。SATD と組み合わせる研究にも使えます。
- データ: <https://github.com/clowee/The-Technical-Debt-Dataset>

### 4.2 Issue / PR / コードレビュー中の SATD

- Xavier et al., "Beyond the Code: Mining Self-Admitted Technical Debt in Issue Tracker Systems," MSR 2020: 5システム（GitLab、VS Code など）の286件の SATD-I。
- Karmakar et al., "An Experience Report on Technical Debt in Pull Requests," ESEM 2022: Spark、Kafka、React の PR コメント。
- Kashiwa et al., "An empirical study on self-admitted technical debt in modern code review," 2022: OpenStack と Qt の375件の SATD コメント。
- これらは小規模で専門的ですが、「コードコメント以外の SATD」を評価したいときに使えます。

## 5. 用途別の選び方

| 目的 | おすすめ | 理由 |
|---|---|---|
| 二値分類の標準ベンチマーク | Jitterbug corrected、Potdar & Shihab | 比較論文が多い。Maldonado 系では Jitterbug 版が実質的な標準です |
| 多クラス分類（SATD タイプ） | Maldonado / Jitterbug、CppSATD、Li et al. 2023 | タイプ付きのラベルが揃っています |
| コード文脈・位置特定 | MSR16 removal、Zampetti et al. 2018、Tesoro、CppSATD | ファイル・行・関数・周辺コードの情報があります |
| クロスアーティファクト | Li et al. 2022（Issue）、Li et al. 2023（4ソース） | コメント以外の SATD を大規模に扱える |
| クロス言語 | CppSATD（C++）、R Packages（R）、ML SATD（Python）、Tesoro（Java） | 言語ごとの特性を比較できる |
| ドメイン特化 | Scientific Software、ML SATD、LLM Software、Test Code SATD | 科学・ML・LLM・テストの固有性を分析できる |
| TD の時系列・修復 | TDD、Zampetti et al. 2018 | コミット・Issue・削除履歴が充実しています |

## 6. 注意点

1. **派生関係**: Jitterbug、MSR16 removal、Fucci et al. は Maldonado 由来です。「独立したデータセット」として扱うと、訓練データとテストデータの間で重複が起きます。
2. **ラベル定義の違い**: 同じ「SATD」でも、コードコメントだけを対象にするか、Issue や PR を含むかで範囲が異なります。比較するときはラベル定義を揃えてください。
3. **クラス不均衡**: SATD はコメント全体の数%程度です。Accuracy だけでなく、F1・Precision・Recall を確認してください。
4. **位置情報の有無**: 検出用データの多くはテキスト単位で、行番号がありません。位置特定の評価には MSR16 removal、Zampetti、Tesoro、CppSATD などを使う必要があります。
5. **スナップショット**: リポジトリの現在のコードと、データセット作成時のコードは一致しないことがあります。コミットハッシュを確認してください。
6. **ライセンス**: Zenodo の CC-BY と、GitHub のリポジトリライセンスは異なります。再配布時は確認してください。

## 7. 参考文献（主要なもの）

- A. Potdar, E. Shihab, "An Exploratory Study on Self-Admitted Technical Debt," ICSME 2014.
- G. Bavota, B. Russo, "A Large-Scale Empirical Study on Self-Admitted Technical Debt," MSR 2016.
- S. Wehaibi, E. Shihab, L. Guerrouj, "Examining the Impact of Self-Admitted Technical Debt on Software Quality," SANER 2016.
- E. da S. Maldonado, E. Shihab, N. Tsantalis, "Using Natural Language Processing to Automatically Detect Self-Admitted Technical Debt," IEEE TSE, 43(11), 2017.
- F. Zampetti, A. Serebrenik, M. Di Penta, "Was Self-Admitted Technical Debt Removal a Real Removal? An In-Depth Perspective," MSR 2018.
- G. Fucci, F. Zampetti, A. Serebrenik, M. Di Penta, "Who (Self) Admits Technical Debt?" ICSME 2020.
- Y. Li, M. Soliman, P. Avgeriou, "Identifying self-admitted technical debt in issue tracking systems using machine learning," EMSE, 27(131), 2022.
- Y. Li, M. Soliman, P. Avgeriou, "Automatic identification of self-admitted technical debt from four different sources," EMSE, 28(65), 2023.
- Z. Yu, F. Fahid, H. Tu, T. Menzies, "Identifying Self-Admitted Technical Debts with Jitterbug: A Two-Step Approach," IEEE TSE, 2022.
- P. Pham, M. Sridharan, M. Esposito, V. Lenarduzzi, "C++ Self-Admitted Technical Debt Dataset (CppSATD)," 2025.
- N. Le Hai et al., "Detection of Technical Debt in Java Source Code," ACM TOSEM, 2026.
- D. O'Brien et al., "23 Shades of Self-Admitted Technical Debt: An Empirical Study on Machine Learning Software," ESEC/FSE 2022.
- A. Bhatia et al., "An Empirical Study of Self-Admitted Technical Debt in Machine Learning Software," 2023.
- I. Nakamura, Y. Kashiwa, B. Lin, H. Iida, "Understanding Self-Admitted Technical Debt in Test Code: An Empirical Study," ACM TOSEM, 2026.
- V. Lenarduzzi, N. Saarimäki, D. Taibi, "The Technical Debt Dataset," PROMISE 2019.
