# 03_DATASET_SYSTEM.md

## Purpose

This document defines how LASI handles datasets.

The dataset system is responsible for dataset ingestion, manifests, validation, characterization, versioning, lineage, benchmark roles, comparability, improvement proposals, and dataset portfolio tracking.

It does not define model training, experiment execution, scientist-provider prompts, report templates, or database schemas in detail. Those belong in separate documents.

The dataset system answers:

> What data do we have, what does it contain, how has it changed, and can results across versions be compared?

---

## Core Idea

In LASI, datasets are not passive inputs.

Datasets are research assets.

Every dataset version should be treated as an experimental object with identity, lineage, characterization, quality profile, and outcome history.

A model result is only meaningful when tied to the dataset version that produced it.

A dataset change is only meaningful when tied to the reason it was made.

---

## Dataset Storage Model

LASI should not store datasets as PyTorch `Dataset` objects.

A PyTorch `Dataset` is a runtime adapter for PyTorch training. It is useful when a tool needs to feed data into a PyTorch `DataLoader`, but it is not a good universal storage format for LASI.

LASI should store datasets as framework-neutral, versioned assets.

The dataset storage model should be layered:

```text
Raw Data Store
↓
Canonical Dataset Store
↓
Dataset Manifest
↓
Metadata Database
↓
Characterization Artifacts
↓
Runtime Adapters
```

Each layer has a different job.

The raw data store preserves the original source export. It should remain untouched so that conversion errors can be traced and corrected later.

The canonical dataset store contains LASI-managed dataset versions in stable, typed, framework-neutral formats such as Parquet, Arrow, CSV, JSONL, NumPy arrays, or sharded files depending on modality and scale.

The dataset manifest describes the samples, labels, file references, metadata, and split assignments.

The metadata database stores dataset identity, version, lineage, characterization summaries, status, comparability, benchmark role, and artifact references.

MLflow or the artifact store stores heavier derived artifacts such as plots, embeddings, cluster outputs, reports, model outputs, and characterization visualizations.

Runtime adapters convert a canonical dataset version into whatever shape a specific tool needs.

---

## Runtime Adapters

Runtime adapters are tool-specific views over a dataset version.

A dataset version should be usable by many tools without changing the underlying dataset.

Examples:

```text
PyTorch Dataset       → neural network training
NumPy arrays          → custom algorithms
Pandas DataFrame      → inspection and reporting
scikit-learn matrix   → classical ML
XGBoost DMatrix       → gradient boosting
FAISS index           → vector search
HDBSCAN input matrix  → clustering
HTML sample grid      → human review
CSV/Parquet export    → external tools
```

This prevents LASI from being locked into one ML framework.

The canonical dataset belongs to LASI.

The adapter belongs to the tool.

For example, a PyTorch tool may request a PyTorch dataset adapter. A clustering tool may request an embedding matrix. A human review tool may request sample cards or an HTML grid. All of those views should point back to the same dataset version.

---

## Framework Neutrality

LASI should remain framework-neutral.

PyTorch may be an important training backend, but it should not define the dataset architecture. Not every useful tool will run through PyTorch, and not every experiment is a neural-network experiment.

The dataset system should support PyTorch, scikit-learn, XGBoost, FAISS, classical statistics, custom geometry algorithms, static reports, and future tools without changing the meaning of a dataset version.

The practical rule is:

> Store datasets in canonical framework-neutral formats. Generate framework-specific adapters at runtime.

---

## MVP Storage Stack

The MVP should not begin with many specialized databases.

A practical Phase 1 stack is:

```text
data/
├── raw/
├── canonical/
├── derived/
└── splits/

SQLite metadata database
MLflow artifact storage
YAML/Pydantic configuration
Tool-specific runtime adapters
```

This gives LASI enough structure to support dataset versioning, characterization, experiment tracking, report generation, and remote execution without creating unnecessary infrastructure.

Vector databases, graph databases, remote object stores, and dataset caching systems can be added later if the workload justifies them.

---

## Vector Indexes and Graph Structures

A vector database may become useful later, but it should not be the primary dataset store.

Vector indexes are derived artifacts for similarity search. They may support nearest-neighbor retrieval, similar-sample search, similar-dataset search, cluster inspection, human-review candidate selection, and prior-case retrieval.

A knowledge graph may also become useful later, but it should not be required for the MVP.

The early system can represent lineage and relationships in a relational database using explicit foreign keys:

```text
dataset_version.parent_version_id
dataset_version.created_because_recommendation_id
experiment.dataset_version_id
project_outcome.project_id
artifact.source_run_id
knowledge_document.source_project_id
```

This gives LASI graph-like traceability without the operational cost of a graph database.

A true graph database should only be considered if lineage, dependency, or relationship queries become painful in the relational model.

---

## Design Principles

### Characterize Before Training

Every dataset version should be characterized before training unless explicitly waived.

The harness should not begin model experiments on a dataset it has not profiled.

Characterization does not need to be perfect, but it should be systematic enough to describe the dataset’s primitives, distributions, clusters, quality issues, coverage gaps, and ambiguity regions.

---

### Version Every Dataset

Datasets should be versioned.

A project should never overwrite a dataset and pretend it is the same asset.

If labels are corrected, data is added, synthetic samples are introduced, classes are merged, or the train/validation split changes, a new dataset version should be created.

---

### Preserve Lineage

Every dataset version should know where it came from.

The system should be able to answer:

- What was the parent dataset?
- Why was this version created?
- What changed?
- Who or what recommended the change?
- Was the change expected to improve something?
- Did it actually help?

---

### Separate Data Change from Model Improvement

A better metric after a dataset update does not automatically mean the model improved.

The task may have changed.

The validation set may have changed.

The label policy may have changed.

The benchmark may no longer be comparable.

LASI should explicitly track comparability across dataset versions.

---

### Treat Benchmarks as Protected Assets

Benchmark datasets should be managed differently from training datasets.

A frozen benchmark should not be casually edited.

If label policy changes, a new benchmark version should be created rather than overwriting the old one.

---

## Dataset Concepts

### Dataset

A dataset is the logical family of data.

Example:

```text
scratch_pointcloud
```

A dataset may have many versions.

---

### Dataset Version

A dataset version is a specific, immutable or effectively immutable snapshot.

Example:

```text
scratch_pointcloud:v0.3.0
```

Every experiment should reference a dataset version, not just a dataset name.

---

### Dataset Manifest

A dataset manifest describes the samples in a dataset version.

It should be machine-readable and validated before use.

For the initial point-cloud scratch classification use case, a manifest should identify each sample, its label, the point-cloud data location, optional features, optional metadata, and split assignment if available.

A practical manifest may be a CSV, Parquet file, or JSONL file.

---

### Dataset Characterization

Dataset characterization is the diagnostic profile of a dataset version.

It describes what the dataset contains before modeling begins.

Characterization includes primitive profiles, distribution summaries, cluster profiles, quality checks, separability measures, coverage gaps, and ambiguous regions.

---

### Dataset Role

A dataset version may serve different roles.

Common roles include:

```text
training
validation
test
frozen_benchmark
stress_test
human_review
synthetic
unlabeled_pretraining
```

The same physical data should not silently change roles without being recorded.

---

## Dataset Manifest

The manifest is the entry point into the dataset system.

For the first LASI use case, the manifest should support binary point-cloud scratch classification.

A minimal manifest should include:

```text
sample_id
label
point_cloud_ref
```

Optional fields may include:

```text
wafer_id
lot_id
tool_id
recipe_id
layer_id
x_location
y_location
defect_width
defect_height
metadata_ref
split
```

The exact point-cloud representation is not settled. Two practical options are:

1. A Parquet file with one row per sample and a serialized point list.
2. A manifest file that references one point-cloud file per sample.

The first option is easier to move as a single dataset artifact. The second option is easier to inspect manually and may scale better when point-cloud files are large.

The MVP should pick one primary format and one optional secondary format. Supporting every possible industrial export format should be deferred.

---

## Dataset Validation

Dataset validation confirms that the manifest and referenced files are usable.

Validation should check that required fields exist, sample IDs are unique, labels are valid, point-cloud references exist, splits are valid if provided, labels match the declared label schema, and no obvious file corruption exists.

For point-cloud data, validation should also check that each sample has a valid coordinate structure and that point counts fall within reasonable bounds.

Validation does not decide whether the dataset is good. It decides whether the dataset is structurally usable.

A dataset that passes validation may still be too small, too ambiguous, imbalanced, duplicated, or poorly covered. Those are characterization findings, not validation failures.

---

## Dataset Characterization

Characterization is mandatory before training unless explicitly waived.

The purpose is to answer:

> What is in this dataset?

For point-cloud scratch classification, characterization should attempt to describe the primitives and structures relevant to scratch detection.

### Primitive Profile

The primitive profile describes the basic units of the dataset.

For point-cloud scratch data, primitives may include points, local neighborhoods, connected components, arcs, curve segments, sparse clusters, dense clusters, defect groups, size features, density regions, curvature segments, and aspect-ratio indicators.

The system should not assume that every primitive is available from the raw data. Some primitives may need to be derived.

### Distribution Profile

The distribution profile describes dataset-wide and class-specific distributions.

Examples include point-count distribution, spatial extent distribution, density distribution, curvature distribution, arc-length distribution, defect-size distribution, wafer-location distribution, and metadata distribution.

The goal is to identify whether the dataset is dominated by a narrow kind of sample or whether it covers the expected operational range.

### Cluster Profile

The cluster profile describes natural groupings in the dataset.

Clustering may be performed on engineered features, learned embeddings, or both.

The system should record cluster count, cluster size, cluster purity, low-purity clusters, noise fraction, dominant labels, and representative examples.

Low-purity clusters are especially important because they often indicate label ambiguity, hidden subclasses, or feature insufficiency.

### Quality Profile

The quality profile describes potential data problems.

Examples include missing labels, corrupt samples, duplicate samples, near-duplicates, extreme outliers, invalid coordinates, inconsistent metadata, invalid split assignments, and leakage risk.

The quality profile should distinguish between hard validation failures and softer warnings.

### Coverage Profile

The coverage profile describes which regions of the data space are dense, sparse, underrepresented, or missing.

For scratch detection, a coverage gap may look like too few short arcs, too few sparse non-scratch arc-like examples, too few examples from a specific tool, or poor coverage of edge-of-wafer cases.

Coverage gaps are candidate dataset improvement targets.

### Separability Profile

The separability profile describes whether labels appear naturally separable.

Possible measures include nearest-neighbor label consistency, class-overlap score, silhouette score, prototype distance, cluster purity, and confusion-prone region detection.

Separability should be treated as evidence, not truth. A low separability score might mean labels are ambiguous, features are inadequate, representation is poor, or the task is genuinely hard.

### Ambiguity Profile

The ambiguity profile identifies regions where labels or classes appear difficult to distinguish.

Ambiguity regions may include mixed-label clusters, low-confidence regions, high-disagreement neighborhoods, or groups of samples that look geometrically similar but have different labels.

Ambiguity should be surfaced clearly because additional model training may not resolve a label-policy problem.

---

## Dataset Characterization Output

A characterization should produce both structured records and artifacts.

Structured records should be saved to the database.

Artifacts may include plots, cluster visualizations, representative sample grids, distribution charts, and characterization summaries. These should be saved to MLflow or the artifact store and referenced from the database.

The static report should include a dataset characterization section that summarizes the most important findings.

A useful characterization summary might say:

```text
Dataset v0.3.0 contains 12,400 samples across two classes. Class balance is even, but three low-purity clusters were detected. The most important ambiguity region contains short low-point-count arcs with mixed scratch and non-scratch labels. Compared with v0.2.0, coverage of short-arc examples improved, but label ambiguity in that region remains high.
```

---

## Dataset Versioning

Dataset versions should be created whenever the dataset materially changes.

Material changes include adding samples, removing samples, correcting labels, changing label policy, merging classes, splitting classes, adding synthetic data, changing metadata, changing derived features, changing train/validation/test splits, or refreshing a benchmark.

A dataset version should record:

```text
dataset_id
version
parent_version
data_hash
manifest_path
created_at
created_by
change_type
change_summary
created_because
comparability_status
status
```

Version names may use semantic versioning, but the exact convention is not settled.

A useful starting convention is:

```text
major.minor.patch
```

A major version changes the task definition, label policy, class ontology, or benchmark meaning.

A minor version adds or removes meaningful data while preserving task definition.

A patch version corrects errors without materially changing task definition.

This convention should remain flexible until real dataset changes reveal better rules.

---

## Dataset Change Types

Dataset change types should be controlled values.

Recommended initial change types:

```text
initial_import
raw_data_addition
targeted_data_addition
label_correction
label_policy_change
class_merge
class_split
synthetic_data_addition
sample_removal
deduplication
metadata_enrichment
feature_addition
split_change
benchmark_refresh
human_review_update
```

The change type matters because it affects comparability.

For example, a targeted data addition may preserve the task while changing class coverage. A class merge may create a new task. A label-policy change may invalidate direct comparison to prior metrics.

---

## Dataset Lineage

Dataset lineage records how dataset versions relate.

A lineage graph might look like:

```text
scratch_pointcloud:v0.1.0
└── scratch_pointcloud:v0.2.0
    change: label correction after human review
    result: validation errors reduced

    └── scratch_pointcloud:v0.3.0
        change: targeted short-arc additions
        result: short-arc recall improved

        └── scratch_pointcloud:v1.0.0
            change: label policy changed
            result: new task definition
```

Lineage allows LASI to reason about dataset evolution rather than treating each dataset as isolated.

---

## Comparability

Comparability describes whether results from two dataset versions can be meaningfully compared.

Suggested comparability values:

```text
comparable
partially_comparable
not_comparable
unknown
```

A dataset version may be comparable if data was added without changing the label policy or evaluation definition.

It may be partially comparable if the dataset was expanded, deduplicated, or corrected in a way that changes distribution but preserves task meaning.

It may be not comparable if class definitions, label policy, ontology, benchmark construction, or evaluation policy changed.

Comparability should be recorded explicitly. The harness should not claim improvement across non-comparable dataset versions.

---

## Benchmark Datasets

Benchmarks are protected dataset versions used to evaluate progress.

The benchmark system should distinguish training sets, validation sets, frozen benchmarks, stress tests, human-review sets, synthetic sets, and unlabeled pretraining sets.

A frozen benchmark should not be casually modified. If labels or policy change, create a new benchmark version and preserve the old one.

Benchmark governance is not fully defined yet. The system will eventually need rules for benchmark approval, refresh cadence, label audit, and overfitting prevention.

For the MVP, the system should at least record whether a dataset version is being used as a benchmark and warn if the benchmark changes.

---

## Dataset Improvement Proposals

A dataset improvement proposal is created when the harness, scientist provider, human reviewer, or sabbatical review recommends changing the dataset.

A proposal should state:

```text
proposal_id
dataset_version
hypothesis
recommended_change
expected_effect
success_metric
comparability_risk
required_approval
status
```

Example:

```text
Hypothesis:
Short-arc scratch examples are underrepresented.

Recommended Change:
Add 300 to 500 reviewed examples from the short-arc ambiguity region.

Expected Effect:
Improve short-arc recall without increasing false positives by more than 2%.

Comparability Risk:
Partially comparable.
```

Dataset improvement proposals are important because they make data changes testable. The system should later check whether the change had the expected effect.

---

## Dataset Update Validation

When a new dataset version is created because of a recommendation, the system should validate whether the update helped.

It should compare the new version to the parent version where comparison is valid.

It should answer:

> Did the dataset change address the issue it was supposed to address?

For example, if the recommendation was to add short-arc examples, the system should check whether short-arc coverage improved and whether short-arc recall improved after retraining or re-evaluation.

The result should be recorded as confirming, weakening, contradicting, or making non-comparable the original recommendation.

---

## Dataset Portfolio View

The dataset portfolio is the long-term view of dataset assets.

It should show dataset versions, change types, causes, comparability, benchmark roles, performance before and after changes, open improvement proposals, and current status.

A useful portfolio table might include:

```text
Dataset Version | Change Type | Cause | Comparable? | Key Effect | Status
v0.1.0          | initial     | import | baseline    | baseline   | archived
v0.2.0          | correction  | review | partial     | fewer errors | approved
v0.3.0          | targeted add| agent recommendation | partial | short-arc recall improved | candidate
v1.0.0          | policy change | reviewer disagreement | no | new task definition | experimental
```

The portfolio view should make it obvious when apparent performance improvements are not directly comparable.

---

## Dataset Status

Dataset versions should have status values.

Suggested values:

```text
draft
validated
characterized
approved_for_training
experimental
benchmark
production_candidate
deprecated
archived
blocked
```

A dataset should not be used for training unless it has passed validation and, ideally, characterization.

A benchmark should not be deprecated without preserving its history.

---

## Dataset Characterization and Knowledge Layer

The dataset system should produce operational records and may also produce semantic lessons.

The database records characterization metrics and dataset version metadata.

MLflow stores characterization artifacts.

The knowledge layer stores lessons that generalize beyond one dataset.

For example, a characterization finding might say:

```text
Cluster 12 in scratch_pointcloud:v0.3.0 has low purity.
```

That belongs in the database.

A lesson might say:

```text
In multiple scratch point-cloud datasets, short low-point-count arcs have been the most common source of label ambiguity.
```

That belongs in the knowledge layer after review.

The knowledge curator may draft such a lesson, but it should not be automatically accepted as institutional knowledge.

---

## Dataset System Data Flow

A normal dataset workflow follows this pattern:

```text
Raw data is provided
↓
Dataset manifest is created
↓
Manifest is validated
↓
Dataset version is created
↓
Dataset is characterized
↓
Characterization is stored
↓
Artifacts are saved
↓
Dataset may be approved for training
↓
Experiments reference the dataset version
↓
Results may trigger dataset improvement proposals
↓
New dataset versions preserve lineage
```

This flow should remain stable even as new dataset types are added.

---

## Authority Boundaries

The dataset system records and validates data.

It does not decide scientific meaning by itself.

The scientist provider may recommend dataset changes.

The decision system determines whether those changes are allowed.

Humans approve high-consequence changes such as label-policy updates, class merges, benchmark changes, and production dataset promotion.

The knowledge curator may draft lessons based on dataset evolution, but humans approve semantic knowledge updates.

---

## MVP Dataset Scope

The minimum viable dataset system should support only one concrete use case:

```text
binary point-cloud scratch classification
```

It should support one primary manifest format, one label schema, basic validation, basic characterization, dataset version records, and static report integration.

It does not need to support every data modality, complex ontology versioning, automated benchmark governance, synthetic data management, or learned dataset similarity in the MVP.

---

## Unsettled Questions

The first unsettled question is the exact point-cloud storage format. The MVP should choose one primary format quickly to avoid blocking implementation.

The second unsettled question is the operational definition of scratch. Without a label policy, the harness can diagnose ambiguity but cannot resolve it.

The third unsettled question is the minimum useful characterization. Too little characterization makes the scientist provider guess. Too much characterization can delay the MVP.

The fourth unsettled question is comparability policy. The system needs clear rules for when dataset versions are comparable, partially comparable, or not comparable.

The fifth unsettled question is benchmark governance. The MVP can record benchmark roles, but a mature system needs approval and refresh rules.

The sixth unsettled question is how synthetic data should be represented. It may be a dataset role, a dataset version, a generation artifact, or a separate managed asset.

The seventh unsettled question is whether dataset characterization should run locally or remotely. For large datasets, characterization may need SSH execution just like training.

---

## Out of Scope for This File

This file does not define database table schemas, model training workflows, scientist-provider prompts, report templates, OpenCode command syntax, or detailed implementation code.

Those belong in separate LASI documents.

This file defines the responsibilities and behavior of the dataset system.
