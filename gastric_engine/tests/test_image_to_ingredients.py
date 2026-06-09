import pytest

from gastric_engine.pipeline.image_to_ingredients import (
    INGREDIENT_PROMPT,
    predict_food_and_ingredients,
)


def test_prompt_is_gi_focused():
    assert "gastrointestinal" in INGREDIENT_PROMPT.lower()
    assert "json" in INGREDIENT_PROMPT.lower()


def test_predict_returns_dish_and_ingredients_with_stubs():
    def fake_load_image(_image):
        return "IMG"

    def fake_generate(prompt, *, image=None, **kwargs):
        assert image == "IMG"
        return {
            "dish": "ramen",
            "ingredients": [{"name": "wheat noodles", "amount": "200 g"}],
        }

    result = predict_food_and_ingredients(
        b"fake-bytes", generate=fake_generate, load_image=fake_load_image
    )

    assert result["dish"] == "ramen"
    assert result["ingredients"][0]["name"] == "wheat noodles"


def test_predict_raises_on_missing_keys():
    def fake_generate(prompt, *, image=None, **kwargs):
        return {"unexpected": True}

    with pytest.raises(ValueError) as exc:
        predict_food_and_ingredients(
            b"x", generate=fake_generate, load_image=lambda _i: "IMG"
        )
    assert "ingredients" in str(exc.value)
