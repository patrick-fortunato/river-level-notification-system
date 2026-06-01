# Feature: aw-reach-links, Property 2: Mapping Inversion Preserves All Associations
"""Property tests for AWClient mapping inversion.

Verifies that inverting the mapping from reach→gauges to gauge→reaches
preserves all associations: every original triple is represented in the
output, and no associations are lost or duplicated.

**Validates: Requirements 1.3, 1.4**
"""

import requests
from hypothesis import given, settings
from hypothesis import strategies as st

from src.aw_client import AWClient
from src.config import Config
from src.models import Reach


# Strategy for generating reach IDs (positive integers)
reach_ids = st.integers(min_value=1, max_value=100_000)

# Strategy for generating reach names (non-empty strings)
reach_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# Strategy for generating USGS gauge numbers (numeric strings like real gauge IDs)
gauge_numbers = st.text(
    alphabet="0123456789",
    min_size=1,
    max_size=15,
).filter(lambda s: len(s) > 0)


# Strategy for generating a list of (reach_id, reach_name, gauge_number) triples
# We use unique reach_id per triple to match the deduplication behavior
reach_gauge_triples = st.lists(
    st.tuples(reach_ids, reach_names, gauge_numbers),
    min_size=0,
    max_size=30,
)


@settings(max_examples=100)
@given(triples=reach_gauge_triples)
def test_mapping_inversion_preserves_all_associations(
    triples: list[tuple[int, str, str]],
):
    """For any set of (reach_id, reach_name, gauge_number) triples with
    gauge_source='usgs', inverting the mapping produces a result where every
    original triple is represented — each gauge_number key contains a Reach
    with the corresponding reach_id and reach_name, and no associations are
    lost or duplicated.

    **Validates: Requirements 1.3, 1.4**
    """
    config = Config()
    client = AWClient(config, requests.Session())

    # Build input pairs with gauge_source always "usgs" since we're testing
    # the inversion property, not the filtering logic
    reach_gauge_pairs = [
        (reach_id, reach_name, "usgs", gauge_number)
        for reach_id, reach_name, gauge_number in triples
    ]

    # Execute the inversion
    result = client._build_inverted_mapping(reach_gauge_pairs)

    # Compute expected unique associations: for each gauge_number, the set of
    # unique reach_ids that should appear (the method deduplicates by reach_id)
    expected: dict[str, dict[int, str]] = {}
    for reach_id, reach_name, gauge_number in triples:
        if gauge_number not in expected:
            expected[gauge_number] = {}
        # First occurrence of a reach_id for a gauge wins (matches implementation)
        if reach_id not in expected[gauge_number]:
            expected[gauge_number][reach_id] = reach_name

    # Property: every gauge_number from the input is a key in the result
    for gauge_number in expected:
        assert gauge_number in result, (
            f"Gauge number '{gauge_number}' missing from inverted mapping"
        )

    # Property: every unique (reach_id, reach_name) pair for a gauge is present
    for gauge_number, reach_map in expected.items():
        result_reaches = result[gauge_number]
        result_reach_ids = {r.reach_id for r in result_reaches}

        for reach_id, reach_name in reach_map.items():
            assert reach_id in result_reach_ids, (
                f"Reach {reach_id} ('{reach_name}') missing from gauge "
                f"'{gauge_number}' in inverted mapping"
            )
            # Find the matching reach and verify the name
            matching = [r for r in result_reaches if r.reach_id == reach_id]
            assert len(matching) == 1, (
                f"Reach {reach_id} should appear exactly once for gauge "
                f"'{gauge_number}', found {len(matching)}"
            )
            assert matching[0].reach_name == reach_name, (
                f"Reach {reach_id} name mismatch: expected '{reach_name}', "
                f"got '{matching[0].reach_name}'"
            )

    # Property: no extra gauge keys exist beyond what was in the input
    for gauge_number in result:
        assert gauge_number in expected, (
            f"Unexpected gauge number '{gauge_number}' in inverted mapping"
        )

    # Property: no extra reaches exist beyond what was in the input
    for gauge_number, reaches in result.items():
        expected_reach_ids = set(expected[gauge_number].keys())
        result_reach_ids = {r.reach_id for r in reaches}
        assert result_reach_ids == expected_reach_ids, (
            f"Reach IDs mismatch for gauge '{gauge_number}': "
            f"expected {expected_reach_ids}, got {result_reach_ids}"
        )


# Feature: aw-reach-links, Property 3: USGS Gauge Extraction Filters by Source
"""Property test for USGS gauge extraction filtering.

Verifies that the extraction logic includes only gauges where source equals
"usgs" (case-insensitive) and correctly maps their source_id as the USGS
gauge number. Non-USGS gauges are excluded from the resulting mapping.

**Validates: Requirements 1.2**
"""

# Strategy for generating gauge sources — mix of USGS and non-USGS
gauge_sources = st.sampled_from(
    ["usgs", "USGS", "Usgs", "uSgS", "canada", "virtual", "nws", "environment_canada"]
)

# Strategy for generating gauge source IDs (numeric strings)
gauge_source_ids = st.text(
    alphabet="0123456789",
    min_size=1,
    max_size=15,
)

# Strategy for generating tuples of (reach_id, reach_name, gauge_source, gauge_source_id)
mixed_source_tuples = st.lists(
    st.tuples(reach_ids, reach_names, gauge_sources, gauge_source_ids),
    min_size=0,
    max_size=30,
)


@settings(max_examples=100)
@given(tuples=mixed_source_tuples)
def test_usgs_gauge_extraction_filters_by_source(
    tuples: list[tuple[int, str, str, str]],
):
    """For any valid AW API response containing gauges with mixed sources
    (e.g., 'usgs', 'canada', 'virtual'), the extraction logic SHALL include
    only gauges where source equals 'usgs' (case-insensitive) and SHALL
    correctly map their source_id as the USGS gauge number. Non-USGS gauges
    SHALL be excluded from the resulting mapping.

    **Validates: Requirements 1.2**
    """
    config = Config()
    client = AWClient(config, requests.Session())

    # Build input pairs from the generated tuples
    reach_gauge_pairs = [
        (reach_id, reach_name, gauge_source, gauge_source_id)
        for reach_id, reach_name, gauge_source, gauge_source_id in tuples
    ]

    # Execute the inversion/filtering
    result = client._build_inverted_mapping(reach_gauge_pairs)

    # Separate USGS and non-USGS tuples for verification
    usgs_tuples = [
        (reach_id, reach_name, gauge_source, gauge_source_id)
        for reach_id, reach_name, gauge_source, gauge_source_id in tuples
        if gauge_source.lower() == "usgs"
    ]
    non_usgs_tuples = [
        (reach_id, reach_name, gauge_source, gauge_source_id)
        for reach_id, reach_name, gauge_source, gauge_source_id in tuples
        if gauge_source.lower() != "usgs"
    ]

    # Property: All USGS gauge source_ids should appear as keys in the result
    expected_usgs_gauge_ids = {t[3] for t in usgs_tuples}
    for gauge_id in expected_usgs_gauge_ids:
        assert gauge_id in result, (
            f"USGS gauge source_id '{gauge_id}' should be in the result mapping"
        )

    # Property: No non-USGS gauge source_ids should appear as keys
    # (unless they happen to coincide with a USGS gauge source_id)
    non_usgs_only_ids = {t[3] for t in non_usgs_tuples} - expected_usgs_gauge_ids
    for gauge_id in non_usgs_only_ids:
        assert gauge_id not in result, (
            f"Non-USGS gauge source_id '{gauge_id}' should NOT be in the result mapping"
        )

    # Property: Result keys are exactly the set of USGS gauge source_ids
    assert set(result.keys()) == expected_usgs_gauge_ids, (
        f"Result keys {set(result.keys())} should equal USGS gauge IDs "
        f"{expected_usgs_gauge_ids}"
    )

    # Property: Each reach in the result came from a USGS tuple
    usgs_reach_ids_per_gauge: dict[str, set[int]] = {}
    for reach_id, reach_name, gauge_source, gauge_source_id in usgs_tuples:
        if gauge_source_id not in usgs_reach_ids_per_gauge:
            usgs_reach_ids_per_gauge[gauge_source_id] = set()
        usgs_reach_ids_per_gauge[gauge_source_id].add(reach_id)

    for gauge_id, reaches in result.items():
        for reach in reaches:
            assert reach.reach_id in usgs_reach_ids_per_gauge.get(gauge_id, set()), (
                f"Reach {reach.reach_id} in result for gauge '{gauge_id}' "
                f"did not come from a USGS source tuple"
            )

    # Property: No reaches from non-USGS sources appear in the result
    non_usgs_associations: set[tuple[str, int]] = {
        (gauge_source_id, reach_id)
        for reach_id, reach_name, gauge_source, gauge_source_id in non_usgs_tuples
    }
    for gauge_id, reaches in result.items():
        for reach in reaches:
            assert (gauge_id, reach.reach_id) not in non_usgs_associations or (
                gauge_id in expected_usgs_gauge_ids
                and reach.reach_id in usgs_reach_ids_per_gauge.get(gauge_id, set())
            ), (
                f"Reach {reach.reach_id} for gauge '{gauge_id}' appears to come "
                f"from a non-USGS source"
            )
