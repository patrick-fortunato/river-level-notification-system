# Tasks

## Task 1: Add rmin/rmax fields and RunnabilityStatus enum to data model

- [x] 1.1 Add `rmin: float | None = None` and `rmax: float | None = None` fields to `ResolvedReach` dataclass in `src/models.py`
- [x] 1.2 Add `RunnabilityStatus` enum to `src/models.py` with values RUNNABLE, TOO_LOW, TOO_HIGH, UNKNOWN
- [x] 1.3 Add `classify_runnability(flow, rmin, rmax) -> RunnabilityStatus` function to `src/models.py`

## Task 2: Expand GraphQL query and extract rmin/rmax in ReachResolver

- [x] 2.1 Add `rmin` and `rmax` to the GraphQL query string in `ReachResolver._query_reach`
- [x] 2.2 Extract `rmin`/`rmax` from the first gauge entry in the API response and pass to `ResolvedReach` constructor
- [x] 2.3 Handle null/absent `rmin`/`rmax` in API response by setting None on ResolvedReach

## Task 3: Update ReachCache for rmin/rmax serialization

- [x] 3.1 Serialize `rmin` and `rmax` in `ReachCache.put_reach` cache entry dict
- [x] 3.2 Deserialize `rmin` and `rmax` in `ReachCache._entry_to_resolved_reach` with None defaults for missing keys

## Task 4: Render runnability indicator in ReportBuilder

- [x] 4.1 In `_render_reach_entry` for USGS reaches: convert `gauge_entry.flow_level` to float, call `classify_runnability`, and append indicator HTML span with inline CSS
- [x] 4.2 In `_render_reach_entry` for AW fallback reaches: use `resolved.aw_flow_data.reading`, call `classify_runnability`, and append indicator HTML span with inline CSS
- [x] 4.3 Ensure no indicator is rendered when status is UNKNOWN or no flow data exists

## Task 5: Write property-based tests

- [x] 5.1 Write Property 1 test: cache round-trip preserves rmin/rmax in `tests/property/test_reach_cache_props.py`
- [x] 5.2 Write Property 2 test: classification correctness for flow vs range in `tests/property/test_runnability_props.py`
- [x] 5.3 Write Property 3 test: missing data produces Unknown in `tests/property/test_runnability_props.py`
- [x] 5.4 Write Property 4 test: rendered indicator matches runnability status in `tests/property/test_report_builder_props.py`
- [x] 5.5 Write Property 5 test: Unknown status renders no indicator in `tests/property/test_report_builder_props.py`

## Task 6: Write unit tests

- [x] 6.1 Unit test verifying GraphQL query string includes `rmin` and `rmax` fields
- [x] 6.2 Unit test for `flow_level` string-to-float conversion edge cases (non-numeric strings → Unknown)
- [x] 6.3 Unit test verifying indicator HTML uses inline `style=` attributes (not class-based)

## Task 7: Verify all tests pass

- [x] 7.1 Run the full test suite and verify no regressions
