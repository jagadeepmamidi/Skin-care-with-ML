"""Gold ML feature export and content-based recommendations."""

from __future__ import annotations

import duckdb
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skincare_platform.config import Settings
from skincare_platform.lake import Lake, write_parquet
from skincare_platform.transforms import tokenize_ingredients


def load_gold_features(settings: Settings) -> pd.DataFrame:
    con = duckdb.connect(str(settings.duckdb_path_resolved()), read_only=True)
    try:
        return con.execute("SELECT * FROM marts.gold_ml_product_features").df()
    finally:
        con.close()


def export_ml_features(settings: Settings) -> dict[str, str | int]:
    frame = load_gold_features(settings)
    out_dir = settings.repo_root / "ml" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "gold_ml_product_features.parquet"
    frame.to_parquet(path, index=False)
    csv_path = out_dir / "gold_ml_product_features.csv"
    frame.to_csv(csv_path, index=False)
    return {"rows": int(len(frame)), "parquet": str(path), "csv": str(csv_path)}


def write_gold_ml_parquet(settings: Settings, lake: Lake) -> str:
    frame = load_gold_features(settings)
    return write_parquet(lake, "gold/recommendations/ml_product_features.parquet", frame)


def _ingredient_text(value: str | None) -> str:
    tokens = tokenize_ingredients(value)
    return " ".join(tokens)


class IngredientRecommender:
    """Content-based recommender that reads Gold features instead of cosmetics.csv."""

    def __init__(self, features: pd.DataFrame) -> None:
        self.features = features.reset_index(drop=True)
        corpus = self.features["ingredients"].fillna("").map(_ingredient_text)
        self.vectorizer = CountVectorizer(binary=True, token_pattern=r"[^ ]+")
        matrix = self.vectorizer.fit_transform(corpus)
        self.similarity = cosine_similarity(matrix)
        self._name_index = {
            str(name).lower(): i for i, name in enumerate(self.features["product_name"])
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> IngredientRecommender:
        artifact = settings.repo_root / "ml" / "artifacts" / "gold_ml_product_features.parquet"
        if artifact.exists():
            frame = pd.read_parquet(artifact)
        else:
            frame = load_gold_features(settings)
        return cls(frame)

    def recommend(self, product_name: str, k: int = 10) -> pd.DataFrame:
        key = product_name.lower()
        if key not in self._name_index:
            matches = [n for n in self._name_index if key in n]
            if not matches:
                raise KeyError(f"Product '{product_name}' not found in Gold features")
            key = matches[0]
        idx = self._name_index[key]
        scores = list(enumerate(self.similarity[idx]))
        scores.sort(key=lambda item: item[1], reverse=True)
        top = [i for i, _ in scores if i != idx][:k]
        out = self.features.iloc[top][
            [
                "product_id",
                "brand",
                "product_name",
                "price",
                "rating",
                "category",
                "popularity_score",
            ]
        ].copy()
        out["similarity"] = [self.similarity[idx][i] for i in top]
        return out.reset_index(drop=True)
