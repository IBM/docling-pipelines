## ADDED Requirements

### Requirement: Server starts and registers all tools
The MCP server SHALL start via stdio transport, register all documentation tools, and be ready to handle requests without requiring external services or network access.

#### Scenario: Clean startup
- **WHEN** the server process is launched with `python -m docs_mcp` or `uv run docs_mcp`
- **THEN** the server SHALL emit readiness over stdio and all tools SHALL be callable within 3 seconds

#### Scenario: Startup without docs directory
- **WHEN** the `docs/` directory is missing or empty
- **THEN** the server SHALL start successfully and return empty results from search/list tools rather than crashing

### Requirement: Tool routing resolves requests to handlers
The server SHALL route incoming MCP tool calls to the correct handler based on the tool name.

#### Scenario: Unknown tool name
- **WHEN** a client calls a tool name not registered by the server
- **THEN** the server SHALL return an MCP error response with a descriptive message

#### Scenario: Handler error is contained
- **WHEN** a registered tool handler raises an exception
- **THEN** the server SHALL return an MCP error response and remain running — it SHALL NOT crash the server process
