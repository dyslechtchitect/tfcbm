"""Tests for formatting utilities."""

from datetime import datetime, timedelta


def test_format_timestamp_just_now():
    from ui.utils.formatting import format_timestamp

    now = datetime.now()
    timestamp = now.isoformat()

    result = format_timestamp(timestamp)

    assert result == "Just now"


def test_format_timestamp_minutes_ago():
    from ui.utils.formatting import format_timestamp

    past = datetime.now() - timedelta(minutes=30)
    timestamp = past.isoformat()

    result = format_timestamp(timestamp)

    assert result == "30m ago"


def test_format_timestamp_hours_ago():
    from ui.utils.formatting import format_timestamp

    past = datetime.now() - timedelta(hours=2)
    timestamp = past.isoformat()

    result = format_timestamp(timestamp)

    assert result == "2h ago"


def test_format_timestamp_yesterday():
    from ui.utils.formatting import format_timestamp

    yesterday = datetime.now() - timedelta(days=1)
    timestamp = yesterday.isoformat()

    result = format_timestamp(timestamp)

    assert result == "Yesterday"


def test_format_timestamp_days_ago():
    from ui.utils.formatting import format_timestamp

    past = datetime.now() - timedelta(days=3)
    timestamp = past.isoformat()

    result = format_timestamp(timestamp)

    assert result == "3d ago"


def test_format_timestamp_weeks_ago():
    from ui.utils.formatting import format_timestamp

    past = datetime.now() - timedelta(days=10)
    timestamp = past.isoformat()

    result = format_timestamp(timestamp)

    assert past.strftime("%b %d") in result


def test_format_timestamp_invalid():
    from ui.utils.formatting import format_timestamp

    result = format_timestamp("invalid")

    assert result == "invalid"


def test_truncate_text_short():
    from ui.utils.formatting import truncate_text

    text = "Short text"

    result = truncate_text(text, max_length=100)

    assert result == "Short text"


def test_truncate_text_long():
    from ui.utils.formatting import truncate_text

    text = "A" * 200

    result = truncate_text(text, max_length=100)

    assert len(result) == 103
    assert result.endswith("...")


def test_truncate_text_exact_length():
    from ui.utils.formatting import truncate_text

    text = "A" * 100

    result = truncate_text(text, max_length=100)

    assert result == text


def test_format_size_bytes():
    from ui.utils.formatting import format_size

    result = format_size(512)

    assert result == "512.0 B"


def test_format_size_kilobytes():
    from ui.utils.formatting import format_size

    result = format_size(2048)

    assert result == "2.0 KB"


def test_format_size_megabytes():
    from ui.utils.formatting import format_size

    result = format_size(5242880)

    assert result == "5.0 MB"


def test_format_size_gigabytes():
    from ui.utils.formatting import format_size

    result = format_size(2147483648)

    assert result == "2.0 GB"
