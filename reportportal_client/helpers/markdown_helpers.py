"""A set of utility methods for reporting to ReportPortal."""

from itertools import zip_longest
from typing import Any, Dict, List, Optional

MARKDOWN_MODE = "!!!MARKDOWN_MODE!!!"
NEW_LINE = "\n"
ONE_SPACE = "\xA0"
TABLE_INDENT = ONE_SPACE * 4
TABLE_COLUMN_SEPARATOR = "|"
TABLE_ROW_SEPARATOR = "-"
TRUNCATION_REPLACEMENT = "..."
PADDING_SPACES_NUM = 2
MAX_TABLE_SIZE = 83
MIN_COL_SIZE = 3
LOGICAL_SEPARATOR = NEW_LINE + NEW_LINE + "---" + NEW_LINE + NEW_LINE


def as_markdown(message: str) -> str:
    """Add special prefix to make log message being processed as markdown.

    :param message: Message to be marked as markdown
    :return: Message with markdown marker
    """
    return MARKDOWN_MODE + message


def as_code(language: Optional[str], script: Optional[str]) -> str:
    """Build markdown representation of some script to be logged to ReportPortal.

    :param language: Script language
    :param script: Script content
    :return: Message to be sent to ReportPortal
    """
    lang = language or ""
    return as_markdown(f"```{lang}\n{script}\n```")


def calculate_col_sizes(table: List[List[str]]) -> List[int]:
    """Calculate maximum width for each column in the table.

    :param table: Table data as list of rows
    :return: List of maximum widths for each column
    """
    if not table:
        return []
    if len(table) == 1:
        cols = table
    else:
        # noinspection PyArgumentList
        cols = list(zip_longest(*table))
    return [max(len(str(cell)) for cell in col if cell is not None) for col in cols]


def calculate_table_size(col_sizes: List[int]) -> int:
    """Calculate total table width including separators and padding.

    :param col_sizes: List of column widths
    :return: Total table width
    """
    if not col_sizes:
        return 0
    col_table_size = sum(col_sizes)
    col_table_size += (PADDING_SPACES_NUM + len(TABLE_COLUMN_SEPARATOR)) * len(col_sizes) - 1
    col_table_size += 2
    return col_table_size


def transpose_table(table: List[List[Any]]) -> List[List[Any]]:
    """Transpose table rows into columns.

    :param table: Table data as list of rows
    :return: Transposed table
    """
    if not table:
        return []
    if len(table) == 1:
        transposed = table
    else:
        # noinspection PyArgumentList
        transposed = zip_longest(*table)
    return [list(filter(None, col)) for col in transposed]


def adjust_col_sizes(col_sizes: List[int], max_table_size: int) -> List[int]:
    """Adjust column sizes to fit maximum table width.

    :param col_sizes: List of column widths
    :param max_table_size: Maximum allowed table width
    :return: Adjusted column widths
    """
    col_table_size = calculate_table_size(col_sizes)
    if max_table_size >= col_table_size:
        return col_sizes

    cols_by_size = sorted([(size, i) for i, size in enumerate(col_sizes)], reverse=True)
    size_to_shrink = col_table_size - max_table_size

    for _ in range(size_to_shrink):
        for j in range(len(cols_by_size)):
            current_size, current_idx = cols_by_size[j]
            if current_size <= MIN_COL_SIZE:
                continue
            next_size = cols_by_size[j + 1][0] if j + 1 < len(cols_by_size) else 0
            if current_size >= next_size:
                cols_by_size[j] = (current_size - 1, current_idx)
                break

    return [size for size, _ in sorted(cols_by_size, key=lambda x: x[1])]


def format_data_table(table: List[List[str]], max_table_size: int = MAX_TABLE_SIZE) -> str:
    """Convert a table represented as List of Lists to a formatted table string.

    :param table: Table data as list of rows
    :param max_table_size: Maximum size in characters of result table
    :return: String representation of the table
    """
    if not table:
        return ""

    col_sizes = calculate_col_sizes(table)
    transpose = len(col_sizes) > len(table) and calculate_table_size(col_sizes) > max_table_size
    print_table = transpose_table(table) if transpose else table

    if transpose:
        col_sizes = calculate_col_sizes(print_table)

    col_sizes = adjust_col_sizes(col_sizes, max_table_size)
    table_size = calculate_table_size(col_sizes)
    add_padding = table_size <= max_table_size
    header = not transpose

    result = []
    for row in print_table:
        line = [TABLE_INDENT + TABLE_COLUMN_SEPARATOR]
        for i, cell in enumerate(row):
            cell = str(cell)
            col_size = col_sizes[i]
            if col_size < len(cell):
                if len(TRUNCATION_REPLACEMENT) < col_size:
                    cell = cell[: col_size - len(TRUNCATION_REPLACEMENT)] + TRUNCATION_REPLACEMENT
                else:
                    cell = cell[:col_size]

            pad_size = col_size - len(cell) + (PADDING_SPACES_NUM if add_padding else 0)
            l_space = pad_size // 2
            r_space = pad_size - l_space
            line.append(ONE_SPACE * l_space + cell + ONE_SPACE * r_space + TABLE_COLUMN_SEPARATOR)

        result.append("".join(line))
        if header:
            header = False
            separator = [TABLE_INDENT + TABLE_COLUMN_SEPARATOR]
            for i in range(len(row)):
                max_size = col_sizes[i] + (PADDING_SPACES_NUM if add_padding else 0)
                separator.append(TABLE_ROW_SEPARATOR * max_size + TABLE_COLUMN_SEPARATOR)
            result.append("".join(separator))

    return "\n".join(result)


def format_data_table_dict(table: Dict[str, str]) -> str:
    """Convert a table represented as Map to a formatted table string.

    :param table: Table data as dictionary
    :return: String representation of the table
    """
    keys = list(table.keys())
    values = [table[k] for k in keys]
    return format_data_table([keys, values])


def as_two_parts(first_part: str, second_part: str) -> str:
    """Join two parts with a logical separator.

    :param first_part: First part of the text
    :param second_part: Second part of the text
    :return: Joined text with logical separator
    """
    return first_part + LOGICAL_SEPARATOR + second_part
