# Tasks

## Task 1: Extend ResolvedReach model with state field

- [x] 1.1 Add `state: str | None = None` field to the `ResolvedReach` dataclass in `src/models.py`

## Task 2: Update ReachResolver to fetch and extract state

- [x] 2.1 Add `state` to the GraphQL query string in `ReachResolver._query_reach` (change `{ river section altname }` to `{ river section altname state }`)
- [x] 2.2 Extract `state` from `reach_data` in `_query_reach` and pass it to the `ResolvedReach` constructor (map null/empty to None)

## Task 3: Update ReachCache to persist state

- [x] 3.1 Update `put_reach` to include `"state": resolved.state` in the cached entry dict
- [x] 3.2 Update `_entry_to_resolved_reach` to read `entry.get("state")` and pass it to `ResolvedReach` constructor

## Task 4: Update ReportBuilder to group reaches by state

- [x] 4.1 Import `STATE_NAMES` from `src.config` in `report_builder.py`
- [x] 4.2 Implement state grouping logic in `build_report`: collect reaches into groups keyed by state, preserving subscriber order within each group
- [x] 4.3 Sort state groups alphabetically by full state name, place "Other" group last
- [x] 4.4 Render state heading (`<h2>` with class `state-heading`) before each group's reach entries
- [x] 4.5 Map state abbreviation to full name via `STATE_NAMES`; use raw abbreviation if not found
- [x] 4.6 Add `.state-heading` CSS styles to the HTML template

## Task 5: Write property-based tests

- [x] 5.1 Write Property 1 test: resolver extracts state from mocked API response (in `tests/property/test_reach_resolver_props.py`)
- [x] 5.2 Write Property 2 test: cache round-trip preserves state field (in `tests/property/test_reach_cache_props.py`)
- [x] 5.3 Write Property 3 test: state groups ordered alphabetically with "Other" last (in `tests/property/test_report_builder_props.py`)
- [x] 5.4 Write Property 4 test: state headings display full state name (in `tests/property/test_report_builder_props.py`)
- [x] 5.5 Write Property 5 test: intra-group subscriber order preserved (in `tests/property/test_report_builder_props.py`)

## Task 6: Write unit tests

- [x] 6.1 Unit test: ResolvedReach defaults state to None when not provided
- [x] 6.2 Unit test: GraphQL query string includes "state" field
- [x] 6.3 Unit test: Legacy cache entry without state key loads with state=None
- [x] 6.4 Unit test: Report with single state produces one heading
- [x] 6.5 Unit test: Report with all None states produces only "Other" heading

## Task 7: Run tests and verify

- [x] 7.1 Run full test suite and verify all existing tests still pass
- [x] 7.2 Run new property tests and verify they pass with 100+ examples each
