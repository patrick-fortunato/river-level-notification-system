# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Hardcoded State in Email Subject
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to subscribers with a non-default `state_code` (e.g., "WA", "CA", "TX") where `effective_state != globalConfig.usgs_state_code`
  - Create test file `tests/property/test_email_subject_bug_condition.py`
  - Use Hypothesis to generate subscribers with `state_code` drawn from `STATE_NAMES` keys excluding the global default ("OR")
  - Mock the Gmail API service to capture the constructed MIME message subject
  - Call `send_email(recipient, html_body)` on unfixed code (no `state_code` param yet)
  - Assert that the email subject contains `STATE_NAMES[subscriber.state_code]` (e.g., "Washington" for "WA")
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (subject always contains "Oregon" regardless of subscriber state — this proves the bug exists)
  - Document counterexamples found (e.g., subscriber with state_code="WA" gets subject "Current Oregon River Levels" instead of "Current Washington River Levels")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Default State Subscribers Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Create test file `tests/property/test_email_subject_preservation.py`
  - Observe: On unfixed code, `send_email("user@example.com", body)` with global default "OR" produces subject "Current Oregon River Levels"
  - Observe: On unfixed code, any subscriber with empty `state_code` or `state_code` matching global default gets subject with global default state name
  - Write property-based test using Hypothesis: for all valid state codes used as the global default, when `send_email()` is called without a state override (or with state matching global), the subject contains `STATE_NAMES[global_state_code]`
  - Mock the Gmail API service to capture the MIME message subject
  - Generate random global state codes from `STATE_NAMES` keys
  - Assert subject equals `Config.email_subject.format(state_name=STATE_NAMES[global_state_code])`
  - Verify test passes on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Fix for hardcoded state in email subject

  - [x] 3.1 Implement the fix
    - In `src/email_sender.py`: Add `state_code: str | None = None` parameter to `send_email()` method signature
    - In `src/email_sender.py`: Import `STATE_NAMES` from `src.config`
    - In `src/email_sender.py`: Before formatting the subject, resolve the state name: if `state_code` is provided, use `STATE_NAMES.get(state_code, state_code)`; otherwise fall back to `self._config.state_name`
    - In `src/email_sender.py`: Replace `state_name=self._config.state_name` with the resolved state name value
    - In `src/pipeline.py`: Change the call from `email_sender.send_email(subscriber.email, report)` to `email_sender.send_email(subscriber.email, report, state_code=effective_state)`
    - _Bug_Condition: isBugCondition(subscriber, globalConfig) where effective_state != globalConfig.usgs_state_code_
    - _Expected_Behavior: Email subject uses STATE_NAMES[effective_state] for the subscriber's state_
    - _Preservation: Subscribers with empty state_code or state_code matching global default get same subject as before_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Hardcoded State in Email Subject
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (subject reflects subscriber's state)
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1: `pytest tests/property/test_email_subject_bug_condition.py`
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Default State Subscribers Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2: `pytest tests/property/test_email_subject_preservation.py`
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tests/`
  - Ensure all existing tests pass (no regressions in other modules)
  - Ensure both new property tests pass
  - Ask the user if questions arise
