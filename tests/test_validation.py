import pandas as pd

from toxic_service.data import validate_dataset


def test_valid_dataframe_passes():
    """Проверяет, что корректный датасет объемом >= 1000 строк успешно проходит проверку."""
    data = {
        "comment_text": [f"Neutral clean test comment number {i}" for i in range(1200)],
        "toxic": [0] * 1050 + [1] * 150,  # ~12.5% токсичности (в пределах 1% - 90%)
    }
    df = pd.DataFrame(data)
    assert validate_dataset(df) is True


def test_corrupted_value_caught():
    """Проверяет, что недопустимый класс (toxic=5) или пустой текст отлавливаются."""
    # Недопустимый класс (5 вместо 0 или 1)
    bad_class_data = {
        "comment_text": [f"Valid text {i}" for i in range(1100)],
        "toxic": [0] * 1099 + [5],
    }
    df_bad_class = pd.DataFrame(bad_class_data)
    assert validate_dataset(df_bad_class) is False

    # Пустая строка в тексте комментария
    empty_text_data = {
        "comment_text": [f"Valid text {i}" for i in range(1099)] + [""],
        "toxic": [0] * 1100,
    }
    df_empty_text = pd.DataFrame(empty_text_data)
    assert validate_dataset(df_empty_text) is False


def test_undersized_dataset_rejected():
    """Проверяет, что выгрузка объемом менее 1000 строк отвергается."""
    small_data = {
        "comment_text": [f"Valid comment {i}" for i in range(500)],
        "toxic": [0] * 450 + [1] * 50,
    }
    df_small = pd.DataFrame(small_data)
    assert validate_dataset(df_small) is False