from reportportal_client.core.rp_requests import (
    ItemFinishRequest,
    ItemStartRequest,
    LaunchFinishRequest,
    LaunchStartRequest,
)
from reportportal_client.helpers import (
    ITEM_DESCRIPTION_LENGTH_LIMIT,
    ITEM_NAME_LENGTH_LIMIT,
    LAUNCH_DESCRIPTION_LENGTH_LIMIT,
    LAUNCH_NAME_LENGTH_LIMIT,
)


def test_launch_name_truncated_in_payload():
    launch_name = "n" * (LAUNCH_NAME_LENGTH_LIMIT + 20)
    payload = LaunchStartRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        name=launch_name,
        start_time="0",
    ).payload
    assert len(payload["name"]) == LAUNCH_NAME_LENGTH_LIMIT
    assert payload["name"].endswith("...")


def test_item_name_cleaned_and_truncated_in_payload():
    item_name = "bad\x00name" + ("n" * ITEM_NAME_LENGTH_LIMIT)
    payload = ItemStartRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        name=item_name,
        start_time="0",
        type_="SUITE",
        launch_uuid="launch_uuid",
        attributes=None,
        code_ref=None,
        description=None,
        has_stats=True,
        parameters=None,
        retry=False,
        retry_of=None,
        test_case_id=None,
        uuid=None,
    ).payload
    assert "\x00" not in payload["name"]
    assert len(payload["name"]) == ITEM_NAME_LENGTH_LIMIT


def test_launch_description_cleaned_and_truncated_in_payload():
    launch_description = "bad\x00description" + ("d" * LAUNCH_DESCRIPTION_LENGTH_LIMIT)
    payload = LaunchStartRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        name="launch",
        start_time="0",
        description=launch_description,
    ).payload
    assert "\x00" not in payload["description"]
    assert len(payload["description"]) == LAUNCH_DESCRIPTION_LENGTH_LIMIT
    assert payload["description"].endswith("...")


def test_item_description_cleaned_and_truncated_in_payload():
    item_description = "bad\x00description" + ("d" * ITEM_DESCRIPTION_LENGTH_LIMIT)
    payload = ItemStartRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        name="item",
        start_time="0",
        type_="SUITE",
        launch_uuid="launch_uuid",
        attributes=None,
        code_ref=None,
        description=item_description,
        has_stats=True,
        parameters=None,
        retry=False,
        retry_of=None,
        test_case_id=None,
        uuid=None,
    ).payload
    assert "\x00" not in payload["description"]
    assert len(payload["description"]) == ITEM_DESCRIPTION_LENGTH_LIMIT
    assert payload["description"].endswith("...")


def test_finish_requests_truncate_description():
    launch_finish_payload = LaunchFinishRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        end_time="0",
        description="d" * (LAUNCH_DESCRIPTION_LENGTH_LIMIT + 10),
    ).payload
    item_finish_payload = ItemFinishRequest(
        truncate_attributes_enabled=None,
        truncate_fields_enabled=None,
        replace_binary_characters=None,
        end_time="0",
        launch_uuid="launch_uuid",
        status="PASSED",
        attributes=None,
        description="d" * (ITEM_DESCRIPTION_LENGTH_LIMIT + 10),
        is_skipped_an_issue=True,
        issue=None,
        retry=False,
        retry_of=None,
        test_case_id=None,
    ).payload

    assert len(launch_finish_payload["description"]) == LAUNCH_DESCRIPTION_LENGTH_LIMIT
    assert launch_finish_payload["description"].endswith("...")
    assert len(item_finish_payload["description"]) == ITEM_DESCRIPTION_LENGTH_LIMIT
    assert item_finish_payload["description"].endswith("...")
