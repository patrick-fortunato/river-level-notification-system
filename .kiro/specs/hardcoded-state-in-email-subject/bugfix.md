# Bugfix Requirements Document

## Introduction

The email subject line for river level notifications always displays "Oregon" regardless of the subscriber's configured state. The `EmailSender.send_email()` method formats the subject using the global `Config.state_name` property, which resolves from the global `usgs_state_code` (default "OR"). Since the pipeline determines each subscriber's effective state but never passes it to the email sender, all subscribers receive emails with "Current Oregon River Levels" in the subject — even those configured for other states like Washington or California.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a subscriber has a per-subscriber state_code override (e.g., "WA") configured in the spreadsheet THEN the system sends an email with the subject "Current Oregon River Levels" instead of reflecting the subscriber's actual state

1.2 WHEN multiple subscribers have different state_code values THEN the system sends all emails with the same subject "Current Oregon River Levels" regardless of each subscriber's configured state

### Expected Behavior (Correct)

2.1 WHEN a subscriber has a per-subscriber state_code override (e.g., "WA") THEN the system SHALL send an email with the subject "Current Washington River Levels" reflecting the subscriber's effective state

2.2 WHEN multiple subscribers have different state_code values THEN the system SHALL send each email with a subject that reflects that specific subscriber's effective state (e.g., "Current Washington River Levels" for WA, "Current California River Levels" for CA)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a subscriber has an empty state_code (uses the global default) THEN the system SHALL CONTINUE TO send an email with the subject reflecting the global default state (e.g., "Current Oregon River Levels" when the global default is "OR")

3.2 WHEN the email_subject template format string is configured THEN the system SHALL CONTINUE TO use the `{state_name}` placeholder pattern for subject formatting

3.3 WHEN a subscriber's state_code matches the global default state THEN the system SHALL CONTINUE TO send an email with the same subject as before (e.g., "Current Oregon River Levels")
