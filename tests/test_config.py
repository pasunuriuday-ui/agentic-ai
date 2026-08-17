from app.core.config import settings


def test_embedding_model():

    print(
        "EMBEDDING MODEL:",
        settings.embedding_model
    )

    assert settings.embedding_model


def test_collection_name():

    assert settings.collection_name


def test_max_steps():

    assert settings.max_steps > 0