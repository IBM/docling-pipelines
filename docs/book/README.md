# Docling-pipelines Documentation

AsciiDoc sources compiled into a **static website** and a **PDF book** from the same
12-chapter source files. Two Podman images are required — both must be available locally.

## Requirements

| Tool | Image / Binary | Purpose |
|---|---|---|
| `podman` or `docker` | — | Container runtime (podman preferred; docker used as fallback) |
| `docker.io/antora/antora` | site build | Antora static site generator |
| `docker.io/asciidoctor/docker-asciidoctor` | PDF build | asciidoctor-pdf |
| `zip` | system binary | UI bundle assembly (`brew install zip` / `apt install zip`) |

Pull the images once:

```bash
# podman
podman pull docker.io/antora/antora
podman pull docker.io/asciidoctor/docker-asciidoctor

# or docker
docker pull docker.io/antora/antora
docker pull docker.io/asciidoctor/docker-asciidoctor
```

---

## Quick Start

```bash
cd docs/book

./build-site.sh      # → docs/book/site/index.html
./build-pdf.sh       # → docling-pipelines-guide.pdf
```

---

## Static Website

Builds a multi-page HTML site using `docker.io/antora/antora`.
Theme: dark IBM navy + cyan, syntax highlighting, copy buttons,
per-page TOC, and prev/next pagination.

```bash
cd docs/book

./build-site.sh           # build only
./build-site.sh --serve   # build then serve at http://localhost:8080
```

The `--serve` option uses `python3 -m http.server` — no additional install needed.

### What the build does

1. **Sync** — Copies `chapters/*.adoc` into `modules/ROOT/pages/`.
2. **UI bundle** — Runs `build-ui-bundle.sh` to assemble the Handlebars + CSS + JS
   theme into `ui/ui-bundle.zip`.
3. **Antora** — Runs `antora` inside the Podman container, mounting the repo root
   as `/repo` (git source) and `docs/book/` as `/antora` (playbook + output).
   The generated site is written to `docs/book/site/`.

---

## PDF Book

Builds a print-ready A4 PDF using `docker.io/asciidoctor/docker-asciidoctor`.
Theme: white page, IBM navy headings, cyan accents, `rouge` syntax highlighting,
running header/footer with page numbers.

```bash
cd docs/book

./build-pdf.sh                      # → docling-pipelines-guide.pdf
./build-pdf.sh --open               # build + open immediately
./build-pdf.sh --out /tmp/my.pdf    # custom output path
```

### Script flags

| Flag | Description |
|---|---|
| `--open` | Open the PDF after building (macOS: `open`, Linux: `xdg-open`). |
| `--out <path>` | Write to a custom path instead of `docling-pipelines-guide.pdf`. |
| `--help` | Print usage and exit. |

### How it works

Mounts `docs/book/` as `/documents` and runs `asciidoctor-pdf`:

```bash
podman run --rm \
  -v "${SCRIPT_DIR}:/documents:Z" \
  -w /documents \
  docker.io/asciidoctor/docker-asciidoctor \
  asciidoctor-pdf \
  -a pdf-themesdir=/documents \
  -a pdf-theme=docling-pipelines \
  toc.adoc
```

The PDF theme is defined in [`docling-pipelines-theme.yml`](docling-pipelines-theme.yml).

---

## File Structure

```
docs/book/
├── toc.adoc                          # Master include list + PDF title-page attributes
├── docling-pipelines-theme.yml       # asciidoctor-pdf print theme (A4, IBM navy/cyan)
├── antora-playbook.yml               # Antora site configuration
├── antora.yml                        # Antora component descriptor
├── build-site.sh                     # Builds the static HTML site via Podman
├── build-pdf.sh                      # Builds the PDF via Podman
├── build-ui-bundle.sh                # Assembles the Antora UI bundle ZIP
├── chapters/                         # AsciiDoc source (shared by site + PDF)
│   ├── 01_introduction_and_architecture.adoc
│   ├── 02_installation_and_quick_start.adoc
│   ├── 03_authoring_flows.adoc
│   ├── 04_ingesting_data.adoc
│   ├── 05_extracting_and_processing_documents.adoc
│   ├── 06_data_quality_and_enrichment.adoc
│   ├── 07_vector_storage_and_retrieval.adoc
│   ├── 08_llm_integration.adoc
│   ├── 09_python_api_and_programmatic_usage.adoc
│   ├── 10_extending_docling_pipelines.adoc
│   ├── 11_production_deployment_and_observability.adoc
│   └── 12_troubleshooting_and_contributing.adoc
├── modules/
│   └── ROOT/
│       ├── nav.adoc         # Sidebar navigation tree
│       └── pages/           # Synced from chapters/ at build time (generated)
├── ui-src/                  # Web theme source
│   ├── css/site.css         # Dark IBM-inspired stylesheet (CSS variables)
│   ├── js/site.js           # Copy buttons, active TOC, highlight.js init
│   ├── layouts/
│   │   ├── default.hbs      # Handlebars page layout
│   │   └── 404.hbs          # 404 error page layout
│   ├── partials/            # header, footer, nav, breadcrumbs, pagination, toc
│   └── helpers/             # eq, or, year, relativizeUrlPath Handlebars helpers
├── ui/
│   └── ui-bundle.zip        # Compiled UI bundle (generated)
├── site/                    # Generated static HTML (generated, under docs/book/)
└── docling-pipelines-guide.pdf       # Generated PDF (generated)
```

---

## Customising the Web Theme

Edit [`ui-src/css/site.css`](ui-src/css/site.css). All colours are CSS variables at
the top of the file:

```css
:root {
  --color-bg:       #0f1117;   /* page background        */
  --color-accent:   #33b1ff;   /* cyan highlight / links */
  --color-text:     #d4dbe8;   /* body text              */
  --color-nav-bg:   #161b27;   /* sidebar background     */
  /* … */
}
```

Re-run `./build-site.sh` to apply changes.

## Customising the PDF Theme

Edit [`docling-pipelines-theme.yml`](docling-pipelines-theme.yml). All colours are inlined hex values.
Key sections: `base` (body font/colour), `heading` (h1-h6), `table.head`, `title_page`.

Re-run `./build-pdf.sh` to apply changes.
