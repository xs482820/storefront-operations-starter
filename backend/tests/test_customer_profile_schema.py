import pytest
from pydantic import ValidationError

from app.schemas.customer import CustomerMeUpdateIn


def test_customer_display_name_accepts_chinese_and_english() -> None:
    display_name = "\u80b2\u5a74\u56edAlice"
    assert CustomerMeUpdateIn(display_name=display_name).display_name == display_name


@pytest.mark.parametrize("display_name", ["", " user", "user_1202", "\u7528\u62371202", "\u7528\u6237!", "a" * 21])
def test_customer_display_name_rejects_invalid_input(display_name: str) -> None:
    with pytest.raises(ValidationError):
        CustomerMeUpdateIn(display_name=display_name)
