# AW Flow Fallback Bugfix Design

## Overview

The system discards all non-USGS gauge data returned by the AW GraphQL API, leaving reaches without USGS gauge associations showing "No gauge data available" in email reports — even when the AW API provides valid flow readings from virtual or calculated gauges. The fix adds a fallback path: when no USGS gauge is found for a reach, the resolver captures the first available AW gauge reading into a new `AWFlowData` dataclass on `ResolvedReach`. The report builder then renders this data with AW attribution instead of the empty-state message. USGS remains the preferred source and its code path is untouched.

## Glossary

- **Bug_Condition (C)**: A reach has no gauge with `source="usgs"` in its AW API gauge associations BUT has at least one gauge with a valid reading (gauge_reading or reading field)
- **Property (P)**: When the bug condition holds, the resolved reach carries `aw_flow_data` and the report renders flow information with AW attribution
- **Preservation**: USGS-backed reaches, report formatting for USGS data, and the pipeline's USGS fetch logic remain unchanged
- **AWFlowData**: A new dataclass holding `reading` (float), `unit` (str), `gauge_name` (str), `updated` (float | None) — represents flow data sourced from AW's gauge response
- **ResolvedReach**: The domain object produced by `ReachResolver` that carries a reach's name, USGS gauge ID, state, and (after fix) optional AW flow data
- **Virtual gauge**: An AW-computed gauge (source="virtual") that provides derived flow readings without a physical sensor

## Bug Details

### Bug Condition

The bug manifests when a reach has no USGS gauge association but the AW API returns gauge data with valid flow readings. The `_query_reach` method extracts only the USGS gauge ID and discards all other gauge information, so the flow reading, unit, gauge name, and timestamp are lost.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ReachGaugeResponse (reach_id, gauges[])
  OUTPUT: boolean

  hasUsgsGauge ← EXISTS g IN input.gauges WHERE g.gauge.source = "usgs"
  hasAwFlowData ← EXISTS g IN input.gauges WHERE g.gauge_reading IS NOT NULL OR g.reading IS NOT NULL

  RETURN (NOT hasUsgsGauge) AND hasAwFlowData
END FUNCTION
```

### Examples

- **Reach 4121 (S. Fork Payette)**: AW returns `[{gauge: {source: "virtual", source_id: "49596"}, gauge_reading: 2461, reading: 2461, metric: {unit: "cfs"}, updated: 30578618.0}]` → Currently produces `gauge_id=None`, report shows "No gauge data available". Expected: `aw_flow_data=AWFlowData(reading=2461, unit="cfs", gauge_name="...", updated=30578618.0)`
- **Reach with calculated gauge**: AW returns a gauge with `source="calculated"`, reading=150, unit="cfs" → Same bug: discarded despite valid data
- **Reach with USGS gauge (not a bug)**: AW returns `[{gauge: {source: "usgs", source_id: "14209500"}, ...}]` → System correctly sets `gauge_id="14209500"`, USGS fetch provides data
- **Reach with zero gauges (not a bug)**: AW returns `{gauges: []}` → Correctly shows "No gauge data available"

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Reaches with a USGS gauge continue to use USGS as the primary data source via `gauge_id`
- When both USGS and non-USGS gauges exist, the USGS gauge is preferred and `aw_flow_data` is not populated
- Reaches with no gauges at all continue to display "No gauge data available"
- USGS report rendering (flow in cfs, formatted datetime, USGS gauge link) is identical to current behavior
- Cache serialization/deserialization of existing fields (`reach_name`, `gauge_id`, `state`) remains backward-compatible
- Pipeline orchestration (subscriber processing, email sending, error handling) is unchanged

**Scope:**
All inputs where a USGS gauge IS found, or where NO gauges exist at all, should produce exactly the same output as before this fix.

## Hypothesized Root Cause

Based on the code analysis, the root cause is straightforward:

1. **`_query_reach` discards non-USGS gauge data**: The method calls `_extract_usgs_gauge(gauges)` which returns `None` when no USGS gauge exists. No code path captures the flow reading, unit, or gauge name from the remaining gauges.

2. **`ResolvedReach` has no field for AW flow data**: The dataclass only holds `gauge_id: str | None`, which maps exclusively to a USGS gauge number. There is no mechanism to carry alternative flow data.

3. **`ReportBuilder` has a binary check**: If `gauge_entry` (from USGS fetch) is None, it renders the "No gauge data available" message. There is no fallback path that checks for AW-sourced flow data on the resolved reach.

4. **`ReachCache` does not serialize AW flow data**: Even if captured, the cache would not persist it across runs.

## Correctness Properties

Property 1: Bug Condition - AW flow data captured as fallback

_For any_ AW API response where no gauge has source="usgs" but at least one gauge has a valid reading (gauge_reading is not null), the fixed `_query_reach` function SHALL produce a `ResolvedReach` with `aw_flow_data` populated containing the first gauge's reading value, unit, gauge name, and updated timestamp.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - USGS gauge selection unchanged

_For any_ AW API response where at least one gauge has source="usgs", the fixed `_query_reach` function SHALL produce a `ResolvedReach` with `gauge_id` set to the first USGS gauge's source_id and `aw_flow_data` set to None, preserving the existing USGS-preferred behavior.

**Validates: Requirements 3.1, 3.2**

Property 3: Bug Condition - Report renders AW flow data

_For any_ resolved reach with `aw_flow_data` populated (non-None) and `gauge_id` = None, the fixed `ReportBuilder._render_reach_entry` SHALL produce HTML that contains the flow reading value and does NOT contain "No gauge data available".

**Validates: Requirements 2.3**

Property 4: Preservation - USGS report rendering unchanged

_For any_ resolved reach with a valid `gauge_id` and a corresponding `GaugeEntry`, the fixed `ReportBuilder._render_reach_entry` SHALL produce HTML identical to the original function's output.

**Validates: Requirements 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/models.py`

**Change**: Add `AWFlowData` dataclass and `aw_flow_data` field to `ResolvedReach`

1. **Add AWFlowData dataclass**: New dataclass with fields `reading: float`, `unit: str`, `gauge_name: str`, `updated: float | None`
2. **Add field to ResolvedReach**: `aw_flow_data: AWFlowData | None = None`

---

**File**: `src/reach_resolver.py`

**Function**: `_query_reach`

**Specific Changes**:
1. **Expand GraphQL query fields**: Add `gauge_reading`, `reading`, `updated`, `metric { unit name }`, and `gauge { name }` to the `getGaugeInformationForReachID` selection set (some are already present; ensure `name`, `gauge_reading`, `reading`, `updated`, `metric { unit }` are included)
2. **Capture AW flow data when no USGS gauge**: After `_extract_usgs_gauge` returns None, iterate the gauges list and take the first entry with a valid `gauge_reading` or `reading` value. Construct an `AWFlowData` from it.
3. **Pass aw_flow_data to ResolvedReach**: Set the new field when constructing the return value.

---

**File**: `src/reach_cache.py`

**Function**: `put_reach` and `_entry_to_resolved_reach`

**Specific Changes**:
1. **Serialize aw_flow_data in put_reach**: When `resolved.aw_flow_data` is not None, store it as a nested dict `{"reading": ..., "unit": ..., "gauge_name": ..., "updated": ...}`
2. **Deserialize aw_flow_data in _entry_to_resolved_reach**: Read the `aw_flow_data` key from the cache entry and reconstruct an `AWFlowData` object if present

---

**File**: `src/report_builder.py`

**Function**: `_render_reach_entry`

**Specific Changes**:
1. **Add AW flow fallback rendering**: When `gauge_entry` is None but `resolved.aw_flow_data` is not None, render a flow display showing the reading, unit, and gauge name with AW attribution
2. **Keep "No gauge data available" for truly empty reaches**: Only show the empty-state message when both `gauge_entry` is None AND `resolved.aw_flow_data` is None

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis.

**Test Plan**: Write tests that mock the AW GraphQL API to return responses with non-USGS gauges containing valid flow readings, then assert that `_query_reach` captures the flow data. Run these on the UNFIXED code to observe failures.

**Test Cases**:
1. **Virtual gauge with reading**: Mock API returns `[{gauge: {source: "virtual"}, gauge_reading: 2461, metric: {unit: "cfs"}}]` — assert `aw_flow_data` is populated (will fail on unfixed code)
2. **Calculated gauge with reading**: Mock API returns `[{gauge: {source: "calculated"}, gauge_reading: 150, metric: {unit: "cfs"}}]` — assert `aw_flow_data` is populated (will fail on unfixed code)
3. **Report with AW flow data**: Provide a ResolvedReach with `aw_flow_data` set — assert report does not contain "No gauge data available" (will fail on unfixed code since field doesn't exist yet)

**Expected Counterexamples**:
- `resolved.aw_flow_data` is None (or field doesn't exist) when API provides non-USGS gauge readings
- Report shows "No gauge data available" even when flow data could be displayed

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  resolved := _query_reach_fixed(input.reach_id)
  ASSERT resolved.aw_flow_data IS NOT NULL
  ASSERT resolved.aw_flow_data.reading == input.gauges[0].gauge_reading
  ASSERT resolved.aw_flow_data.unit == input.gauges[0].metric.unit

  report := render_reach_entry(resolved, gauge_entry=None)
  ASSERT "No gauge data available" NOT IN report
  ASSERT str(resolved.aw_flow_data.reading) IN report
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  resolved_fixed := _query_reach_fixed(input.reach_id)
  resolved_original := _query_reach_original(input.reach_id)

  ASSERT resolved_fixed.gauge_id == resolved_original.gauge_id
  ASSERT resolved_fixed.reach_name == resolved_original.reach_name
  ASSERT resolved_fixed.state == resolved_original.state

  IF resolved_fixed.gauge_id IS NOT NULL THEN
    // USGS path: aw_flow_data should be None
    ASSERT resolved_fixed.aw_flow_data IS NULL
  END IF
END FOR
```

**Testing Approach**: Property-based testing with Hypothesis is recommended for preservation checking because:
- It generates many random AW API response shapes automatically
- It catches edge cases in gauge list parsing that manual tests might miss
- It provides strong guarantees that USGS gauge selection is unchanged

**Test Plan**: Observe behavior on UNFIXED code first for USGS-backed reaches, then write property-based tests capturing that behavior continues after the fix.

**Test Cases**:
1. **USGS gauge selection preservation**: Generate random gauge lists containing at least one USGS gauge — verify `gauge_id` matches first USGS source_id and `aw_flow_data` is None
2. **Empty gauge list preservation**: Generate reaches with no gauges — verify `gauge_id` is None and `aw_flow_data` is None
3. **Report USGS rendering preservation**: Generate random GaugeEntry objects — verify `_render_reach_entry` output is identical to original

### Unit Tests

- Test `_query_reach` with mocked API response containing only non-USGS gauges with valid readings
- Test `_query_reach` with mocked API response containing USGS gauge (no aw_flow_data)
- Test `_query_reach` with empty gauges list (no aw_flow_data)
- Test `AWFlowData` serialization/deserialization in `ReachCache`
- Test `_render_reach_entry` with `aw_flow_data` present and `gauge_entry` None
- Test `_render_reach_entry` with both None (shows "No gauge data available")

### Property-Based Tests

- Generate random non-USGS gauge responses and verify `aw_flow_data` is always populated with correct values (Property 1)
- Generate random USGS gauge responses and verify `gauge_id` is set and `aw_flow_data` is None (Property 2)
- Generate random `AWFlowData` values and verify report output contains reading and lacks empty-state message (Property 3)
- Generate random `GaugeEntry` values and verify USGS report rendering is unchanged (Property 4)

### Integration Tests

- End-to-end test: reach with only virtual gauge produces email with AW flow data
- End-to-end test: reach with USGS gauge continues to produce email with USGS data
- Cache round-trip: resolve reach with AW flow data, verify cache stores and retrieves it correctly
