"""This modules contains unit tests for the helpers module."""

from reportportal_client.helpers import gen_attributes


def test_gen_attributes():
    """Test functionality of the gen_attributes function."""
    expected_out = [{'value': 'Tag'}, {'key': 'Key', 'value': 'Value'}]
    out = gen_attributes(['Tag', 'Key:Value', ''])
    assert expected_out == out
