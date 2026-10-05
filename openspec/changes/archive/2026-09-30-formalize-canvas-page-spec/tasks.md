# Tasks

## 1. Archive the change

- [ ] 1.1 Run `openspec validate --change formalize-canvas-page-spec` and verify it reports no errors before archiving
- [ ] 1.2 Run `openspec archive --change formalize-canvas-page-spec` and verify `openspec/specs/canvas-page/spec.md` is created at the repo root with the Purpose section and all requirements present
- [ ] 1.3 Verify `openspec list --specs` lists `canvas-page` and `openspec show "canvas-page" --type spec` returns the full capability with all 18 requirements
