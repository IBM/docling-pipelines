# Adding a New Operator to the Frontend

This guide documents every file you need to touch when adding a new operator to the
pipeline canvas UI. Follow the steps in order — each one builds on the previous.

The Document Classifier operator (`document_classifier`) was implemented following
this exact checklist and can be used as a reference implementation throughout.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Node | ≥ 20 (see `.nvmrc`) |
| npm  | bundled with Node |

```bash
cd frontend
npm install          # install deps if not already done
npm run dev          # start dev server at http://localhost:3000
```

---

## Checklist

### 1. Palette JSON — register the node in the left palette

**File:** `frontend/src/data/operatorPalette.json`

Add a new object inside the correct `categories[].node_types` array.
Every operator needs:

- `id` — unique string (use the operator name, e.g. `document_classifier`)
- `op`  — the runtime operator key (matches Python backend, e.g. `document_classifier`)
- `inputs` / `outputs` — port definitions (use `min: 1, max: 1` for a single in/out)
- `app_data.ui_data.label` — display name shown in the palette card
- `app_data.ui_data.description` — one-line description shown on hover

```jsonc
{
  "id": "document_classifier",
  "type": "execution_node",
  "op": "document_classifier",
  "inputs": [
    {
      "id": "document_classifier_inPort",
      "app_data": {
        "ui_data": { "cardinality": { "min": 1, "max": 1 }, "label": "Input Port" }
      }
    }
  ],
  "outputs": [
    {
      "id": "document_classifier_outPort",
      "app_data": {
        "ui_data": { "cardinality": { "min": 1, "max": 1 }, "label": "Output Port" }
      }
    }
  ],
  "app_data": {
    "ui_data": {
      "label": "Document Classifier",
      "description": "Classify documents into predefined types using LLM"
    }
  }
}
```

> Operators with no inputs (source nodes, e.g. Ingest) omit the `inputs` array entirely.

---

### 2. Operator constant — add the op key as a typed constant

**File:** `frontend/src/constants/operators.ts`

Add a new entry to the `NodeOperator` object. The value **must** match the `op` field
used in `operatorPalette.json` and the Python backend.

```ts
/** Document classification using LLM */
DOCUMENT_CLASSIFIER: 'document_classifier',
```

This gives you a typed constant (`NodeOperator.DOCUMENT_CLASSIFIER`) that every other
file imports instead of using raw strings.

---

### 3. Operator label — add display text for the properties panel header

**File:** `frontend/src/constants/operatorLabels.ts`

Add an entry to `OPERATOR_LABELS` keyed by your new constant:

```ts
[NodeOperator.DOCUMENT_CLASSIFIER]: {
  label: 'Document Classifier',
  description:
    'Classify documents into predefined types using an LLM (litellm or watsonx providers).',
},
```

`label` appears in the panel header; `description` appears below the display-name input.

---

### 4. Palette icon — map the operator to a Carbon icon

**File:** `frontend/src/utils/paletteEnhancer.tsx`

**4a.** Import a suitable icon from `@carbon/icons-react`:

```ts
import {
  // ... existing imports ...
  Category,          // ← add your chosen icon
} from '@carbon/icons-react';
```

Browse available icons at https://carbondesignsystem.com/elements/icons/library/

**4b.** Add the mapping to `OPERATOR_ICON_MAP`:

```ts
[NodeOperator.DOCUMENT_CLASSIFIER]: <Category size={20} />,
```

The icon appears both in the palette card and in the properties panel header.

---

### 5. Parameter definition JSON — declare the operator's parameters

**File:** `frontend/public/parameterDefs/<op>_paramDef.json`
(e.g. `document_classifier_paramDef.json`)

This file tells Elyra's `CommonProperties` which parameters exist. The `group_info`
entry routes rendering to the shared `common_properties_panel` custom panel, which
in turn renders your TSX component (Step 7).

```jsonc
{
  "parameters": [
    { "id": "provider" },
    { "id": "provider_config" }
    // ... one entry per parameter
  ],
  "uihints": {
    "editor_size": "medium",
    "id": "<op>_cpd_uihints",
    "parameter_info": [
      { "parameter_ref": "provider" },
      { "parameter_ref": "provider_config" }
    ],
    "group_info": [
      {
        "id": "common_properties_panel",
        "type": "customPanel"
      }
    ]
  }
}
```

> The file is served statically. The service at
> `frontend/src/services/parameterDefs/parameterDefsService.ts` fetches it via
> `GET /ui/parameterDefs/<op>_paramDef.json` when the user opens a node for editing.

---

### 6. SCSS module — styles scoped to the panel body

**File:** `frontend/src/components/PropertiesPanel/CustomPanels/<OperatorName>/<OperatorName>.module.scss`

Create a CSS Modules file for any layout specific to your panel. Use Carbon spacing
and type tokens — avoid hard-coded values.

```scss
@use '@carbon/react/scss/spacing' as *;
@use '@carbon/react/scss/theme' as *;
@use '@carbon/react/scss/type';

.panelBody {
  display: flex;
  flex-direction: column;
  gap: $spacing-05;
}

.sectionHeading {
  @include type.type-style('label-01');
  color: $text-secondary;
  text-transform: uppercase;
}

.divider {
  border: none;
  border-top: 1px solid $border-subtle-01;
  margin: 0;
}
```

If your panel only uses standard Carbon components with no custom layout, this file
can be omitted and you can reference `CommonPropertiesPanel.module.scss` instead.

---

### 7. TSX panel component — the configuration UI

**File:** `frontend/src/components/PropertiesPanel/CustomPanels/<OperatorName>/<OperatorName>.tsx`

This is the React component that Elyra renders inside the right-flyout properties
panel when a user double-clicks (or right-click → Edit) a node on the canvas.

**Key patterns:**

```tsx
import React from 'react';
import { TextInput, NumberInput, Toggle, Dropdown } from '@carbon/react';
import styles from './<OperatorName>.module.scss';

interface <OperatorName>PanelBodyProps {
  controller: any;
}

export function <OperatorName>PanelBody({ controller }: <OperatorName>PanelBodyProps): React.JSX.Element {
  // ── 1. Read current values from Elyra controller ──────────────────────
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const myParam = (controller?.getPropertyValue?.({ name: 'my_param' }) as string | undefined) ?? 'default';

  // ── 2. Write updates back to the controller ────────────────────────────
  const update = (name: string, value: unknown): void => {
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    controller?.updatePropertyValue?.({ name }, value);
  };

  return (
    <div className={styles.panelBody}>
      <TextInput
        id="my_param"
        labelText="My parameter"
        value={myParam}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          update('my_param', e.target.value);
        }}
      />
    </div>
  );
}
```

**Rules:**
- Export the component as a **named export** (not default).
- Use Carbon components (`TextInput`, `NumberInput`, `Toggle`, `Dropdown`, `TextArea`).
- Map every parameter declared in the paramDef JSON to a corresponding control.
- Use `// eslint-disable-next-line @typescript-eslint/no-unsafe-call` above each
  `controller?.getPropertyValue` / `controller?.updatePropertyValue` call — these
  are typed `any` by the Elyra API.

---

### 8. Register the panel in CommonPropertiesPanel

**File:** `frontend/src/components/PropertiesPanel/CommonPropertiesPanel.tsx`

**8a.** Add the import near the top (alphabetical order within the imports block):

```ts
import { DocumentClassifierPanelBody } from './CustomPanels/DocumentClassifier/DocumentClassifier';
```

**8b.** Add the mapping to `OPERATOR_PANEL_MAP`:

```ts
const OPERATOR_PANEL_MAP: Record<string, React.ComponentType<{ controller: any }>> = {
  [NodeOperator.INGEST]: IngestPanelBody,
  [NodeOperator.DOCUMENT_CLASSIFIER]: DocumentClassifierPanelBody,  // ← add here
};
```

`CommonPropertiesPanel` uses this map to look up which component to render for
the currently-selected node's operator type.

---

## End-to-end data flow

```
User double-clicks node
        │
        ▼
Canvas.tsx editActionHandler
  └─ getParameterDef(operatorName)          ← fetches /ui/parameterDefs/<op>_paramDef.json
  └─ sets propertiesInfo → opens flyout
        │
        ▼
CommonProperties (Elyra)
  └─ renders customPanel: CommonPropertiesPanelWrapper
        │
        ▼
CommonPropertiesPanel
  └─ resolves operatorName from controller.getAppData()
  └─ looks up OPERATOR_PANEL_MAP[operatorName]
  └─ renders <YourPanelBody controller={controller} />
        │
        ▼
YourPanelBody
  └─ controller.getPropertyValue({ name })   → read
  └─ controller.updatePropertyValue({name},v) → write on change
        │
        ▼
User clicks Save → Elyra calls applyPropertyChanges
  └─ Canvas.tsx handleApplyPropertyChanges
  └─ canvasController.setNodeParameters(nodeId, propertySet)
```

---

## Quick reference — files to touch per new operator

| Step | File | What changes |
|------|------|--------------|
| 1 | `frontend/src/data/operatorPalette.json` | New node entry in correct category |
| 2 | `frontend/src/constants/operators.ts` | New `NodeOperator.X` constant |
| 3 | `frontend/src/constants/operatorLabels.ts` | Label + description for panel header |
| 4 | `frontend/src/utils/paletteEnhancer.tsx` | Icon import + `OPERATOR_ICON_MAP` entry |
| 5 | `frontend/public/parameterDefs/<op>_paramDef.json` | **New file** — parameter declaration |
| 6 | `frontend/src/components/PropertiesPanel/CustomPanels/<Op>/<Op>.module.scss` | **New file** — panel-scoped styles |
| 7 | `frontend/src/components/PropertiesPanel/CustomPanels/<Op>/<Op>.tsx` | **New file** — panel React component |
| 8 | `frontend/src/components/PropertiesPanel/CommonPropertiesPanel.tsx` | Import + `OPERATOR_PANEL_MAP` entry |

---

## Naming conventions

| Thing | Convention | Example |
|-------|-----------|---------|
| Operator key (op / constant value) | `snake_case` | `document_classifier` |
| `NodeOperator` constant | `SCREAMING_SNAKE` | `DOCUMENT_CLASSIFIER` |
| TSX component name | `PascalCase` + `PanelBody` suffix | `DocumentClassifierPanelBody` |
| Folder name | `PascalCase` | `DocumentClassifier/` |
| paramDef file | `<op>_paramDef.json` | `document_classifier_paramDef.json` |
| SCSS module | `<ComponentName>.module.scss` | `DocumentClassifier.module.scss` |
