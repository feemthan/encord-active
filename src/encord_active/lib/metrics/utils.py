from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, Union

import pandas as pd
import pandera as pa
from encord.objects.common import PropertyType
from encord.ontology import OntologyStructure
from natsort import natsorted
from pandera.typing import DataFrame, Series

from encord_active.lib.common.utils import load_json
from encord_active.lib.metrics.metric import (
    AnnotationType,
    AnnotationTypeUnion,
    EmbeddingType,
    MetricMetadata,
)


@dataclass
class MetricData:
    name: str
    path: Path
    meta: MetricMetadata
    level: str


class IdentifierSchema(pa.SchemaModel):
    identifier: Series[str] = pa.Field()


class MetricSchema(IdentifierSchema):
    score: Series[float] = pa.Field(coerce=True)
    identifier: Series[str] = pa.Field()
    description: Series[str] = pa.Field(nullable=True, coerce=True)
    object_class: Series[str] = pa.Field(nullable=True, coerce=True)
    annotator: Series[str] = pa.Field(nullable=True, coerce=True)
    frame: Series[int] = pa.Field()
    url: Series[str] = pa.Field(nullable=True, coerce=True)


def load_metric_dataframe(
    metric: MetricData, normalize: bool = False, *, sorting_key="score"
) -> DataFrame[MetricSchema]:
    """
    Load and sort the selected csv file and cache it, so we don't need to perform this
    heavy computation each time the slider in the UI is moved.
    :param metric: The metric to load data from.
    :param normalize: whether to apply normalisation to the scores or not.
    :param sorting_key: key by which to sort dataframe (default: "score")
    :return: a pandas data frame with all the scores.
    """
    df = pd.read_csv(metric.path).sort_values([sorting_key, "identifier"], ascending=True).reset_index()

    if normalize:
        min_val = metric.meta.get("min_value")
        max_val = metric.meta.get("max_value")
        if min_val is None:
            min_val = df["score"].min()
        if max_val is None:
            max_val = df["score"].max()

        diff = max_val - min_val
        if diff == 0:  # Avoid dividing by zero
            diff = 1.0

        df["score"] = (df["score"] - min_val) / diff

    return df.pipe(DataFrame[MetricSchema])


class MetricScope(Enum):
    DATA_QUALITY = "data_quality"
    LABEL_QUALITY = "label_quality"
    MODEL_QUALITY = "model_quality"


def get_metric_operation_level(pth: Path) -> str:
    if not all([pth.exists(), pth.is_file(), pth.suffix == ".csv"]):
        return ""

    with pth.open("r", encoding="utf-8") as f:
        _ = f.readline()  # Header, which we don't care about
        csv_row = f.readline()  # Content line

    if not csv_row:  # Empty metric
        return ""

    key, _ = csv_row.split(",", 1)
    _, _, _, *object_hashes = key.split("_")
    return "O" if object_hashes else "F"


def is_valid_annotation_type(
    annotation_type: Union[None, List[str]], metric_scope: Optional[MetricScope] = None
) -> bool:
    if metric_scope == MetricScope.DATA_QUALITY:
        return annotation_type is None
    elif metric_scope == MetricScope.LABEL_QUALITY:
        return isinstance(annotation_type, list)
    else:
        return True


def load_available_metrics(metric_dir: Path, metric_scope: Optional[MetricScope] = None) -> List[MetricData]:
    if not metric_dir.is_dir():
        return []

    paths = natsorted([p for p in metric_dir.iterdir() if p.suffix == ".csv"], key=lambda x: x.stem.split("_", 1)[1])
    levels = list(map(get_metric_operation_level, paths))

    make_name = lambda p: p.name.split("_", 1)[1].rsplit(".", 1)[0].replace("_", " ").title()
    names = [f"{make_name(p)}" for p, l in zip(paths, levels)]
    meta_data = [load_json(f.with_suffix(".meta.json")) for f in paths]

    out: List[MetricData] = []

    if not meta_data:
        return out

    for p, n, m, l in zip(paths, names, meta_data, levels):
        if n in {"Object Count", "Frame Object Density"}:
            continue

        if m is None or not l or not is_valid_annotation_type(m.get("annotation_type"), metric_scope):
            continue

        out.append(MetricData(name=n, path=p, meta=MetricMetadata(**m), level=l))  # type: ignore

    out = natsorted(out, key=lambda i: (i.level, i.name))  # type: ignore
    return out


class AnnotatorInfo(TypedDict):
    name: str
    total_annotations: int
    mean_score: float


def get_annotator_level_info(df: DataFrame[MetricSchema]) -> dict[str, AnnotatorInfo]:
    annotator_set: List[str] = natsorted(df[MetricSchema.annotator].dropna().unique().tolist())
    annotators: Dict[str, AnnotatorInfo] = {}
    for annotator in annotator_set:
        annotators[annotator] = AnnotatorInfo(
            name=annotator,
            total_annotations=df[df[MetricSchema.annotator] == annotator].shape[0],
            mean_score=df[df[MetricSchema.annotator] == annotator]["score"].mean(),
        )

    return annotators


def is_multiclass_ontology(ontology: OntologyStructure):
    has_objects = bool(ontology.objects)
    radio_classifications = filter(
        lambda class_label: class_label.attributes[0].get_property_type() == PropertyType.RADIO,
        ontology.classifications,
    )
    num_of_classifications = len(list(radio_classifications))

    return (has_objects and num_of_classifications > 0) or (num_of_classifications > 1)


def get_embedding_type(metric_title: str, annotation_type: Optional[List[AnnotationTypeUnion]]) -> EmbeddingType:
    if not annotation_type or (metric_title in ["Frame object density", "Object Count"]):
        return EmbeddingType.IMAGE
    elif len(annotation_type) == 1 and annotation_type[0] == AnnotationType.CLASSIFICATION.RADIO:
        return EmbeddingType.CLASSIFICATION
    else:
        return EmbeddingType.OBJECT
