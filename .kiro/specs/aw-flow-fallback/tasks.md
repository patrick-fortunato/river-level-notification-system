# Tasks

## 1. Add AWFlowData dataclass and update ResolvedReach
- [x] 1.1 Add `AWFlowData` dataclass to `src/models.py` with fields: `reading: float`, `unit: str`, `gauge_name: str`, `updated: float | None`
- [x] 1.2 Add `aw_flow_data: AWFlowData | None = None` field to `ResolvedReach` dataclass

## 2. Update ReachResolver to capture AW flow data
- [x] 2.1 Expand the GraphQL query in `_query_reach` to include `gauge_reading`, `reading`, `updated`, `metric { unit name }`, and `gauge { name }` fields
- [x] 2.2 Add `_extract_aw_flow_data` helper method that takes the gauges list and returns `AWFlowData | None` — picks the first gauge entry with a non-null `gauge_reading` or `reading` value
- [x] 2.3 Call `_extract_aw_flow_data` in `_query_reach` when `_extract_usgs_gauge` returns None, and pass the result to the `ResolvedReach` constructor

## 3. Update ReachCache to serialize/deserialize aw_flow_data
- [x] 3.1 Update `put_reach` to serialize `aw_flow_data` as a nested dict when present
- [x] 3.2 Update `_entry_to_resolved_reach` to deserialize the `aw_flow_data` key into an `AWFlowData` object when present in the cache entry

## 4. Update ReportBuilder to render AW flow fallback
- [x] 4.1 Update `_render_reach_entry` to render AW flow data (reading, unit, gauge name) when `gauge_entry` is None but `resolved.aw_flow_data` is not None
- [x] 4.2 Ensure "No gauge data available" is only shown when both `gauge_entry` and `resolved.aw_flow_data` are None

## 5. Write property-based tests
- [x] 5.1 [PBT-exploration] Property 1: Bug Condition — AW flow data captured as fallback. Generate random AW API responses with no USGS gauge but valid gauge_reading; assert `aw_flow_data` is populated with correct values. Run on UNFIXED code first to confirm failure.
- [x] 5.2 [PBT-preservation] Property 2: Preservation — USGS gauge selection unchanged. Generate random AW API responses containing at least one USGS gauge; assert `gauge_id` equals first USGS source_id and `aw_flow_data` is None.
- [x] 5.3 [PBT-exploration] Property 3: Bug Condition — Report renders AW flow data. Generate random `AWFlowData` values on a `ResolvedReach` with no `gauge_entry`; assert output contains reading and does not contain "No gauge data available".
- [x] 5.4 [PBT-preservation] Property 4: Preservation — USGS report rendering unchanged. Generate random `GaugeEntry` objects for a reach with `gauge_id` set; assert `_render_reach_entry` produces identical output to the original logic.

## 6. Write unit tests
- [x] 6.1 Test `_query_reach` with mocked API response containing only virtual gauge with reading → `aw_flow_data` populated
- [x] 6.2 Test `_query_reach` with mocked API response containing USGS gauge → `gauge_id` set, `aw_flow_data` is None
- [x] 6.3 Test `_query_reach` with empty gauges list → `gauge_id` None, `aw_flow_data` None
- [x] 6.4 Test `ReachCache` round-trip: put/get reach with `aw_flow_data` populated
- [x] 6.5 Test `ReachCache` backward compatibility: get reach from cache entry without `aw_flow_data` key
- [x] 6.6 Test `_render_reach_entry` with `aw_flow_data` present, `gauge_entry` None → renders flow with AW attribution
- [x] 6.7 Test `_render_reach_entry` with both None → shows "No gauge data available"
