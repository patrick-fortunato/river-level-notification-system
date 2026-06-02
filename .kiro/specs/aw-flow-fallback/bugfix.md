# Bugfix Requirements Document

## Introduction

When a reach has no USGS gauge association (e.g., reach 4121 — South Fork Payette in Idaho), the email report displays "No gauge data available" even though the American Whitewater (AW) API returns flow readings for that reach via a virtual gauge. The system currently discards all non-USGS gauge data from the AW API response, leaving reaches without USGS gauges with no flow information in reports. The fix should use AW-provided flow data as a fallback when no USGS gauge is available, while preserving USGS as the preferred data source.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a reach has no gauge with source="usgs" in its AW API gauge associations BUT has a virtual or other non-USGS gauge providing flow data THEN the system discards the available flow reading and sets gauge_id to None

1.2 WHEN a reach has gauge_id=None (no USGS gauge) THEN the pipeline skips USGS data fetching for that reach and no alternative flow data is captured or stored

1.3 WHEN the report is rendered for a reach with no gauge data THEN the system displays "No gauge data available" despite the AW API having returned valid flow readings (gauge_reading, unit, gauge name, updated timestamp)

### Expected Behavior (Correct)

2.1 WHEN a reach has no gauge with source="usgs" BUT the AW API response contains gauge data with a valid reading (gauge_reading or reading field) from any gauge source THEN the system SHALL capture that AW flow data (reading value, unit, gauge name, updated timestamp) as fallback flow information on the resolved reach

2.2 WHEN a reach has AW fallback flow data and no USGS gauge THEN the pipeline SHALL use the captured AW flow data for that reach without attempting a USGS fetch

2.3 WHEN the report is rendered for a reach with AW fallback flow data THEN the system SHALL display the flow reading with appropriate attribution (e.g., showing the gauge name and indicating the data source is AW rather than USGS) instead of "No gauge data available"

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a reach has a gauge with source="usgs" in its AW API gauge associations THEN the system SHALL CONTINUE TO use the USGS gauge_id as the primary data source and fetch flow data from the USGS API

3.2 WHEN a reach has both a USGS gauge and non-USGS gauges in its AW API response THEN the system SHALL CONTINUE TO prefer the USGS gauge data and ignore the non-USGS gauge readings

3.3 WHEN a reach has no gauges of any type in the AW API response THEN the system SHALL CONTINUE TO display "No gauge data available" in the report

3.4 WHEN the USGS API returns valid data for a reach's gauge THEN the report formatting (flow in cfs, reading datetime, USGS gauge link) SHALL CONTINUE TO render identically to current behavior

---

## Bug Condition

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type ReachGaugeData (reach_id, aw_api_gauges[])
  OUTPUT: boolean
  
  // Returns true when reach has no USGS gauge but has AW flow data available
  hasUsgsGauge ← EXISTS gauge IN X.aw_api_gauges WHERE gauge.source = "usgs"
  hasAwFlowData ← EXISTS gauge IN X.aw_api_gauges WHERE gauge.gauge_reading IS NOT NULL
  
  RETURN (NOT hasUsgsGauge) AND hasAwFlowData
END FUNCTION
```

## Fix Checking Property

```pascal
// Property: Fix Checking - AW flow fallback is used when no USGS gauge exists
FOR ALL X WHERE isBugCondition(X) DO
  resolved ← ReachResolver.resolve(X.reach_id)
  ASSERT resolved.aw_flow_data IS NOT NULL
  ASSERT resolved.aw_flow_data.reading IS NOT NULL
  ASSERT resolved.aw_flow_data.unit IS NOT NULL
  
  report ← ReportBuilder.render(resolved)
  ASSERT report DOES NOT CONTAIN "No gauge data available"
  ASSERT report CONTAINS resolved.aw_flow_data.reading
END FOR
```

## Preservation Checking Property

```pascal
// Property: Preservation Checking - USGS reaches behave identically
FOR ALL X WHERE NOT isBugCondition(X) DO
  resolved ← ReachResolver.resolve(X.reach_id)
  resolved_original ← OriginalReachResolver.resolve(X.reach_id)
  
  // USGS gauge selection unchanged
  ASSERT resolved.gauge_id = resolved_original.gauge_id
  
  // Report output unchanged for USGS-backed reaches
  IF resolved.gauge_id IS NOT NULL THEN
    report ← ReportBuilder.render(resolved, usgs_data)
    report_original ← OriginalReportBuilder.render(resolved_original, usgs_data)
    ASSERT report = report_original
  END IF
END FOR
```
