# Feature: email-consolidation, Property 1: Case-insensitive email grouping
"""Property tests for the EmailGrouper component.

Property 1: For any list of subscriber rows, the number of groups produced
by the EmailGrouper SHALL equal the number of case-insensitively unique
email addresses in the input.

Validates: Requirements 1.1, 1.3
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.email_grouper import EmailGrouper
from src.models import Subscriber


# Strategy for generating valid email local parts
email_local_strategy = st.from_regex(r"[a-zA-Z][a-zA-Z0-9.]{1,15}", fullmatch=True)

# Strategy for generating valid email domains
email_domain_strategy = st.from_regex(r"[a-z]{3,10}\.(com|org|net)", fullmatch=True)

# Strategy for generating email addresses
email_strategy = st.builds(
    lambda local, domain: f"{local}@{domain}",
    local=email_local_strategy,
    domain=email_domain_strategy,
)

# Strategy for generating state codes
state_code_strategy = st.sampled_from(["OR", "WA", "CA", "ID", "MT", "NV", ""])

# Strategy for generating gauge inclusion lists
gauge_list_strategy = st.lists(
    st.from_regex(r"[0-9]{5,10}", fullmatch=True),
    min_size=0,
    max_size=5,
)

# Strategy for generating a Subscriber row
subscriber_strategy = st.builds(
    Subscriber,
    email=email_strategy,
    included_gauges=gauge_list_strategy,
    state_code=state_code_strategy,
)


def apply_random_case(email: str, data) -> str:
    """Apply random casing to an email address."""
    return "".join(
        c.upper() if data.draw(st.booleans()) else c.lower() for c in email
    )


# --- Property 1: Case-insensitive email grouping ---


@settings(max_examples=100)
@given(subscribers=st.lists(subscriber_strategy, min_size=0, max_size=20))
def test_group_count_equals_case_insensitive_unique_emails(
    subscribers: list[Subscriber],
):
    """**Validates: Requirements 1.1, 1.3**

    For any list of subscriber rows, the number of groups produced by the
    EmailGrouper SHALL equal the number of case-insensitively unique email
    addresses in the input.
    """
    grouper = EmailGrouper()
    groups = grouper.group_subscribers(subscribers)

    # Count case-insensitively unique emails in the input
    unique_emails = {sub.email.lower() for sub in subscribers}

    assert len(groups) == len(unique_emails)


@settings(max_examples=100)
@given(data=st.data())
def test_case_variants_of_same_email_produce_single_group(data):
    """**Validates: Requirements 1.1, 1.3**

    When multiple subscriber rows have email addresses differing only in
    letter case, the EmailGrouper SHALL treat them as the same subscriber
    and produce a single group.
    """
    # Generate a base email
    base_email = data.draw(email_strategy)

    # Generate multiple case variants of the same email
    num_variants = data.draw(st.integers(min_value=2, max_value=5))
    subscribers = []
    for _ in range(num_variants):
        case_variant = apply_random_case(base_email, data)
        sub = Subscriber(
            email=case_variant,
            included_gauges=data.draw(gauge_list_strategy),
            state_code=data.draw(state_code_strategy),
        )
        subscribers.append(sub)

    grouper = EmailGrouper()
    groups = grouper.group_subscribers(subscribers)

    # All variants should collapse into a single group
    assert len(groups) == 1
    # The group email should match the first occurrence (case-preserved)
    assert groups[0].email == subscribers[0].email


# --- Property 2: Data preservation during grouping ---
# Feature: email-consolidation, Property 2: Data preservation during grouping


@settings(max_examples=100)
@given(subscribers=st.lists(subscriber_strategy, min_size=0, max_size=20))
def test_total_state_preferences_equals_unique_email_state_pairs(
    subscribers: list[Subscriber],
):
    """**Validates: Requirements 1.2**

    For any list of subscriber rows, after grouping, the total number of
    StatePreference entries across all groups SHALL equal the number of
    unique (email_lower, state_code) pairs in the input.
    """
    grouper = EmailGrouper()
    groups = grouper.group_subscribers(subscribers)

    # Count total StatePreference entries across all groups
    total_state_prefs = sum(len(g.state_preferences) for g in groups)

    # Count unique (email_lower, state_code) pairs in the input
    unique_pairs = {(sub.email.lower(), sub.state_code) for sub in subscribers}

    assert total_state_prefs == len(unique_pairs)


@settings(max_examples=100)
@given(subscribers=st.lists(subscriber_strategy, min_size=1, max_size=20))
def test_each_row_state_code_appears_in_correct_group(
    subscribers: list[Subscriber],
):
    """**Validates: Requirements 1.2**

    For any list of subscriber rows, after grouping, each original row's
    state code SHALL appear in exactly one group's state preferences —
    specifically in the group corresponding to that row's email address.
    """
    grouper = EmailGrouper()
    groups = grouper.group_subscribers(subscribers)

    # Build a lookup: email_lower -> GroupedSubscriber
    group_by_email = {g.email.lower(): g for g in groups}

    for sub in subscribers:
        email_key = sub.email.lower()
        # The group for this email must exist
        assert email_key in group_by_email

        group = group_by_email[email_key]
        # The state code from this row must appear in the group's state preferences
        state_codes_in_group = [sp.state_code for sp in group.state_preferences]
        assert sub.state_code in state_codes_in_group


# --- Property 5: Gauge list union with empty-list dominance ---
# Feature: email-consolidation, Property 5: Gauge list union with empty-list dominance


@settings(max_examples=100)
@given(
    gauge_lists=st.lists(
        gauge_list_strategy,
        min_size=1,
        max_size=10,
    ).filter(lambda gls: any(len(gl) == 0 for gl in gls))
)
def test_merge_gauge_lists_empty_list_dominance(gauge_lists: list[list[str]]):
    """**Validates: Requirements 2.4, 2.5**

    For any set of gauge inclusion lists where at least one list is empty,
    the merged result SHALL be empty (include all gauges).
    """
    from src.email_grouper import merge_gauge_lists

    result = merge_gauge_lists(gauge_lists)

    # If any list is empty, the merged result must be empty
    assert result == []


@settings(max_examples=100)
@given(
    gauge_lists=st.lists(
        st.lists(
            st.from_regex(r"[0-9]{5,10}", fullmatch=True),
            min_size=1,
            max_size=5,
        ),
        min_size=1,
        max_size=10,
    )
)
def test_merge_gauge_lists_set_union_when_no_empty(gauge_lists: list[list[str]]):
    """**Validates: Requirements 2.4, 2.5**

    For any set of gauge inclusion lists where no list is empty,
    the merged result SHALL be the sorted set union of all lists.
    """
    from src.email_grouper import merge_gauge_lists

    result = merge_gauge_lists(gauge_lists)

    # No list is empty, so result should be the sorted set union
    expected = sorted(set(gauge for gl in gauge_lists for gauge in gl))
    assert result == expected
