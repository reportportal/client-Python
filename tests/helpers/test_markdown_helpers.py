from reportportal_client.helpers.markdown_helpers import (
    ONE_SPACE,
    TABLE_INDENT,
    as_code,
    as_markdown,
    as_two_parts,
    format_data_table,
    format_data_table_dict,
)

# Constants for table formatting
BIG_COLUMN_VALUE = "4CZtyV3qsjVX08vBKu5YpvY2ckoFxLUombHEj1yf4uaBmrSGTzcXvlfba52HtUGLm56a8Vx4fBa0onEjlXY"
TRUNCATED_COLUMN_VALUE = "4CZtyV3qsjVX08vBKu5YpvY2ckoFxLUombHEj1yf4uaBmrSGTzcXvlfba52..."
SECOND_TRUNCATED_COLUMN_VALUE = "4CZtyV3qsjVX08vBKu5YpvY2ckoFxLU..."

ONE_ROW_EXPECTED_TABLE = (
    f"{TABLE_INDENT}|{ONE_SPACE}var_a{ONE_SPACE}|{ONE_SPACE}var_b{ONE_SPACE}|{ONE_SPACE}result{ONE_SPACE}|\n"
    f"{TABLE_INDENT}|-------|-------|--------|\n"
    f"{TABLE_INDENT}|{ONE_SPACE*3}2{ONE_SPACE*3}|{ONE_SPACE*3}2{ONE_SPACE*3}|{ONE_SPACE*3}4{ONE_SPACE*4}|"
)

TWO_ROWS_EXPECTED_TABLE = (
    ONE_ROW_EXPECTED_TABLE
    + f"\n{TABLE_INDENT}|{ONE_SPACE*3}1{ONE_SPACE*3}|{ONE_SPACE*3}2{ONE_SPACE*3}|{ONE_SPACE*3}3{ONE_SPACE*4}|"
)

TWO_ROWS_LONG_EXPECTED_TABLE = (
    f"{TABLE_INDENT}|{ONE_SPACE}var_a{ONE_SPACE}|{ONE_SPACE*29}var_b{ONE_SPACE*30}|{ONE_SPACE}result{ONE_SPACE}|\n"
    f"{TABLE_INDENT}|-------|----------------------------------------------------------------|--------|\n"
    f"{TABLE_INDENT}|{ONE_SPACE*3}2{ONE_SPACE*3}|{ONE_SPACE*31}2{ONE_SPACE*32}|{ONE_SPACE*3}4{ONE_SPACE*4}|\n"
    f"{TABLE_INDENT}|{ONE_SPACE*3}1{ONE_SPACE*3}|{ONE_SPACE}{TRUNCATED_COLUMN_VALUE}{ONE_SPACE}|{ONE_SPACE*3}3{ONE_SPACE*4}|"  # noqa: E501
)

TWO_ROWS_LONG_EXPECTED_TABLE_TWO = (
    f"{TABLE_INDENT}|{ONE_SPACE}var_a{ONE_SPACE}|{ONE_SPACE*15}var_b{ONE_SPACE*16}|{ONE_SPACE*15}result{ONE_SPACE*15}|\n"  # noqa: E501
    f"{TABLE_INDENT}|-------|------------------------------------|------------------------------------|"
    f"\n{TABLE_INDENT}|{ONE_SPACE*3}2{ONE_SPACE*3}|{ONE_SPACE*17}2{ONE_SPACE*18}|{ONE_SPACE}{SECOND_TRUNCATED_COLUMN_VALUE}{ONE_SPACE}|\n"  # noqa: E501
    f"{TABLE_INDENT}|{ONE_SPACE*3}1{ONE_SPACE*3}|{ONE_SPACE}{SECOND_TRUNCATED_COLUMN_VALUE}{ONE_SPACE}|{ONE_SPACE*17}3{ONE_SPACE*18}|"  # noqa: E501
)

MIN_ROW_WIDTH_EXPECTED_TABLE_TRANSPOSE = f"{TABLE_INDENT}|var|2|\n" f"{TABLE_INDENT}|var|2|\n" f"{TABLE_INDENT}|res|4|"

MIN_ROW_WIDTH_EXPECTED_TABLE_NO_TRANSPOSE = (
    f"{TABLE_INDENT}|var|res|\n"
    f"{TABLE_INDENT}|---|---|\n"
    f"{TABLE_INDENT}|{ONE_SPACE}2{ONE_SPACE}|{ONE_SPACE}4{ONE_SPACE}|"
)

MIN_ROW_WIDTH_EXPECTED_TABLE_TRANSPOSE_PAD = (
    f"{TABLE_INDENT}|{ONE_SPACE}var_a{ONE_SPACE*2}|{ONE_SPACE}2{ONE_SPACE}|\n"
    f"{TABLE_INDENT}|{ONE_SPACE}var_b{ONE_SPACE*2}|{ONE_SPACE}2{ONE_SPACE}|\n"
    f"{TABLE_INDENT}|{ONE_SPACE}result{ONE_SPACE}|{ONE_SPACE}4{ONE_SPACE}|"
)


def test_as_markdown():
    assert as_markdown("hello") == "!!!MARKDOWN_MODE!!!hello"


def test_to_markdown_script():
    assert as_code("groovy", "hello") == "!!!MARKDOWN_MODE!!!```groovy\nhello\n```"


def test_format_data_table():
    table = [["var_a", "var_b", "result"], ["2", "2", "4"], ["1", "2", "3"]]
    assert format_data_table(table) == TWO_ROWS_EXPECTED_TABLE


def test_format_data_table_one_big_col():
    table = [["var_a", "var_b", "result"], ["2", "2", "4"], ["1", BIG_COLUMN_VALUE, "3"]]
    assert format_data_table(table) == TWO_ROWS_LONG_EXPECTED_TABLE


def test_format_data_table_two_big_col():
    table = [["var_a", "var_b", "result"], ["2", "2", BIG_COLUMN_VALUE], ["1", BIG_COLUMN_VALUE, "3"]]
    assert format_data_table(table) == TWO_ROWS_LONG_EXPECTED_TABLE_TWO


def test_format_data_table_map():
    table = {"var_a": "2", "var_b": "2", "result": "4"}
    assert format_data_table_dict(table) == ONE_ROW_EXPECTED_TABLE


def test_format_data_table_min_size_transpose():
    table = [["var_a", "var_b", "result"], ["2", "2", "4"]]
    assert format_data_table(table, 0) == MIN_ROW_WIDTH_EXPECTED_TABLE_TRANSPOSE


def test_format_data_table_min_size_no_transpose():
    table = [["var_a", "result"], ["2", "4"]]
    assert format_data_table(table, 0) == MIN_ROW_WIDTH_EXPECTED_TABLE_NO_TRANSPOSE


def test_format_data_table_min_size_transpose_pad():
    table = [["var_a", "var_b", "result"], ["2", "2", "4"]]
    assert format_data_table(table, 14) == MIN_ROW_WIDTH_EXPECTED_TABLE_TRANSPOSE_PAD


def test_format_two_parts():
    text_part_one = "This is a text"
    text_part_two = "This is another text"
    expected_two_parts = f"{text_part_one}\n\n---\n\n{text_part_two}"
    assert as_two_parts(text_part_one, text_part_two) == expected_two_parts
