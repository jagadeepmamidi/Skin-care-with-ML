"""Thin wrapper so the original ML notebook path still works as a Gold consumer."""

from skincare_platform.ml.features import IngredientRecommender


def get_recommendations(product_name: str, k: int = 10):
    return IngredientRecommender.from_settings(__import__("skincare_platform.config", fromlist=["get_settings"]).get_settings()).recommend(
        product_name, k=k
    )


if __name__ == "__main__":
    import sys

    name = " ".join(sys.argv[1:]) or "Crème de la Mer"
    print(get_recommendations(name).to_string(index=False))
