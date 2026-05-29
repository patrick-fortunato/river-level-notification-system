# Hardcoded State in Email Subject Bugfix Design

## Overview

The `EmailSender.send_email()` method always formats the email subject using the global `Config.state_name` property, which resolves from the global `usgs_state_code` (default "OR" → "Oregon"). The pipeline already determines each subscriber's effective state code but never passes it to the email sender. The fix adds a `state_code` parameter to `send_email()` so the subject line reflects the subscriber's actual state.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — a subscriber has a per-subscriber `state_code` override that differs from the global default, yet the email subject always shows the global default state name
- **Property (P)**: The desired behavior — the email subject uses the subscriber's effective state name (resolved from their `state_code`)
- **Preservation**: Existing behavior for subscribers without a state override (empty `state_code`) must remain unchanged — they continue to receive emails with the global default state name in the subject
- **`send_email()`**: The method in `src/email_sender.py` that constructs and sends the MIME email via Gmail API
- **`effective_state`**: The state code resolved per subscriber in `src/pipeline.py` — either the subscriber's override or the global default
- **`STATE_NAMES`**: The mapping in `src/config.py` from two-letter state codes to full state names

## Bug Details

### Bug Condition

The bug manifests when a subscriber has a per-subscriber `state_code` override that differs from the global `usgs_state_code`. The `send_email()` method formats the subject using `self._config.state_name`, which always resolves from the global config rather than the subscriber's effective state.

**Formal Specification:**
```
FUNCTION isBugCondition(subscriber, globalConfig)
  INPUT: subscriber of type Subscriber, globalConfig of type Config
  OUTPUT: boolean

  effective_state := subscriber.state_code IF subscriber.state_code != ""
                     ELSE globalConfig.usgs_state_code

  RETURN effective_state != globalConfig.usgs_state_code
END FUNCTION
```

### Examples

- Subscriber with `state_code = "WA"`, global default `"OR"`: Email subject says "Current Oregon River Levels" instead of "Current Washington River Levels"
- Subscriber with `state_code = "CA"`, global default `"OR"`: Email subject says "Current Oregon River Levels" instead of "Current California River Levels"
- Subscriber with `state_code = "TX"`, global default `"OR"`: Email subject says "Current Oregon River Levels" instead of "Current Texas River Levels"
- Subscriber with `state_code = ""` (empty), global default `"OR"`: Email subject correctly says "Current Oregon River Levels" (not a bug case)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Subscribers with an empty `state_code` must continue to receive emails with the global default state name in the subject
- The `email_subject` template format string must continue to use the `{state_name}` placeholder pattern
- Subscribers whose `state_code` matches the global default must receive the same subject as before
- Email body content, recipient addressing, rate limiting, retry logic, and authentication must remain unchanged
- The `Config.state_name` property must continue to work for other uses in the system

**Scope:**
All inputs where the subscriber's effective state equals the global default state should be completely unaffected by this fix. This includes:
- Subscribers with empty `state_code` (fall through to global default)
- Subscribers whose `state_code` explicitly matches the global `usgs_state_code`
- All non-subject-line aspects of email construction and delivery

## Hypothesized Root Cause

Based on the bug description, the root cause is clear and singular:

1. **Missing parameter propagation**: The `send_email()` method in `src/email_sender.py` (line ~120) formats the subject as:
   ```python
   message["Subject"] = self._config.email_subject.format(
       state_name=self._config.state_name
   )
   ```
   This always uses `self._config.state_name`, which resolves from the global `usgs_state_code`. The pipeline in `src/pipeline.py` (line ~119) already computes `effective_state` per subscriber but only uses it for gauge data lookup — it never passes it to `send_email()`.

2. **No state parameter on `send_email()`**: The method signature is `send_email(self, recipient: str, html_body: str) -> bool` with no way to specify which state to use for subject formatting.

## Correctness Properties

Property 1: Bug Condition - Email subject reflects subscriber's effective state

_For any_ subscriber where the bug condition holds (subscriber has a non-empty `state_code` that differs from the global default), the fixed `send_email()` function SHALL format the email subject using the full state name corresponding to the subscriber's `state_code`.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Default state subscribers unchanged

_For any_ subscriber where the bug condition does NOT hold (subscriber has empty `state_code` or `state_code` matching the global default), the fixed code SHALL produce an email with the same subject as the original code, preserving the global default state name in the subject line.

**Validates: Requirements 3.1, 3.3**

## Fix Implementation

### Changes Required

**File**: `src/email_sender.py`

**Function**: `send_email()`

**Specific Changes**:
1. **Add `state_code` parameter**: Change the method signature to `send_email(self, recipient: str, html_body: str, state_code: str | None = None) -> bool` — the optional parameter defaults to `None` for backward compatibility
2. **Resolve state name from parameter**: When `state_code` is provided, look up the full state name from `STATE_NAMES`; otherwise fall back to `self._config.state_name`
3. **Format subject with resolved state name**: Replace `state_name=self._config.state_name` with the resolved value

**File**: `src/pipeline.py`

**Function**: `Pipeline.run()` (the subscriber loop at ~line 119)

**Specific Changes**:
4. **Pass effective state to `send_email()`**: Change the call from `email_sender.send_email(subscriber.email, report)` to `email_sender.send_email(subscriber.email, report, state_code=effective_state)`

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm that the root cause is the hardcoded `self._config.state_name` in subject formatting.

**Test Plan**: Write tests that call `send_email()` with subscribers having different state codes and assert the email subject contains the correct state name. Run these tests on the UNFIXED code to observe failures.

**Test Cases**:
1. **Non-default state subscriber**: Call `send_email()` for a subscriber with `state_code="WA"` and verify subject contains "Washington" (will fail on unfixed code — subject will say "Oregon")
2. **Multiple different states**: Send emails for subscribers with "WA", "CA", "TX" and verify each subject is different (will fail on unfixed code — all will say "Oregon")
3. **Pipeline integration**: Run the pipeline loop with mixed-state subscribers and capture the subjects (will fail on unfixed code)

**Expected Counterexamples**:
- Email subject always contains "Oregon" regardless of subscriber's state_code
- Root cause confirmed: `self._config.state_name` always resolves from global `usgs_state_code`

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL (subscriber, globalConfig) WHERE isBugCondition(subscriber, globalConfig) DO
  result_subject := send_email_fixed(subscriber.email, body, state_code=subscriber.state_code)
  expected_name := STATE_NAMES[subscriber.state_code]
  ASSERT expected_name IN result_subject
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL (subscriber, globalConfig) WHERE NOT isBugCondition(subscriber, globalConfig) DO
  subject_original := send_email_original(subscriber.email, body)
  subject_fixed := send_email_fixed(subscriber.email, body, state_code=globalConfig.usgs_state_code)
  ASSERT subject_original == subject_fixed
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many combinations of global state codes and subscriber configurations
- It catches edge cases like unknown state codes or boundary conditions in the STATE_NAMES mapping
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for subscribers with empty state_code, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Empty state_code preservation**: Verify that subscribers with empty `state_code` get the global default state name in the subject, same as before
2. **Matching state_code preservation**: Verify that subscribers whose `state_code` equals the global default get the same subject as before
3. **Email body preservation**: Verify that the HTML body content is unchanged regardless of state_code
4. **Rate limiting preservation**: Verify that rate limiting between sends continues to work

### Unit Tests

- Test `send_email()` with explicit `state_code` parameter produces correct subject
- Test `send_email()` with `state_code=None` falls back to global config state name
- Test `send_email()` with `state_code` matching global default produces same subject
- Test that `STATE_NAMES` lookup handles the provided state code correctly

### Property-Based Tests

- Generate random valid state codes from `STATE_NAMES` keys and verify the subject contains the corresponding full state name
- Generate random subscriber configurations (with and without state overrides) and verify preservation for non-bug-condition inputs
- Generate random global config state codes and verify that empty-state-code subscribers always use the global default

### Integration Tests

- Test full pipeline run with mixed-state subscribers and verify each email has the correct subject
- Test pipeline run with all subscribers using the global default and verify no behavioral change
- Test pipeline run with a single subscriber having a non-default state and verify correct subject
