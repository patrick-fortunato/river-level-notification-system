# Implementation Plan: AW Reach Links

## Overview

Add American Whitewater reach links to gauge entries in notification emails. Implementation introduces the `Reach` data model, an `AWClient` for querying AW's GraphQL API, a `ReachCache` for TTL-based local JSON caching, and integrates the reach mapping into the existing `Pipeline` and `ReportBuilder` components.

## Tasks

- [x] 1. Add Reach data model and Config extensions
  - [x] 1.1 Add the `Reach` dataclass to `src/models.py`
    - Add `Reach` dataclass with `reach_id: int` and `reach_name: str` fields
    - Add `url` property that returns the AW reach URL using the pattern `https://www.americanwhitewater.org/content/River/view/river-detail/{reach_id}/main`
    - Add `ReachMapping` type alias: `dict[str, list[Reach]]`
    - _Requirements: 3.3_

  - [x] 1.2 Add AW configuration fields to `src/config.py`
    - Add `aw_graphql_url: str = "https://www.americanwhitewater.org/graphql"`
    - Add `aw_reach_cache_file: str = "aw_reach_cache.json"`
    - Add `aw_cache_ttl_seconds: int = 604800` (7 days)
    - Add `aw_request_timeout: int = 30`
    - Add `aw_request_delay: float = 0.5`
    - _Requirements: 2.2, 2.3_

- [x] 2. Implement AWClient
  - [x] 2.1 Create `src/aw_client.py` with the `AWClient` class
    - Implement `AWClientError` exception class
    - Implement `__init__` accepting `Config` and `requests.Session`
    - Implement `fetch_reach_mapping(state_codes)` that orchestrates the full fetch flow
    - Implement `_fetch_reaches_for_state(state_code)` to get reach IDs from AW's state index
    - Implement `_fetch_gauges_for_reach(reach_id)` to query AW GraphQL for gauge associations
    - Implement `_build_inverted_mapping(reach_gauge_pairs)` to invert reach→gauge into gauge→reaches
    - Filter only gauges where source is "usgs" when building the mapping
    - Add request delay between API calls using `config.aw_request_delay`
    - Raise `AWClientError` on network errors, HTTP errors, and malformed responses
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Write property test for mapping inversion (Property 2)
    - **Property 2: Mapping Inversion Preserves All Associations**
    - Generate random lists of (reach_id, reach_name, gauge_number) triples
    - Verify that inverting produces a mapping where every original triple is represented
    - File: `tests/property/test_aw_client_props.py`
    - **Validates: Requirements 1.3, 1.4**

  - [x] 2.3 Write property test for USGS gauge extraction (Property 3)
    - **Property 3: USGS Gauge Extraction Filters by Source**
    - Generate random API response structures with mixed gauge sources ("usgs", "canada", "virtual")
    - Verify only "usgs" gauges are included and non-USGS gauges are excluded
    - File: `tests/property/test_aw_client_props.py`
    - **Validates: Requirements 1.2**

- [x] 3. Implement ReachCache
  - [x] 3.1 Create `src/reach_cache.py` with the `ReachCache` class
    - Implement `__init__` accepting `Config`
    - Implement `get_mapping(state_codes, aw_client)` that returns cached or fresh mapping
    - Implement `_is_cache_valid()` checking file existence and TTL expiration
    - Implement `_read_cache()` deserializing JSON to ReachMapping (return None on corrupt/missing)
    - Implement `_write_cache(mapping)` serializing mapping with timestamp to JSON
    - Handle corrupt cache files by treating as expired and triggering fresh fetch
    - Return `None` when fetch fails and no valid cache exists
    - Return cached mapping with warning log when fetch fails but valid cache exists
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.2 Write property test for serialization round-trip (Property 1)
    - **Property 1: Serialization Round-Trip**
    - Generate random ReachMapping instances with varying gauge counts, reach counts, ID ranges, unicode names
    - Verify serialize then deserialize produces equivalent mapping
    - File: `tests/property/test_reach_cache_props.py`
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [x] 3.3 Write property test for cache TTL validity (Property 6)
    - **Property 6: Cache TTL Validity**
    - Generate random timestamps and TTL durations
    - Verify cache is valid iff elapsed time < TTL, expired when elapsed >= TTL
    - File: `tests/property/test_reach_cache_props.py`
    - **Validates: Requirements 2.2, 2.3**

- [x] 4. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Extend ReportBuilder with reach link rendering
  - [x] 5.1 Add `_render_reach_links(reaches)` method to `ReportBuilder`
    - Render a list of Reach objects as clickable HTML anchor tags
    - Each link uses reach_name as link text and Reach.url as href
    - Add CSS styling for reach links in the email template
    - _Requirements: 3.2, 3.3_

  - [x] 5.2 Update `_render_gauge_entry` to accept and render reach links
    - Add optional `reach_mapping` parameter to `_render_gauge_entry`
    - Look up gauge_number in reach_mapping and call `_render_reach_links` if reaches exist
    - Render no reach link HTML when mapping is None or gauge has no entries
    - _Requirements: 3.1, 3.4, 3.5_

  - [x] 5.3 Update `build_consolidated_report` to accept and pass reach mapping
    - Add optional `reach_mapping: dict[str, list[Reach]] | None = None` parameter
    - Pass reach_mapping through to `_render_gauge_entry` calls
    - _Requirements: 3.1, 4.2_

  - [x] 5.4 Write property test for reach link count (Property 4)
    - **Property 4: Reach Link Count Matches Mapping**
    - Generate random gauge entries paired with random reach mappings (0-5 reaches per gauge)
    - Verify rendered HTML contains exactly N reach link elements for N reaches
    - File: `tests/property/test_reach_report_props.py`
    - **Validates: Requirements 3.1, 3.4, 3.5**

  - [x] 5.5 Write property test for reach link format (Property 5)
    - **Property 5: Reach Links Have Correct Format**
    - Generate random Reach objects with varying IDs and names (including unicode)
    - Verify rendered anchor tag has correct href and visible text
    - File: `tests/property/test_reach_report_props.py`
    - **Validates: Requirements 3.2, 3.3**

- [x] 6. Integrate reach mapping into Pipeline
  - [x] 6.1 Add `_load_reach_mapping` method to `Pipeline`
    - Instantiate `ReachCache` and `AWClient` using pipeline config and a requests session
    - Collect unique state codes from grouped subscribers
    - Call `ReachCache.get_mapping(state_codes, aw_client)`
    - Log the number of gauge-to-reach associations loaded
    - Return `None` on failure (pipeline proceeds without links)
    - _Requirements: 4.1, 4.3, 4.4, 4.5_

  - [x] 6.2 Update `Pipeline.run()` to load and pass reach mapping
    - Call `_load_reach_mapping` after fetching gauge data but before building reports
    - Pass reach_mapping to `report_builder.build_consolidated_report()` calls
    - Log warning if reach mapping is unavailable, do not halt pipeline
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 7. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Unit and integration tests
  - [x] 8.1 Write unit tests for AWClient error handling
    - Test `AWClientError` raised on network failure (mock connection error)
    - Test `AWClientError` raised on HTTP 4xx/5xx responses
    - Test `AWClientError` raised on malformed JSON response
    - File: `tests/unit/test_aw_reach_links.py`
    - _Requirements: 1.5_

  - [x] 8.2 Write unit tests for ReachCache edge cases
    - Test cache returns None on corrupt file and triggers fresh fetch
    - Test cache uses valid cached mapping when fetch fails
    - Test cache treats expired file as needing refresh
    - File: `tests/unit/test_aw_reach_links.py`
    - _Requirements: 2.2, 2.3, 2.5_

  - [x] 8.3 Write unit tests for Pipeline graceful degradation
    - Test pipeline proceeds without reach links when mapping unavailable
    - Test pipeline uses cached mapping on fetch failure with warning log
    - Test gauge entry renders without reach HTML when mapping is None
    - File: `tests/unit/test_aw_reach_links.py`
    - _Requirements: 4.3, 4.4_

  - [x] 8.4 Write integration tests for reach pipeline
    - Test cache write and read cycle with real filesystem (tmp directory)
    - Test full pipeline run with mocked AW API returning reach data
    - File: `tests/integration/test_reach_pipeline.py`
    - _Requirements: 2.1, 4.1, 4.2_

- [x] 9. Update documentation and version
  - [x] 9.1 Update `README.md` with AW reach links feature
    - Add "American Whitewater reach links" to the Features list
    - Add `aw_graphql_url`, `aw_reach_cache_file`, `aw_cache_ttl_seconds` to the Configuration table
    - Add `src/aw_client.py` and `src/reach_cache.py` to the Project Structure section
    - Add a brief note about the `aw_reach_cache.json` file and that it's auto-generated
    - Add `aw_reach_cache.json` mention in the Security section if appropriate (no secrets, but auto-generated)
    - _Requirements: 4.1_

  - [x] 9.2 Bump minor version in `src/__version__.py`
    - Update `__version__` from `"0.2.0"` to `"0.3.0"`

- [x] 10. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The pipeline gracefully degrades: AW failures never halt email delivery
