# frontend/api-client Specification

## Purpose

The api-client capability defines the frontend-backend communication boundary, providing base URL resolution (BFF proxy vs direct API), structured request and response logging interceptors, action-encapsulated HTTP communication with BFF headers, and error propagation to Redux thunks.

## Requirements

### Requirement: Base URL and proxy resolution
The API client layer SHALL configure a shared Axios instance (`apiClient`) with a default timeout and JSON content-type header, targeting relative `/api/*` endpoints delegated to the BFF proxy.

#### Scenario: Relative path resolution under BFF proxy
- **WHEN** an API request is initiated by any service client
- **THEN** the request targets `/api/*`, delegating upstream routing to the BFF proxy server

#### Scenario: Configured default request timeout and headers
- **WHEN** the shared `apiClient` instance is initialized
- **THEN** it sets `timeout = 10000` and default `Content-Type: application/json` headers

### Requirement: Structured request and response logging interceptors
The API client layer SHALL intercept all outgoing requests, successful responses, and network/server errors to emit structured log messages using the project logger utility (`logUtil`).

#### Scenario: Outgoing request logged at debug level
- **WHEN** any HTTP request is dispatched through `apiClient`
- **THEN** the request interceptor logs the HTTP method, request URL, and base URL at debug level

#### Scenario: Successful response logged at debug level
- **WHEN** an HTTP response is received
- **THEN** the response interceptor logs the HTTP method, URL, status code, and status text at debug level

#### Scenario: HTTP response error logged with status and payload
- **WHEN** the server returns an HTTP 4xx or 5xx error response
- **THEN** the error interceptor logs the error with HTTP status, URL, and response data payload

#### Scenario: Network failure without response logged
- **WHEN** a request fails due to network disconnection or timeout without receiving a server response
- **THEN** the error interceptor logs a "No response received from server" error with the request method and URL

### Requirement: Action-encapsulated HTTP communication
API calls SHALL be organized into domain-specific action modules (e.g. `flow-actions`, `project-actions`) that encapsulate endpoint paths, attach standard BFF headers (`Accept`, `X-Requested-With`), and return typed Axios responses.

#### Scenario: Domain action attaches BFF headers
- **WHEN** a domain action (such as `createFlow`) issues a mutation request
- **THEN** the request sends `Accept: application/json` and `X-Requested-With: XMLHttpRequest` headers to the BFF endpoint

#### Scenario: Domain action returns typed response payload
- **WHEN** an API action succeeds
- **THEN** the promise resolves with the typed `AxiosResponse` containing the domain payload

### Requirement: Error logging and propagation to Redux thunks
Domain API actions SHALL log operational errors with contextual details and re-throw caught exceptions so that calling Redux thunks can handle rejections and populate slice error state.

#### Scenario: Action failure logs contextual error and re-throws
- **WHEN** an API call within an action module fails
- **THEN** the action logs an error with module-specific context via `logUtil.error` and re-throws the error for the Redux thunk caller
