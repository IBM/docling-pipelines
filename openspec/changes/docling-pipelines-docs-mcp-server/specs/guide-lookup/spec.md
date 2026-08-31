## ADDED Requirements

### Requirement: get_guide returns the full content of a named guide
The `get_guide` tool SHALL accept a `guide_name` argument (a slug derived from the filename, e.g. `flow-authoring-format`, `custom-operators-guide`) and return the complete markdown content of that guide file.

#### Scenario: Known guide slug
- **WHEN** a client calls `get_guide` with `guide_name="custom-operators-guide"`
- **THEN** the tool SHALL return the full contents of `docs/guides/CUSTOM_OPERATORS_GUIDE.md`

#### Scenario: Unknown guide slug
- **WHEN** a client calls `get_guide` with an unrecognised slug
- **THEN** the tool SHALL return an error message listing valid guide slugs

#### Scenario: Guide name matching is case-insensitive
- **WHEN** a client calls `get_guide` with `guide_name="FLOW-AUTHORING-FORMAT"` or `"Flow-Authoring-Format"`
- **THEN** the tool SHALL resolve it to the correct file

### Requirement: list_guides returns all available guides with titles and slugs
The `list_guides` tool SHALL return a structured list of all guides under `docs/guides/`, each entry containing: `slug` (the kebab-case name used as the `get_guide` argument) and `title` (the first `#`-level heading in the file, falling back to the filename).

#### Scenario: Full guide listing
- **WHEN** a client calls `list_guides` with no arguments
- **THEN** the response SHALL include all `.md` files present in `docs/guides/`
- **THEN** each entry SHALL have `slug` and `title` fields

### Requirement: Guide slug-to-file mapping is derived from the docs directory
The guide lookup SHALL derive slugs from filenames in `docs/guides/` — it SHALL NOT use a hardcoded map.

#### Scenario: New guide added to docs/guides
- **WHEN** a new file `docs/guides/MY_NEW_GUIDE.md` is added
- **THEN** after server restart, `get_guide("my-new-guide")` SHALL return its contents without code changes
