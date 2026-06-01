# Implementation Plan: Email Consolidation

## Overview

Consolidate multiple subscriber rows sharing the same email address into a single email with distinct state sections. This introduces an `EmailGrouper` component, extends `ReportBuilder` with a consolidated report method, and modifies the `Pipeline` to use grouped subscribers.

## Tasks

- [x] 1. Create data models and EmailGrouper component
  - [x] 1.1 Add new data models to `src/models.py`
    - Add `StatePreference` dataclass with `state_code: str` and `included_gauges: list[str]`
    - Add `GroupedSubscriber` dataclass with `email: str` and `state_preferences: list[StatePreference]`
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Implement `merge_gauge_lists` helper function in `src/email_grouper.py`
    - If any list is empty, return empty (include all gauges)
    - Otherwise return sorted set union of all lists
    - _Requirements: 2.4, 2.5_

  - [x] 1.3 Implement `EmailGrouper.group_subscribers()` in `src/email_grouper.py`
    - Group subscriber rows by case-insensitive email
    - Preserve original email casing from first occurrence
    - Merge gauge lists for same-state rows using `merge_gauge_lists`
    - Return list of `GroupedSubscriber` objects
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.4 Write property test for case-insensitive email grouping
    - **Property 1: Case-insensitive email grouping**
    - **Validates: Requirements 1.1, 1.3**
    - File: `tests/property/test_email_grouper_props.py`

  - [x] 1.5 Write property test for data preservation during grouping
    - **Property 2: Data preservation during grouping**
    - **Validates: Requirements 1.2**
    - File: `tests/property/test_email_grouper_props.py`

  - [x] 1.6 Write property test for gauge list union with empty-list dominance
    - **Property 5: Gauge list union with empty-list dominance**
    - **Validates: Requirements 2.4, 2.5**
    - File: `tests/property/test_email_grouper_props.py`

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Extend ReportBuilder with consolidated report method
  - [x] 3.1 Implement `ReportBuilder.build_consolidated_report()` in `src/report_builder.py`
    - Accept a `GroupedSubscriber` and `state_gauge_data: dict[str, dict[str, GaugeEntry]]`
    - Produce one state section per unique state that has matching gauge data
    - Each state section starts with a visible heading (full state name)
    - Order state sections alphabetically by full state name
    - Skip states with no matching gauges (no empty sections)
    - Return `None` if all states produce no content
    - Apply gauge inclusion filtering per state using `StatePreference.included_gauges`
    - _Requirements: 2.1, 2.2, 2.3, 3.3, 3.4_

  - [x] 3.2 Write property test for one state section per unique state
    - **Property 3: One state section per unique state**
    - **Validates: Requirements 2.1, 4.1**
    - File: `tests/property/test_consolidated_report_props.py`

  - [x] 3.3 Write property test for state sections ordered alphabetically
    - **Property 4: State sections ordered alphabetically**
    - **Validates: Requirements 2.3**
    - File: `tests/property/test_consolidated_report_props.py`

  - [x] 3.4 Write property test for empty state sections excluded
    - **Property 6: Empty state sections excluded**
    - **Validates: Requirements 3.3**
    - File: `tests/property/test_consolidated_report_props.py`

  - [x] 3.5 Write property test for all-empty states returns None
    - **Property 7: All-empty states returns None**
    - **Validates: Requirements 3.4**
    - File: `tests/property/test_consolidated_report_props.py`

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Modify Pipeline and Config to use consolidated emails
  - [x] 5.1 Add `consolidated_email_subject` field to `Config` in `src/config.py`
    - Add field with default value `"Current River Levels"` for multi-state subscribers
    - _Requirements: 3.2_

  - [x] 5.2 Modify `Pipeline.run()` in `src/pipeline.py` to use `EmailGrouper`
    - After reading subscribers, call `EmailGrouper.group_subscribers()`
    - Iterate over `GroupedSubscriber` objects instead of raw `Subscriber` rows
    - Fetch USGS data for all unique states across grouped subscribers
    - Call `build_consolidated_report()` for each grouped subscriber
    - Use `consolidated_email_subject` for multi-state subscribers
    - Preserve single-state subject line format for single-state subscribers
    - Skip email if `build_consolidated_report()` returns `None`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2_

  - [x] 5.3 Update `EmailSender.send_email()` to accept an optional subject override
    - Allow the pipeline to pass a custom subject line for consolidated emails
    - Maintain backward compatibility when no override is provided
    - _Requirements: 3.2, 4.2_

  - [x] 5.4 Write unit tests for pipeline consolidation behavior
    - Test subject line uses generic format for multi-state subscribers
    - Test subject line uses state-specific format for single-state subscribers
    - Test pipeline sends exactly one email per grouped subscriber
    - Test single-row subscriber produces same delivery behavior as before
    - File: `tests/unit/test_email_consolidation.py`
    - _Requirements: 3.1, 3.2, 4.1, 4.2_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Integration testing
  - [x] 7.1 Write integration tests for the consolidated pipeline
    - End-to-end pipeline run with mocked Sheet/USGS/Gmail verifying consolidated output
    - Verify email count matches unique subscriber count
    - Verify backward compatibility for single-row subscribers
    - File: `tests/integration/test_consolidation_pipeline.py`
    - _Requirements: 1.1, 3.1, 4.1, 4.2_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The project uses Python with Hypothesis for property-based testing (already in requirements.txt)
- Existing test structure under `tests/property/`, `tests/unit/`, and `tests/integration/` is followed
