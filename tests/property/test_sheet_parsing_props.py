"""Property tests for SheetReader parsing.

Feature: reach-first-subscriptions

Tests the _parse_reach_ids function and SheetReader.get_subscribers() method
for correct parsing, filtering, and deduplication behavior.

Validates: Requirements 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import ReachSubscriber
from src.sheet_reader import SheetReader, _parse_reach_ids


# --- Strategies ---

# Positive integers representing valid reach IDs
positive_int_strategy = st.integers(min_value=1, max_value=99999)

# Whitespace that can appear around tokens
whitespace_strategy = st.text(
    alphabet=" \t", min_size=0, max_size=5
)

# Non-integer tokens (letters, symbols, floats, etc.)
non_integer_token_strategy = st.one_of(
    st.from_regex(r"[a-zA-Z]+", fullmatch=True),
    st.from_regex(r"[0-9]+\.[0-9]+", fullmatch=True),
    st.from_regex(r"[!@#$%^&]+", fullmatch=True),
    st.just(""),
)

# Valid email addresses for testing
email_strategy = st.from_regex(
    r"[a-z]{3,8}@[a-z]{3,6}\.(com|org|net)", fullmatch=True
)


# --- Property 1: Reach ID parsing round-trip ---


@settings(max_examples=100)
@given(
    reach_ids=st.lists(positive_int_strategy, min_size=1, max_size=10),
    spaces=st.lists(whitespace_strategy, min_size=20, max_size=20),
)
def test_property_1_reach_id_parsing_round_trip(
    reach_ids: list[int], spaces: list[str]
):
    """Feature: reach-first-subscriptions, Property 1: Reach ID parsing round-trip

    For any list of positive integers formatted as comma-separated with
    arbitrary whitespace, parsing produces the same integers.

    Validates: Requirements 1.2, 1.3, 7.3
    """
    # Format integers as comma-separated string with random whitespace
    parts = []
    for i, rid in enumerate(reach_ids):
        left_ws = spaces[i % len(spaces)]
        right_ws = spaces[(i + 1) % len(spaces)]
        parts.append(f"{left_ws}{rid}{right_ws}")
    raw_value = ",".join(parts)

    result = _parse_reach_ids(raw_value, "test@example.com")

    # Deduplicate expected (preserving first occurrence) since _parse_reach_ids deduplicates
    expected = list(dict.fromkeys(reach_ids))
    assert result == expected


# --- Property 2: Blank email filtering ---


@settings(max_examples=100)
@given(
    valid_emails=st.lists(email_strategy, min_size=1, max_size=5),
    blank_count=st.integers(min_value=1, max_value=3),
)
def test_property_2_blank_email_filtering(
    valid_emails: list[str], blank_count: int
):
    """Feature: reach-first-subscriptions, Property 2: Blank email filtering

    Rows with blank/whitespace emails are excluded from results.

    Validates: Requirements 1.4
    """
    # Build mock worksheet data: header + valid rows + blank email rows
    header = ["Email", "Reach IDs"]
    rows = [header]

    # Add valid rows
    for email in valid_emails:
        rows.append([email, "1493, 2001"])

    # Add blank email rows (various blank forms)
    blank_emails = ["", "   ", "\t", " \t ", "  "]
    for i in range(blank_count):
        rows.append([blank_emails[i % len(blank_emails)], "1493, 2001"])

    # Mock the worksheet
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_values.return_value = rows

    with patch.object(SheetReader, "_get_worksheet", return_value=mock_worksheet):
        reader = SheetReader.__new__(SheetReader)
        subscribers = reader.get_subscribers()

    # All returned subscribers should have non-blank emails
    assert len(subscribers) == len(valid_emails)
    for sub in subscribers:
        assert sub.email.strip() != ""


# --- Property 3: Empty reach IDs filtering ---


@settings(max_examples=100)
@given(
    valid_emails=st.lists(email_strategy, min_size=1, max_size=5),
    empty_reach_count=st.integers(min_value=1, max_value=3),
)
def test_property_3_empty_reach_ids_filtering(
    valid_emails: list[str], empty_reach_count: int
):
    """Feature: reach-first-subscriptions, Property 3: Empty reach IDs filtering

    Rows with empty Reach IDs are excluded from results.

    Validates: Requirements 1.5
    """
    # Build mock worksheet data: header + valid rows + empty reach ID rows
    header = ["Email", "Reach IDs"]
    rows = [header]

    # Add valid rows
    for email in valid_emails:
        rows.append([email, "1493, 2001"])

    # Add rows with empty reach IDs
    empty_values = ["", "   ", "\t"]
    for i in range(empty_reach_count):
        rows.append([f"empty{i}@test.com", empty_values[i % len(empty_values)]])

    # Mock the worksheet
    mock_worksheet = MagicMock()
    mock_worksheet.get_all_values.return_value = rows

    with patch.object(SheetReader, "_get_worksheet", return_value=mock_worksheet):
        reader = SheetReader.__new__(SheetReader)
        subscribers = reader.get_subscribers()

    # Only valid rows should be returned (those with non-empty reach IDs)
    assert len(subscribers) == len(valid_emails)
    for sub in subscribers:
        assert len(sub.reach_ids) > 0


# --- Property 12: Invalid reach ID filtering ---


@settings(max_examples=100)
@given(
    valid_ids=st.lists(positive_int_strategy, min_size=1, max_size=5),
    invalid_tokens=st.lists(non_integer_token_strategy, min_size=1, max_size=5),
    data=st.data(),
)
def test_property_12_invalid_reach_id_filtering(
    valid_ids: list[int], invalid_tokens: list[str], data
):
    """Feature: reach-first-subscriptions, Property 12: Invalid reach ID filtering

    Non-integer tokens are skipped, valid integers preserved in order.

    Validates: Requirements 7.1
    """
    # Interleave valid and invalid tokens
    all_tokens: list[str] = []
    valid_strs = [str(v) for v in valid_ids]
    invalid_strs = [t for t in invalid_tokens if t.strip()]  # non-empty invalid tokens

    # Build interleaved list: valid, invalid, valid, invalid, ...
    vi = 0
    ii = 0
    # Use data to decide interleaving order
    order = data.draw(
        st.lists(
            st.booleans(),
            min_size=len(valid_strs) + len(invalid_strs),
            max_size=len(valid_strs) + len(invalid_strs),
        )
    )

    for use_valid in order:
        if use_valid and vi < len(valid_strs):
            all_tokens.append(valid_strs[vi])
            vi += 1
        elif not use_valid and ii < len(invalid_strs):
            all_tokens.append(invalid_strs[ii])
            ii += 1

    # Append remaining
    all_tokens.extend(valid_strs[vi:])
    all_tokens.extend(invalid_strs[ii:])

    raw_value = ", ".join(all_tokens)
    result = _parse_reach_ids(raw_value, "test@example.com")

    # Result should only contain valid integers, deduplicated, in order
    expected = list(dict.fromkeys(valid_ids))
    assert result == expected


# --- Property 13: Deduplication preserves first-occurrence order ---


@settings(max_examples=100)
@given(
    reach_ids=st.lists(positive_int_strategy, min_size=2, max_size=15),
)
def test_property_13_deduplication_preserves_first_occurrence_order(
    reach_ids: list[int],
):
    """Feature: reach-first-subscriptions, Property 13: Deduplication preserves first-occurrence order

    Duplicates removed keeping first occurrence.

    Validates: Requirements 7.2
    """
    raw_value = ", ".join(str(rid) for rid in reach_ids)
    result = _parse_reach_ids(raw_value, "test@example.com")

    # Expected: unique values in first-occurrence order
    expected = list(dict.fromkeys(reach_ids))
    assert result == expected

    # Verify no duplicates in result
    assert len(result) == len(set(result))

    # Verify order matches first occurrence
    for i, val in enumerate(result):
        first_idx = reach_ids.index(val)
        for j in range(i):
            assert reach_ids.index(result[j]) < first_idx
