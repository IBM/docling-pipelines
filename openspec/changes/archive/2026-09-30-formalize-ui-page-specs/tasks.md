# Tasks

## 1. Archive the change

- [ ] 1.1 Run `openspec validate formalize-ui-page-specs` and verify it reports no errors before archiving
- [ ] 1.2 Run `openspec archive --change formalize-ui-page-specs` and verify the following five files are created under `openspec/specs/`: `home-page/spec.md`, `projects-page/spec.md`, `project-detail-page/spec.md`, `flow-detail-page/spec.md`, `run-details-page/spec.md`
- [ ] 1.3 Run `openspec list --specs` and verify all five capabilities appear alongside `canvas-page`
- [ ] 1.4 Spot-check one capability with `openspec show "flow-detail-page" --type spec` and verify the Purpose section and all requirements are present
