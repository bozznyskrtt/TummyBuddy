"""Stage 1: food image -> {dish, ingredients}. Ported from the recipe notebook."""

from __future__ import annotations

import io
from typing import Any, Callable

from gastric_engine.pipeline.gemini_client import generate_json

INGREDIENT_PROMPT = (
    "Analyze this food image. Identify the main dish and provide a detailed "
    "ingredient breakdown for ONE individual serving exactly as plated and "
    "eaten in the photo (a single bowl or plate). Estimate the amount of each "
    "ingredient actually consumed in that one portion — do NOT report full-batch "
    "or full-pot recipe quantities. If the dish is normally cooked as a batch "
    "(e.g. a stock or broth), scale the amounts down to the part that ends up in "
    "one served portion. Because this data is used to predict gastrointestinal "
    "(GI) and stomach distress, you must be highly granular and include hidden "
    "or dissolved components like garlic, onion, cooking oils, dairy, or wheat "
    "if they are typically present in this dish style.\n\n"
    "You must respond strictly in JSON format matching this schema:\n"
    "{\n"
    '  "dish": "dish name",\n'
    '  "ingredients": [\n'
    '    {"name": "ingredient name", "amount": "quantity with unit"}\n'
    "  ]\n"
    "}\n"
    "Do not include markdown wrappers. Output raw JSON text only."
)


def _load_image(image: Any) -> Any:
    """Normalize bytes/path into an RGB PIL image (recipe-notebook behavior)."""
    from PIL import Image  # local import: only needed for real calls

    if isinstance(image, (bytes, bytearray)):
        raw = Image.open(io.BytesIO(image))
    else:
        raw = Image.open(image)
    return raw.convert("RGB")


def predict_food_and_ingredients(
    image: Any,
    *,
    generate: Callable[..., Any] = generate_json,
    load_image: Callable[[Any], Any] = _load_image,
) -> dict:
    img = load_image(image)
    result = generate(INGREDIENT_PROMPT, image=img)
    if not isinstance(result, dict) or "ingredients" not in result:
        raise ValueError(
            f"Image stage expected dish/ingredients JSON, got: {result!r}"
        )
    result.setdefault("dish", "unknown dish")
    return result
