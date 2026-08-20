from ropa.collectors.ay_not_dead import AyNotDeadCollector


def test_provider_rules_normalize_gender_and_categories() -> None:
    product = {
        "product_type": "Remeras",
        "tags": "Mujer, Sale",
    }
    collector = AyNotDeadCollector()

    assert collector.gender(product) == "woman"
    assert collector.categories(product) == ("remeras",)
