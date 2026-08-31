## ADDED Requirements

### Requirement: get_operator returns the full readme for a named operator
The `get_operator` tool SHALL accept an `operator_name` argument (the operator's `short_name`, e.g. `chunker`, `embeddings`, `vectordb`) and return the complete markdown content of that operator's readme file.

#### Scenario: Known operator name
- **WHEN** a client calls `get_operator` with `operator_name="chunker"`
- **THEN** the tool SHALL return the full contents of `docs/operators/functional/chunker_readme.md`

#### Scenario: Unknown operator name
- **WHEN** a client calls `get_operator` with an unrecognised name
- **THEN** the tool SHALL return an error message listing the valid operator names

#### Scenario: Operator name matching is case-insensitive
- **WHEN** a client calls `get_operator` with `operator_name="Chunker"` or `"CHUNKER"`
- **THEN** the tool SHALL resolve it to the correct file

### Requirement: list_operators returns all operators with category and summary
The `list_operators` tool SHALL return a structured list of all operators, each entry containing: `short_name`, `category`, and a one-line description derived from the first non-heading paragraph of the operator's readme.

#### Scenario: Full operator listing
- **WHEN** a client calls `list_operators` with no arguments
- **THEN** the response SHALL include all operators present in `docs/operators/`
- **THEN** each entry SHALL have `short_name`, `category`, and `description` fields

#### Scenario: Filter by category
- **WHEN** a client calls `list_operators` with `category="quality"`
- **THEN** only operators in the Quality category SHALL be returned

### Requirement: Operator name-to-file mapping is derived from the docs directory structure
The operator lookup SHALL resolve operator names by scanning the `docs/operators/<category>/` directories for `*_readme.md` files and deriving the short name from the filename — it SHALL NOT use a hardcoded map.

#### Scenario: New operator readme added to docs
- **WHEN** a new file `docs/operators/functional/my_operator_readme.md` is added to the repo
- **THEN** after server restart, `get_operator("my_operator")` SHALL return its contents without any code changes
