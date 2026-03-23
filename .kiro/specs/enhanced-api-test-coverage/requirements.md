# Requirements Document

## Introduction

This feature enhances CollectionAI's Postman collection generation in two key ways:

1. **Comprehensive test coverage** — instead of basic skeletons, the AI generates positive, negative, and edge case test scenarios per API, with meaningful Postman test scripts for each.
2. **Multi-ticket support** — users can provide multiple JIRA ticket IDs (e.g., all tickets under an epic or feature) and receive a single, end-to-end Postman collection covering all APIs in that feature.

The backend is a Python/FastAPI app using Gemini as the LLM. The frontend is a React app with a single-ticket text input today.

---

## Glossary

- **CollectionAI**: The full-stack application being enhanced.
- **Generator**: The backend FastAPI service responsible for producing Postman collections.
- **Postman_Collection**: A valid Postman Collection v2.1 JSON document containing folders, requests, and test scripts.
- **JIRA_Service**: The backend service responsible for fetching ticket data from the JIRA API.
- **Ticket**: A single JIRA issue containing a summary, description, and optionally acceptance criteria.
- **Epic**: A JIRA issue type that groups multiple child Tickets under a common feature.
- **Test_Case**: A single Postman request item with a name, HTTP method, URL, headers, body, and test scripts.
- **Test_Suite**: A named folder within a Postman_Collection grouping all Test_Cases for one Ticket.
- **Coverage_Mode**: The level of test generation — either `basic` (current behavior) or `comprehensive` (positive + negative + edge cases).
- **LLM_Service**: The Gemini-backed service that generates test content from ticket data.
- **UI**: The React frontend application.
- **API_Catalog**: The parsed set of endpoints, methods, and schemas extracted from the Swagger/OpenAPI spec.
- **Swagger_Service**: A new backend service responsible for fetching, parsing, and caching the OpenAPI spec.
- **Inferred_Test_Case**: A Test_Case whose API details were determined by the LLM rather than explicitly provided in the ticket.
- **E2E_Flow**: An ordered sequence of API calls that together represent a complete, runnable end-to-end test scenario for a feature, where outputs from earlier calls are wired as inputs to later calls.
- **Flow_Step**: A single API call within an E2E_Flow, annotated with its position, dependencies, and variable extraction rules.
- **Variable_Extraction**: A Postman test script snippet that reads a value from a response (e.g., `pm.environment.set("advertiserId", pm.response.json().id)`) and stores it for use in subsequent requests.

---

## Requirements

### Requirement 1: Comprehensive Test Case Generation

**User Story:** As a QA engineer, I want the generator to produce positive, negative, and edge case test scenarios for each API, so that my Postman collection provides meaningful coverage beyond happy-path skeletons.

#### Acceptance Criteria

1. WHEN a Ticket is submitted for generation, THE Generator SHALL produce at least one positive Test_Case (valid inputs, expected success response).
2. WHEN a Ticket is submitted for generation, THE Generator SHALL produce at least two negative Test_Cases (e.g., missing required fields, invalid field formats, unauthorized access).
3. WHEN a Ticket is submitted for generation, THE Generator SHALL produce at least one edge case Test_Case (e.g., boundary values, empty collections, maximum field lengths).
4. THE LLM_Service SHALL infer the HTTP method, endpoint path, request schema, and expected status codes from the Ticket summary and description without requiring the user to supply them manually.
5. WHEN generating a Test_Case, THE Generator SHALL include a Postman test script that asserts the expected HTTP status code for that scenario.
6. WHEN generating a Test_Case for a non-GET request, THE Generator SHALL include a realistic request body derived from the Ticket description rather than a generic placeholder.
7. IF the LLM_Service cannot confidently determine required API details from the Ticket content, THEN THE Generator SHALL return a warning in the response describing what information would improve the result, and SHALL include whatever best-effort Test_Cases it could produce rather than returning a hard error.
8. THE Generator SHALL use `{{baseUrl}}` as the host variable in all generated request URLs so that collections are environment-agnostic.

---

### Requirement 2: Multi-Ticket Input

**User Story:** As a QA engineer, I want to submit multiple JIRA ticket IDs at once, so that I can generate a single Postman collection covering all APIs in a feature without repeating the process per ticket.

#### Acceptance Criteria

1. WHEN a list of one or more JIRA ticket IDs is submitted, THE JIRA_Service SHALL fetch the summary and description for each ticket from the JIRA API.
2. THE Generator SHALL accept a request containing a list of between 1 and 20 JIRA ticket IDs.
3. IF a submitted ticket ID does not exist in JIRA or is inaccessible, THEN THE Generator SHALL skip that ticket and include a warning in the response identifying the skipped ID.
4. WHEN all tickets have been fetched, THE Generator SHALL produce a single Postman_Collection containing one Test_Suite folder per Ticket, named after the ticket ID and summary.
5. THE Generator SHALL process tickets and generate their Test_Suites in the order they were submitted.
6. WHEN the resulting Postman_Collection is assembled, THE Generator SHALL include a collection-level description listing all ticket IDs that were successfully processed.

---

### Requirement 3: JIRA Authentication and Configuration

**User Story:** As a developer, I want the backend to authenticate with JIRA using configurable credentials, so that ticket data can be fetched securely without hardcoding secrets.

#### Acceptance Criteria

1. THE JIRA_Service SHALL authenticate with the JIRA API using credentials supplied via environment variables (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`).
2. IF any required JIRA credential environment variable is missing at startup, THEN THE Generator SHALL return a 503 error on any request that requires JIRA access, with a message indicating which variable is missing.
3. WHEN a JIRA API call fails due to an authentication error (HTTP 401 or 403), THE JIRA_Service SHALL surface a descriptive error to the caller rather than returning an empty result.
4. THE JIRA_Service SHALL retrieve at minimum the `summary` and `description` fields for each requested ticket ID.

---

### Requirement 4: Multi-Ticket UI

**User Story:** As a QA engineer, I want a UI that lets me enter multiple JIRA ticket IDs and trigger generation, so that I can produce end-to-end collections without leaving the browser.

#### Acceptance Criteria

1. THE UI SHALL provide an input mode that accepts a comma-separated or newline-separated list of JIRA ticket IDs.
2. WHEN the user submits ticket IDs, THE UI SHALL display a loading indicator for the duration of the generation request.
3. WHEN the Postman_Collection is returned, THE UI SHALL allow the user to download it as a `.json` file named after the first ticket ID or a user-supplied collection name.
4. WHEN the Postman_Collection is returned, THE UI SHALL allow the user to copy the raw JSON to the clipboard.
5. IF the generation request returns an error or partial warnings, THE UI SHALL display the error or warning messages clearly alongside any successfully generated output.
6. THE UI SHALL preserve the existing single-ticket manual description input as an alternative input mode.

---

### Requirement 5: API Contract for Multi-Ticket Endpoint

**User Story:** As a developer, I want a well-defined API endpoint for multi-ticket generation, so that the frontend and any future integrations have a stable contract to depend on.

#### Acceptance Criteria

1. THE Generator SHALL expose a `POST /generate-from-tickets` endpoint that accepts a JSON body with a `ticket_ids` array of strings and an optional `collection_name` string.
2. WHEN the request is valid and at least one ticket is processed successfully, THE Generator SHALL return HTTP 200 with a `postman_collection` object and a `warnings` array (empty if none).
3. IF the `ticket_ids` array is empty or missing, THEN THE Generator SHALL return HTTP 422 with a descriptive validation error.
4. IF all submitted ticket IDs fail to resolve, THEN THE Generator SHALL return HTTP 400 with an error message listing all failed IDs.
5. THE Generator SHALL respond to `POST /generate-from-tickets` within 60 seconds for a batch of up to 10 tickets under normal LLM latency conditions.

---

### Requirement 6: API Catalog Awareness (Swagger-Grounded Generation)

**User Story:** As a QA engineer, I want the generator to use the existing API catalog from a Swagger/OpenAPI spec as grounding context, so that generated test cases reference real endpoints even when JIRA tickets lack explicit API details.

#### Acceptance Criteria

1. THE Swagger_Service SHALL fetch and parse the OpenAPI spec from the URL configured via the `SWAGGER_URL` environment variable at application startup, and cache the result in memory for the lifetime of the process.
2. IF the `SWAGGER_URL` environment variable is missing or the spec cannot be fetched at startup, THEN THE Swagger_Service SHALL log a warning and continue without catalog context rather than preventing startup.
3. WHEN generating a Postman_Collection from a Ticket, THE LLM_Service SHALL include the API_Catalog (endpoints, HTTP methods, summaries, and request/response schemas) as grounding context in its prompt.
4. WHEN a Ticket lacks explicit API details (no endpoint path, no HTTP method, no payload), THE LLM_Service SHALL analyze the Ticket summary and description to identify the most relevant APIs from the API_Catalog that would be needed to implement or test the described feature.
5. WHEN the LLM_Service determines that a feature requires APIs not present in the API_Catalog, THE LLM_Service SHALL infer those APIs from the Ticket context and include the corresponding Test_Cases in the collection, marking each as an Inferred_Test_Case.
6. WHEN a Test_Case is an Inferred_Test_Case, THE Generator SHALL prefix its request name with `[Inferred]` and include a note in the request description indicating the endpoint was not found in the API_Catalog, so QA engineers know to verify it before running.
7. WHEN a JIRA story has subtask child issues, THE JIRA_Service SHALL fetch those subtasks and include their summaries and descriptions as additional context alongside the parent Ticket during generation.
8. WHEN subtask content contains explicit API details (endpoint path, HTTP method, or payload), THE LLM_Service SHALL treat that information as higher-priority context than API_Catalog inference.
9. IF the LLM_Service cannot confidently identify any relevant APIs even with API_Catalog context, THEN THE Generator SHALL return a warning in the response describing what information would improve the result, and SHALL include whatever best-effort Test_Cases it could produce.

---

### Requirement 7: End-to-End Flow Chaining

**User Story:** As a QA engineer, I want the generated Postman collection to include all prerequisite and dependent API calls in the correct execution order, with response values automatically wired into subsequent requests, so that I can run the collection end-to-end without manually setting up test data.

#### Acceptance Criteria

1. WHEN generating a collection for a feature, THE LLM_Service SHALL analyze the API_Catalog and ticket context to identify all prerequisite APIs required before the primary feature API can be called (e.g., authentication, entity lookups, setup calls).
2. THE LLM_Service SHALL order Flow_Steps such that each API call appears after all calls it depends on.
3. WHEN a Flow_Step produces a response value that is required as input to a subsequent Flow_Step (e.g., an ID, a token), THE Generator SHALL include a Variable_Extraction test script in the earlier step that stores that value as a Postman environment variable.
4. WHEN a Flow_Step consumes a value extracted by a previous step, THE Generator SHALL reference that value using the Postman `{{variableName}}` syntax in the request URL, headers, or body.
5. THE LLM_Service SHALL include at minimum: any required authentication/token call, any entity-lookup calls needed to obtain valid IDs, the primary feature API call(s), and any cleanup or teardown calls if applicable.
6. WHEN a prerequisite API is sourced from the API_Catalog (not inferred), THE Generator SHALL NOT prefix it with `[Inferred]`.
7. THE Generator SHALL group all Flow_Steps for a feature into a single named folder in the Postman collection, ordered by execution sequence.
8. IF the LLM_Service cannot determine the full dependency chain, it SHALL include the steps it can identify and add a warning listing which dependencies could not be resolved.
