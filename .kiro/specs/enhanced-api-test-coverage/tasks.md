# Implementation Plan: Enhanced API Test Coverage

## Overview

Implement comprehensive test generation and multi-ticket support across the full stack. Tasks are ordered so each layer is ready before the next depends on it: config → services → models → endpoint → frontend → tests.

## Tasks

- [x] 1. Extend config.py with new environment variables
  - Add `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, and `SWAGGER_URL` to `collectionAI/Backend/app/config.py` alongside the existing `OPENAI_API_KEY` and `GOOGLE_API_KEY` entries
  - Keep `load_dotenv()` call; all new vars use `os.getenv(...)` with no defaults
  - _Requirements: 3.1, 6.1_

- [x] 2. Implement swagger_service.py
  - [x] 2.1 Create `collectionAI/Backend/app/services/swagger_service.py` with `load_catalog(swagger_url)` and `get_catalog()`
    - `load_catalog` fetches the spec via `requests.get`, resolves all `$ref` references inline so the LLM receives self-contained schema snippets, and stores the simplified catalog dict in a module-level `_catalog` variable
    - `get_catalog` returns `_catalog` (may be `None` if load was never called or failed)
    - On any fetch or parse error, log a warning and set `_catalog = None`; do not raise
    - Catalog shape: `{"endpoints": [{"path", "method", "summary", "parameters", "request_body", "responses"}, ...]}`
    - _Requirements: 6.1, 6.2_

  - [ ]* 2.2 Write unit tests for swagger_service
    - Test `load_catalog` with a mocked HTTP response containing a minimal OpenAPI spec with `$ref` entries — assert refs are inlined and catalog has correct endpoint shape
    - Test that a failed HTTP fetch sets catalog to `None` and does not raise
    - _Requirements: 6.1, 6.2_

- [x] 3. Implement jira_service.py
  - [x] 3.1 Create `collectionAI/Backend/app/services/jira_service.py` with `fetch_ticket`, `fetch_subtasks`, and `fetch_ticket_with_subtasks`
    - Use `requests` with HTTP Basic Auth (`JIRA_EMAIL`, `JIRA_API_TOKEN`) against `JIRA_BASE_URL`
    - `fetch_ticket(ticket_id)` → `GET /rest/api/3/issue/{ticket_id}?fields=summary,description`; raise `ConfigurationError` if any env var is missing; raise descriptive error on 401/403
    - `fetch_subtasks(ticket_id)` → fetch child issues via `subtasks` field on the parent; return `[]` if none
    - `fetch_ticket_with_subtasks(ticket_id)` → merge parent + subtasks into `{"id", "summary", "description", "subtasks": [...]}`
    - _Requirements: 2.1, 3.1, 3.2, 3.3, 3.4, 6.7_

  - [ ]* 3.2 Write unit tests for jira_service
    - Mock `requests.get` to return a fixture JIRA response; assert `fetch_ticket_with_subtasks` returns correct `summary`, `description`, and `subtasks` list
    - Assert `ConfigurationError` is raised when env vars are missing
    - Assert descriptive error is raised on 401/403 responses
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 3.3 Write property test for fetch_ticket_with_subtasks (Property 5)
    - `# Feature: enhanced-api-test-coverage, Property 5: Ticket fetch returns summary and description`
    - Use Hypothesis to generate random valid ticket IDs; mock JIRA HTTP layer to return generated summary/description; assert both fields are non-empty in the returned dict
    - **Property 5: Ticket fetch returns summary and description**
    - **Validates: Requirements 2.1, 3.4**

  - [ ]* 3.4 Write property test for skipped ticket warnings (Property 6)
    - `# Feature: enhanced-api-test-coverage, Property 6: Skipped ticket ID appears in warnings`
    - Use Hypothesis to generate batches with random invalid IDs; mock JIRA to return 404 for those IDs; assert each invalid ID appears as a substring in the `warnings` array
    - **Property 6: Skipped ticket ID appears in warnings**
    - **Validates: Requirements 2.3**

  - [ ]* 3.5 Write property test for subtask context (Property 16)
    - `# Feature: enhanced-api-test-coverage, Property 16: Subtasks included in ticket context`
    - Use Hypothesis to generate parent tickets with one or more subtasks; mock JIRA responses; assert `subtasks` list is non-empty and each entry has non-empty `summary` and `description`
    - **Property 16: Subtasks included in ticket context**
    - **Validates: Requirements 6.7**

- [x] 4. Update gemini_service.py with comprehensive generation
  - [x] 4.1 Add `generate_test_cases_comprehensive(ticket_context, catalog)` to `collectionAI/Backend/app/services/gemini_service.py`
    - Leave existing `generate_test_cases` untouched
    - Build the three-section prompt: role/rules, API catalog (serialized JSON, omitted if `catalog` is `None`), ticket context (subtasks before parent description per Req 6.8)
    - Instruct the LLM to return `{"flow_steps": [...], "warnings": []}` with the full `flow_steps` shape from the design
    - Parse the JSON response; on parse failure retry once; if still fails return `{"flow_steps": [], "warnings": ["<ticket_id>: LLM returned unparseable JSON"]}`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 6.3, 6.4, 6.5, 6.8, 6.9, 7.1, 7.2, 7.5_

  - [ ]* 4.2 Write unit tests for generate_test_cases_comprehensive
    - Mock Gemini API; assert prompt contains catalog endpoint paths when catalog is non-None
    - Assert prompt omits catalog section when catalog is None
    - Assert subtask API details appear before parent description text in the prompt
    - Assert JSON parse failure triggers one retry then returns warning
    - _Requirements: 6.3, 6.8_

  - [ ]* 4.3 Write property test for comprehensive coverage (Property 1)
    - `# Feature: enhanced-api-test-coverage, Property 1: Comprehensive coverage per ticket`
    - Use Hypothesis to generate random ticket dicts; mock Gemini to return a valid `flow_steps` list; assert result contains ≥1 `type="positive"`, ≥2 `type="negative"`, ≥1 `type="edge"`
    - **Property 1: Comprehensive coverage per ticket**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 4.4 Write property test for test case structural completeness (Property 2)
    - `# Feature: enhanced-api-test-coverage, Property 2: Test case structural completeness`
    - Use Hypothesis to generate random ticket dicts; assert every item in `flow_steps` has non-empty `method`, `endpoint`, non-null `expected_status`, and non-empty `test_script`
    - **Property 2: Test case structural completeness**
    - **Validates: Requirements 1.4, 1.5**

  - [ ]* 4.5 Write property test for API catalog in prompt (Property 14)
    - `# Feature: enhanced-api-test-coverage, Property 14: API catalog included in prompt when available`
    - Use Hypothesis to generate random non-None catalog dicts with at least one endpoint; capture the prompt string passed to Gemini; assert it contains at least one endpoint path from the catalog
    - **Property 14: API catalog included in prompt when available**
    - **Validates: Requirements 6.3**

  - [ ]* 4.6 Write property test for subtask ordering in prompt (Property 17)
    - `# Feature: enhanced-api-test-coverage, Property 17: Subtask API details precede parent description in prompt`
    - Use Hypothesis to generate ticket contexts where at least one subtask contains an explicit endpoint path; assert that path appears before the parent description text in the prompt string
    - **Property 17: Subtask API details precede parent description in prompt**
    - **Validates: Requirements 6.8**

- [x] 5. Update postman_service.py with multi-suite assembly
  - [x] 5.1 Add `build_test_suite(ticket_context, flow_steps)` to `collectionAI/Backend/app/services/postman_service.py`
    - Sort `flow_steps` by ascending `step` number before building items
    - For each step: build a Postman item with `{{baseUrl}}` in `url.raw`; include `request.body.raw` for non-GET methods; append `pm.environment.set(...)` calls to the test script for each `variable_extractions` entry; pass `{{variableName}}` references through from LLM output as-is
    - Prefix item `name` with `[Inferred]` and add `request.description` note when `inferred` is `true`
    - Return a single Postman folder dict `{"name": "<ticket_id> — <summary>", "item": [...]}`
    - _Requirements: 1.8, 2.4, 6.5, 6.6, 7.2, 7.3, 7.4_

  - [x] 5.2 Add `assemble_collection(suites, collection_name, ticket_ids)` to `collectionAI/Backend/app/services/postman_service.py`
    - Wrap all suite folders into a Collection v2.1 document in submission order
    - `info.name` = `collection_name` if provided, else first ticket ID
    - `info.description` = `"Generated from tickets: <comma-separated ticket_ids>"`
    - _Requirements: 2.4, 2.5, 2.6_

  - [ ]* 5.3 Write unit tests for postman_service
    - Test `build_test_suite` with a fixed flow_steps list: assert `[Inferred]` prefix on inferred steps, `{{baseUrl}}` in all URLs, `pm.environment.set` calls present for extraction entries, steps in ascending order
    - Test `assemble_collection` with two suites: assert folder order matches submission order, description contains both ticket IDs
    - _Requirements: 1.8, 2.4, 2.5, 2.6, 6.5, 6.6_

  - [ ]* 5.4 Write property test for non-GET request bodies (Property 3)
    - `# Feature: enhanced-api-test-coverage, Property 3: Non-GET requests include a request body`
    - Use Hypothesis to generate random flow_steps with non-GET methods; call `build_test_suite`; assert every resulting item's `request.body.raw` is non-null and non-empty
    - **Property 3: Non-GET requests include a request body**
    - **Validates: Requirements 1.6**

  - [ ]* 5.5 Write property test for baseUrl usage (Property 4)
    - `# Feature: enhanced-api-test-coverage, Property 4: All request URLs use {{baseUrl}}`
    - Use Hypothesis to generate random flow_steps; call `build_test_suite`; assert every item's `url.raw` starts with `"{{baseUrl}}"`
    - **Property 4: All request URLs use {{baseUrl}}**
    - **Validates: Requirements 1.8**

  - [ ]* 5.6 Write property test for collection structure order (Property 7)
    - `# Feature: enhanced-api-test-coverage, Property 7: Collection structure matches submission order`
    - Use Hypothesis to generate random lists of N suites; call `assemble_collection`; assert the resulting `item` array has exactly N folders in the same order
    - **Property 7: Collection structure matches submission order**
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 5.7 Write property test for collection description (Property 8)
    - `# Feature: enhanced-api-test-coverage, Property 8: Collection description lists processed ticket IDs`
    - Use Hypothesis to generate random ticket ID lists; call `assemble_collection`; assert each ticket ID appears as a substring in `info.description`
    - **Property 8: Collection description lists processed ticket IDs**
    - **Validates: Requirements 2.6**

  - [ ]* 5.8 Write property test for inferred test case prefixing (Property 15)
    - `# Feature: enhanced-api-test-coverage, Property 15: Inferred test cases are prefixed`
    - Use Hypothesis to generate random flow_steps with `inferred=True`; call `build_test_suite`; assert each resulting item's `name` starts with `"[Inferred]"` and `request.description` contains the catalog note
    - **Property 15: Inferred test cases are prefixed**
    - **Validates: Requirements 6.5, 6.6**

  - [ ]* 5.9 Write property test for E2E flow step ordering (Property 18)
    - `# Feature: enhanced-api-test-coverage, Property 18: E2E flow step ordering`
    - Use Hypothesis to generate random flow_steps with arbitrary step numbers; call `build_test_suite`; assert the folder's `item` array is in ascending step order
    - **Property 18: E2E flow step ordering**
    - **Validates: Requirements 7.2**

  - [ ]* 5.10 Write property test for variable extraction scripts (Property 19)
    - `# Feature: enhanced-api-test-coverage, Property 19: Variable extraction scripts generated`
    - Use Hypothesis to generate random flow_steps with non-empty `variable_extractions`; call `build_test_suite`; assert each extraction entry produces a `pm.environment.set(variableName, ...)` call in the item's test script
    - **Property 19: Variable extraction scripts generated**
    - **Validates: Requirements 7.3**

  - [ ]* 5.11 Write property test for variable reference syntax (Property 20)
    - `# Feature: enhanced-api-test-coverage, Property 20: Variable references use Postman syntax`
    - Use Hypothesis to generate random flow_steps with non-empty `variable_usages`; call `build_test_suite`; assert `{{variableName}}` appears in the item's URL, headers, or body for each usage
    - **Property 20: Variable references use Postman syntax**
    - **Validates: Requirements 7.4**

  - [ ]* 5.12 Write property test for prerequisite step ordering (Property 21)
    - `# Feature: enhanced-api-test-coverage, Property 21: Prerequisite steps precede primary steps`
    - Use Hypothesis to generate random flows mixing `role="prerequisite"` and `role="primary"` steps; call `build_test_suite`; assert all prerequisite items appear before all primary items in the folder's `item` array
    - **Property 21: Prerequisite steps precede primary steps**
    - **Validates: Requirements 7.2, 7.5**

- [x] 6. Add Pydantic models to models.py
  - Add `MultiTicketRequest` with `ticket_ids: list[str]` (min 1, max 20) and `collection_name: str | None = None` to `collectionAI/Backend/app/models.py`
  - Add `MultiTicketResponse` with `postman_collection: dict` and `warnings: list[str] = []`
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 7. Update main.py with startup event and new endpoint
  - [x] 7.1 Add startup event to `collectionAI/Backend/app/main.py` that calls `swagger_service.load_catalog(config.SWAGGER_URL)`
    - Import `swagger_service` and `config`; register via `@app.on_event("startup")`
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 Add `POST /generate-from-tickets` endpoint to `collectionAI/Backend/app/main.py`
    - Accept `MultiTicketRequest`; return `MultiTicketResponse`
    - Validate JIRA env vars; return HTTP 503 with missing var name if any are absent
    - For each ticket ID: call `jira_service.fetch_ticket_with_subtasks`; on failure add warning and continue
    - If all tickets failed, return HTTP 400 listing all failed IDs
    - For each successful ticket: call `gemini_service.generate_test_cases_comprehensive` with ticket context and `swagger_service.get_catalog()`; on LLM error add warning and continue
    - Call `postman_service.build_test_suite` per ticket, then `postman_service.assemble_collection`
    - Return HTTP 200 with assembled collection and all accumulated warnings
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 3.2, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 7.3 Write unit tests for the /generate-from-tickets endpoint
    - HTTP 422 when `ticket_ids` is empty or missing
    - HTTP 400 when all ticket IDs fail to resolve
    - HTTP 503 when a required JIRA env var is missing (assert message names the missing var)
    - HTTP 200 with `postman_collection` and `warnings` when at least one ticket succeeds
    - _Requirements: 3.2, 5.1, 5.2, 5.3, 5.4_

  - [ ]* 7.4 Write property test for missing JIRA credentials (Property 9)
    - `# Feature: enhanced-api-test-coverage, Property 9: Missing JIRA credential returns 503`
    - Use Hypothesis to generate random subsets of the three required JIRA env vars that are absent; call the endpoint; assert HTTP 503 and that the response message identifies the missing variable
    - **Property 9: Missing JIRA credential returns 503**
    - **Validates: Requirements 3.2**

  - [ ]* 7.5 Write property test for successful response structure (Property 13)
    - `# Feature: enhanced-api-test-coverage, Property 13: Successful response structure`
    - Use Hypothesis to generate random valid requests with at least one resolvable ticket; mock JIRA and Gemini; assert HTTP 200 and body contains both `postman_collection` and `warnings`
    - **Property 13: Successful response structure**
    - **Validates: Requirements 5.2**

- [x] 8. Checkpoint — ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Update React frontend for multi-ticket mode
  - [x] 9.1 Add `parseTicketIds(input)` utility to `collectionAI/Frontend/src/components/testGenerator.js` (or a new `utils.js`)
    - Splits on commas and newlines, trims each token, filters empty strings, returns array of unique IDs
    - _Requirements: 4.1_

  - [x] 9.2 Add multi-ticket input mode to `collectionAI/Frontend/src/App.jsx`
    - Add `mode` state (`"manual"` | `"tickets"`), `ticketInput` state, `collectionName` state, and `warnings` state
    - Render a mode toggle (two buttons or tabs) that switches between the existing manual form and the new ticket IDs form
    - Ticket IDs form: textarea for comma/newline-separated IDs, optional collection name text input, "Generate Collection" button
    - On submit: call `parseTicketIds`, POST to `/generate-from-tickets`, show spinner while loading
    - On success: display yellow warning banner if `warnings` is non-empty (one line per warning); show download and copy buttons
    - Download filename: `<collectionName || ticketIds[0]>_collection.json`
    - Preserve existing manual mode (`POST /generate`) unchanged under the "Manual" tab
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 9.3 Write property test for parseTicketIds (Property 10)
    - `# Feature: enhanced-api-test-coverage, Property 10: Ticket ID input parsing`
    - Use fast-check to generate random strings of ticket IDs separated by commas, newlines, or a mix; assert `parseTicketIds` returns trimmed, non-empty strings matching the originals with no duplicates introduced and no IDs dropped
    - **Property 10: Ticket ID input parsing**
    - **Validates: Requirements 4.1**

  - [ ]* 9.4 Write property test for download filename derivation (Property 11)
    - `# Feature: enhanced-api-test-coverage, Property 11: Download filename derivation`
    - Use fast-check to generate random `(collectionName, ticketIds)` pairs; assert filename equals `<collectionName>_collection.json` when name is provided, else `<ticketIds[0]>_collection.json`
    - **Property 11: Download filename derivation**
    - **Validates: Requirements 4.3**

  - [ ]* 9.5 Write property test for warnings rendering (Property 12)
    - `# Feature: enhanced-api-test-coverage, Property 12: Warnings rendered in UI`
    - Use fast-check to generate random non-empty warnings arrays; render the component with that warnings state; assert each warning string is visible in the rendered output
    - **Property 12: Warnings rendered in UI**
    - **Validates: Requirements 4.5**

- [x] 10. Final checkpoint — ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis (Python backend) and fast-check (JS frontend), minimum 100 iterations each
- Each property test includes a comment: `# Feature: enhanced-api-test-coverage, Property <N>: <text>`
- The existing `/generate` endpoint and manual UI mode must remain untouched throughout
