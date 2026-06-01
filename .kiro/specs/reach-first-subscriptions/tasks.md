# Implementation Plan: Reach-First Subscriptions

## Overview

Replace the gauge-first subscription model with a reach-first approach. Subscribers specify AW reach IDs instead of USGS gauge numbers and states. The system resolves reaches via the AW API, fetches only needed USGS gauges, and delivers emails organized by reach. This is a breaking change requiring version bump to 1.0.0.

## Tasks

- [x] 1. Update data models and configuration
  - [x] 1.1 Add new data models (ReachSubscriber, ResolvedReach) to `src/models.py`
    - Add `ReachSubscriber` dataclass with `email: str` and `reach_ids: list[int]`
    - Add `ResolvedReach` dataclass with `reach_id: int`, `reach_name: str`, `gauge_id: str | None`, and `aw_url` property
    - Keep `GaugeEntry` and `RunSummary` unchanged
    - Remove `Subscriber`, `StatePreference`, `GroupedSubscriber`, `Reach`, and `ReachMapping` type alias
    - _Requirements: 5.4, 9.1_

  - [x] 1.2 Update `src/config.py` to remove state-based fields
    - Remove `usgs_state_code` field
    - Remove `email_subject` template with `{state_name}` placeholder
    - Remove `consolidated_email_subject`
    - Add single `email_subject: str = "Current River Levels"`
    - Remove `state_name` property
    - Keep `STATE_NAMES` dict only if needed elsewhere; otherwise remove
    - _Requirements: 5.1, 5.2_

  - [x] 1.3 Update `src/__version__.py` to `"1.0.0"`
    - _Requirements: 9.1_

- [x] 2. Rewrite SheetReader for new 2-column format
  - [x] 2.1 Rewrite `src/sheet_reader.py` for Email + Reach IDs columns
    - Change `EXPECTED_HEADER_COL_B` from `"include gauges"` to `"reach ids"`
    - Remove `EXPECTED_HEADER_COL_C` and all column C logic
    - Implement `get_subscribers()` returning `list[ReachSubscriber]`
    - Parse comma-separated integers from column B with whitespace trimming
    - Skip rows with blank email (column A)
    - Skip rows with empty Reach IDs column (log warning)
    - Skip non-integer values in reach IDs (log warning with email context)
    - Deduplicate reach IDs preserving first-occurrence order
    - Update `validate_structure()` to check for "Email" (A) and "Reach IDs" (B) only
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 7.1, 7.2, 7.3_

  - [x] 2.2 Write property tests for SheetReader parsing (Properties 1, 2, 3, 12, 13)
    - **Property 1: Reach ID parsing round-trip** — for any list of positive integers formatted as comma-separated with arbitrary whitespace, parsing produces the same integers
    - **Property 2: Blank email filtering** — rows with blank/whitespace emails are excluded
    - **Property 3: Empty reach IDs filtering** — rows with empty Reach IDs are excluded
    - **Property 12: Invalid reach ID filtering** — non-integer tokens are skipped, valid integers preserved in order
    - **Property 13: Deduplication preserves first-occurrence order** — duplicates removed keeping first occurrence
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3**

- [x] 3. Checkpoint - Ensure models and SheetReader work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement ReachResolver (new component)
  - [x] 4.1 Create `src/reach_resolver.py` with ReachResolver class
    - Constructor takes `Config`, `requests.Session`, and `ReachCache`
    - Implement `resolve_reaches(reach_ids: list[int]) -> dict[int, ResolvedReach]`
    - Check cache first for each reach ID (use `ReachCache.get_reach`)
    - Query AW API for cache misses using existing `AWClient._fetch_gauges_for_reach` pattern
    - Also query reach name via AW GraphQL `getGaugeInformationForReachID` (extracts river, section, altname)
    - Implement `_extract_reach_name(reach_data)` combining river, section, altname
    - Implement `_extract_usgs_gauge(gauges)` returning first gauge with source="usgs"
    - Update cache with fresh results via `ReachCache.put_reach`
    - Mark unreachable reaches as unresolvable (log error, do not halt)
    - Use stale cache as fallback when API is unreachable
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.4_

  - [x] 4.2 Write property tests for ReachResolver helpers (Properties 4, 5)
    - **Property 4: Reach name formatting** — for any combination of river/section/altname, produces correct joined string
    - **Property 5: First USGS gauge extraction** — returns source_id of first dict with source="usgs", or None
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5**

- [x] 5. Update ReachCache for per-reach entries
  - [x] 5.1 Rewrite `src/reach_cache.py` for per-reach caching
    - Replace state-based `get_mapping` with `get_reach(reach_id: int) -> ResolvedReach | None`
    - Add `put_reach(reach_id: int, resolved: ResolvedReach) -> None`
    - Add `get_stale_reach(reach_id: int) -> ResolvedReach | None` for fallback
    - Change cache JSON format to `{"reaches": {"1493": {"reach_name": "...", "gauge_id": "...", "cached_at": "..."}}}` 
    - Keep TTL-based expiration logic (7 days)
    - Handle corrupt/unreadable cache gracefully (treat as miss)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 5.2 Write property test for ReachCache (Property 11)
    - **Property 11: Cache serialization round-trip** — writing a ResolvedReach and reading it back produces equivalent object
    - **Validates: Requirements 6.1**

- [x] 6. Update USGSFetcher for gauge-ID-based fetching
  - [x] 6.1 Add `fetch_gauges_by_ids` method to `src/usgs_fetcher.py`
    - Implement `fetch_gauges_by_ids(gauge_ids: list[str]) -> dict[str, GaugeEntry]`
    - Build URL with `sites={comma_separated_ids}` parameter instead of `stateCd=`
    - Reuse existing `_parse_response` logic
    - Apply retry logic (same as `fetch_all_state_gauges`)
    - Handle per-gauge errors gracefully (skip failed gauges, do not halt)
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 6.2 Write property test for gauge ID deduplication (Property 6)
    - **Property 6: Gauge ID deduplication** — unique non-None gauge_ids from resolved reaches equals set passed to fetcher
    - **Validates: Requirements 3.2**

- [x] 7. Checkpoint - Ensure resolver, cache, and fetcher work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Rewrite ReportBuilder for reach-first layout
  - [x] 8.1 Rewrite `src/report_builder.py` for reach-first email layout
    - Replace `build_report` signature to accept `ReachSubscriber`, `dict[int, ResolvedReach]`, `dict[str, GaugeEntry]`
    - Remove `build_consolidated_report` method entirely
    - Iterate subscriber's `reach_ids` in order
    - For each reach: render reach name as primary heading linked to AW URL
    - When gauge data available: show flow reading (cfs) and formatted timestamp
    - When USGS gauge associated: show gauge number as secondary link to USGS page
    - When no gauge: show "No gauge data available" text
    - Preserve existing `_format_reading_datetime` helper
    - Return None if no reaches could be rendered
    - Update footer to use version from `__version__`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 9.2_

  - [x] 8.2 Write property tests for ReportBuilder (Properties 7, 8, 9, 10)
    - **Property 7: Report contains AW link for every reach** — rendered HTML contains anchor to correct AW URL
    - **Property 8: Report contains flow data when gauge data present** — HTML contains flow level and timestamp
    - **Property 9: Report contains USGS link when gauge present** — HTML contains USGS monitoring page link
    - **Property 10: Report preserves subscriber reach order** — reach entries appear in subscriber's specified order
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5**

- [x] 9. Rewrite Pipeline for simplified orchestration
  - [x] 9.1 Rewrite `src/pipeline.py` for reach-first flow
    - Remove imports of `EmailGrouper`, `GroupedSubscriber`, `StatePreference`, `Subscriber`
    - Import `ReachSubscriber`, `ResolvedReach`, `ReachResolver`
    - Implement new `run()` flow: validate → read subscribers → resolve reaches → fetch USGS → build reports → send emails → summary
    - Collect all unique reach IDs across subscribers
    - Use ReachResolver to resolve reaches
    - Collect unique gauge IDs from resolved reaches (deduplicate)
    - Use USGSFetcher.fetch_gauges_by_ids for targeted fetch
    - Build per-subscriber reports using ReportBuilder
    - Skip subscribers where all reach resolutions fail (log reason)
    - Continue on individual email send failures
    - Use single `email_subject` from config (no state-based subject logic)
    - Remove `_determine_subject`, `_fetch_gauge_data_for_grouped_subscribers`, `_load_reach_mapping` methods
    - Produce RunSummary with correct counts
    - _Requirements: 5.1, 5.4, 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.2 Write property test for Pipeline run summary (Property 14)
    - **Property 14: Run summary counts consistency** — `emails_sent + emails_failed + subscribers_skipped == total_subscribers`
    - **Validates: Requirements 8.4**

- [x] 10. Checkpoint - Ensure pipeline orchestration works end-to-end
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Remove dead code and update validator
  - [x] 11.1 Delete `src/email_grouper.py`
    - _Requirements: 5.4_

  - [x] 11.2 Update `src/validator.py` to remove state-based validation
    - Remove state code validation
    - Update sheet structure validation to expect "Email" and "Reach IDs" headers
    - Remove column C validation
    - _Requirements: 5.2, 5.3_

  - [x] 11.3 Remove old tests that reference deleted models/components
    - Remove or rewrite `tests/property/test_email_grouper_props.py`
    - Remove or rewrite `tests/property/test_consolidated_report_props.py`
    - Remove or rewrite `tests/property/test_email_subject_bug_condition.py`
    - Remove or rewrite `tests/property/test_email_subject_preservation.py`
    - Remove or rewrite `tests/unit/test_email_consolidation.py`
    - Update `tests/unit/test_aw_client.py` and `tests/unit/test_aw_reach_links.py` if they reference removed models
    - Update `tests/integration/test_consolidation_pipeline.py` and `tests/integration/test_pipeline_integration.py`
    - Update `tests/property/test_sheet_parsing_props.py` for new SheetReader interface
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 12. Documentation and version bump
  - [x] 12.1 Update `README.md` to reflect reach-first model
    - Update intro paragraph to describe reach-first subscriptions (AW reach IDs, not gauges/states)
    - Update Features list: replace "Configurable state" and "Personalized reports" with reach-first descriptions; update "American Whitewater reach links" entry
    - Update Google Sheet Structure section: new 2-column table (Email + Reach IDs), remove State and Include Gauges columns
    - Update Configuration table: remove `usgs_state_code`, update `email_subject` to `"Current River Levels"`, remove `consolidated_email_subject`
    - Update Project Structure: add `reach_resolver.py`, note changes to `reach_cache.py`, remove `email_grouper.py`
    - Update "Who This Is For" section to emphasize reach-based subscriptions for whitewater paddlers
    - _Requirements: 9.1_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The existing `AWClient._fetch_gauges_for_reach` method already works against the real AW GraphQL API and should be reused/adapted in ReachResolver
- The `USGSFetcher._parse_response` method is reusable for the new `fetch_gauges_by_ids` method
- Version bump from 0.3.0 → 1.0.0 reflects the breaking spreadsheet schema change
