# Spec Delta

## MODIFIED Requirements

### Requirement: VectorDB feature mapping and backend configuration
The VectorDB custom panel SHALL support database backend selection (OpenSearch / Milvus / Weaviate), index/collection naming, and a feature mapping tearsheet that manages embeddings-to-field bindings and calls the feature enrichment endpoint.

#### Scenario: Backend selection displays relevant configuration fields
- **WHEN** the user selects "OpenSearch", "Milvus", or "Weaviate" as the vector database provider
- **THEN** provider-specific connection and index settings are displayed

#### Scenario: Feature mapping tearsheet manages embedding field bindings
- **WHEN** the user opens the feature mapping tearsheet
- **THEN** upstream embedding features and document metadata can be mapped to vector database payload fields

## ADDED Requirements

### Requirement: Weaviate resource and similarity settings
When the provider is Weaviate, the panel and tearsheet SHALL store the resource name under `provider_config.collection_name` and the similarity choice under `provider_config.distance_metric`. Labels SHALL read "collection" and "Distance metric", and options SHALL come from operator metadata (or `cosine`, `dot`, `l2-squared`, `manhattan`, `hamming` when absent).

#### Scenario: Saving mappings for Weaviate
- **WHEN** the user selects collection `DocsChunks` and distance metric `cosine` in the tearsheet and saves with the sparse checkbox unchecked
- **THEN** `provider_config` contains `collection_name: "DocsChunks"` and `distance_metric: "cosine"`, does not contain `index_name`, and `add_sparse_vector` is saved as false

### Requirement: Weaviate sparse (BM25) toggle
For Weaviate, the tearsheet SHALL render the sparse retrieval checkbox, as for Milvus, labeled "Enable BM25 sparse retrieval for hybrid search". Toggling it SHALL re-run enrichment with the new value and refresh the mapping rows. Saving SHALL persist `add_sparse_vector` as the checkbox state. The checkbox SHALL be hidden for unsupported collections and SHALL toggle with Space.

#### Scenario: Enable sparse retrieval
- **WHEN** the user checks the sparse checkbox for a Weaviate node and saves
- **THEN** enrichment is re-requested with `add_sparse_vector: true`, the refreshed rows include `content` mapped to `text`, and `add_sparse_vector: true` is persisted

#### Scenario: Keyboard toggle
- **WHEN** keyboard focus is on the sparse checkbox and the user presses Space
- **THEN** the checkbox toggles and enrichment is re-requested exactly as for a pointer click

#### Scenario: Milvus label unchanged
- **WHEN** the provider is Milvus
- **THEN** the checkbox label remains "Compute sparse vectors for hybrid search"

#### Scenario: Hidden for unsupported collection
- **WHEN** the selected existing Weaviate collection is reported as unsupported
- **THEN** the sparse checkbox is not rendered

### Requirement: Weaviate collection name validation gating
For Weaviate, the tearsheet SHALL validate a newly entered collection name against `^[A-Z][_0-9A-Za-z]*$`. It SHALL show the invalid state with helper text explaining the rule, and keep the tearsheet's save action disabled until the name is valid. Existing collections chosen from `available_resources` SHALL be accepted as-is.

#### Scenario: Lowercase first letter
- **WHEN** the user types `docs` as a new Weaviate collection name
- **THEN** the input shows the invalid state with text stating that names must start with an uppercase letter and contain only letters, digits, and underscores, and the save action is disabled

#### Scenario: Valid name enables save
- **WHEN** the user corrects the name to `Docs` and all required mappings are present
- **THEN** the invalid state clears and the save action is enabled

### Requirement: Weaviate connection configuration
For Weaviate, the Connection accordion SHALL offer a deployment selector with Self-hosted and Weaviate Cloud. Self-hosted SHALL show Host (default `localhost`), HTTP port (default `8080`), gRPC host (blank means use Host), gRPC port (default `50051`), and a Secure (TLS) toggle. Weaviate Cloud SHALL show a required Cluster URL. Values persist into `provider_config`.

#### Scenario: Switch to Weaviate Cloud
- **WHEN** the user changes the deployment from Self-hosted to Weaviate Cloud
- **THEN** host, port, gRPC, and secure fields are hidden and removed from `provider_config` in one update, `connection_type` is saved as `cloud`, and the Cluster URL field is shown

#### Scenario: Defaults sent to enrichment
- **WHEN** the user opens the feature mapping tearsheet without editing the self-hosted connection fields
- **THEN** the enrichment request's `provider_config` includes `connection_type: "custom"`, `host: "localhost"`, `port: 8080`, and `grpc_port: 50051`

#### Scenario: Cloud requires cluster URL
- **WHEN** the deployment is Weaviate Cloud and the Cluster URL is empty
- **THEN** the Cluster URL field shows the invalid state and the feature mapping tearsheet cannot be opened

### Requirement: Weaviate authentication configuration
For Weaviate, the Authentication accordion SHALL offer None, API key, Bearer token, and OIDC username/password. Secrets SHALL use the shared masked vault input and plain values SHALL use text inputs. Switching method SHALL remove the previous method's credentials and save the new `auth_type` in one update. Weaviate Cloud SHALL default to API key.

#### Scenario: Switching method clears previous credentials
- **WHEN** an API key is saved and the user switches the method to OIDC username/password
- **THEN** `api_key` is removed and `auth_type: "client_password"` is saved in one `provider_config` update, and Username and Password fields are shown

#### Scenario: Required credential missing
- **WHEN** the method is API key and the API key field is empty
- **THEN** the API key field shows the invalid state and the feature mapping tearsheet cannot be opened

#### Scenario: Managed keys excluded from Advanced JSON
- **WHEN** Weaviate connection and authentication fields have values
- **THEN** the Advanced JSON textarea shows only keys not managed by those fields or by the tearsheet, and editing it never overwrites managed keys

### Requirement: Weaviate panel accessibility
Every Weaviate field SHALL have a visible label associated with its control. Dropdowns SHALL be operable with the keyboard (Enter/Space to open, arrow keys to move, Enter to select, Escape to close). Fields revealed by a selection SHALL follow the selector in tab order, and invalid fields SHALL expose their error text to assistive technology.

#### Scenario: Keyboard-only method change
- **WHEN** a keyboard user focuses the authentication method dropdown, presses Enter, moves with the arrow keys to "API key", and presses Enter
- **THEN** the API key field is rendered and is the next focusable element after the dropdown

#### Scenario: Invalid field announced
- **WHEN** the Cluster URL field is in the invalid state
- **THEN** the field is marked `aria-invalid="true"` and its error text is referenced as the field's accessible description

### Requirement: Weaviate enrichment loading, error, and empty states
For Weaviate, the tearsheet SHALL show a loading indicator while enrichment is in flight and disable save until it settles. A failed enrichment SHALL show an inline error telling the user to check connection settings, and SHALL still allow entering a new collection name. An empty `available_resources` list SHALL show only the "Create new" option. The new-name placeholder SHALL be a valid Weaviate name.

#### Scenario: Enrichment fails
- **WHEN** the enrichment request for a Weaviate node returns an error
- **THEN** an inline error notification states that available resources failed to load and asks the user to check connection settings, last-saved mappings remain visible, and the user can still enter a new collection name

#### Scenario: Placeholder is a valid name
- **WHEN** "Create new" is selected for a Weaviate node
- **THEN** the new-name input's placeholder is a name that passes Weaviate collection-name validation (for example `MyCollection`)

#### Scenario: No existing collections
- **WHEN** enrichment succeeds with an empty `available_resources`
- **THEN** the collection selector offers only "Create new"
