#!/usr/bin/env python3
"""
md2html.py — Convert Markdown files to styled HTML pages.

Uses the same IBM navy/cyan design as docs/index.html and QUICKSTART.html.

Usage (from repo root):
    python3 docs/assets/md2html.py <input.md> [<output.html>]
    python3 docs/assets/md2html.py --all        # convert every tracked .md

When --all is used the script discovers all .md files listed in FILES below
and writes a sibling .html next to each one.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import markdown

# ── Files to convert when --all is used ─────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent  # repo root


def _get_version() -> str:
    """Read the current version from the most recent git tag (e.g. v1.0.1).
    Falls back to the version field in pyproject.toml, then to 'dev'."""
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return tag if tag else "v2.0"
    except Exception:
        pass
    # Fallback: parse pyproject.toml static version (not dynamic)
    try:
        import tomllib  # Python 3.11+

        with (ROOT / "pyproject.toml").open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "dev")
    except Exception:
        return "dev"


VERSION = "v2.0"  # updated manually; switch back to _get_version() once v2.0 is tagged

FILES = [
    # root-level
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "COMMUNITY.md",
    "CONTRIBUTING.md",
    "TROUBLESHOOTING.md",
    "USER_GUIDE_PIPELINE_SETUP.md",
    "README.md",
    # docs/api
    "docs/api/ACL_DOCUMENT_RETRIEVAL.md",
    "docs/api/OAUTH2_AUTHENTICATION.md",
    "docs/api/REST_API_SERVER.md",
    # docs/deployment
    "docs/deployment/OPENSHIFT.md",
    # docs/guides
    "docs/guides/ADVANCED_CONFIGURATION.md",
    "docs/guides/CREATE_CONNECTOR_GUIDE.md",
    "docs/guides/CUSTOM_OPERATORS_GUIDE.md",
    "docs/guides/DEPRECATION_POLICY.md",
    "docs/guides/DOCUMENTATION_STYLE_GUIDE.md",
    "docs/guides/DOCUMENT_CLASS_UTILS.md",
    "docs/guides/EXTERNAL_OPERATOR_INTEGRATION.md",
    "docs/guides/FLOW_AUTHORING_FORMAT.md",
    "docs/guides/FLOW_CONFIGURATION_GUIDE.md",
    "docs/guides/JOB_REPORT_GENERATION.md",
    "docs/guides/LOGGING_BEST_PRACTICES.md",
    "docs/guides/MIGRATION_GUIDE_TEMPLATE.md",
    "docs/guides/PYTHON_API_GUIDE.md",
    "docs/guides/SECURITY_BEST_PRACTICES.md",
    "docs/guides/SLIM_VARIANT.md",
    "docs/guides/TELEMETRY_SETUP.md",
    "docs/guides/TESTING_STANDARDS.md",
    "docs/guides/UI_USER_GUIDE.md",
    "docs/guides/UNIFIED_LLM_ARCHITECTURE_GUIDE.md",
    "docs/guides/USER_GUIDE_DOCUMENT_LIBRARIES.md",
    "docs/guides/VAULT_INTEGRATION_GUIDE.md",
    # docs/integrations
    "docs/integrations/milvus/README.md",
    "docs/integrations/opensearch/ENVIRONMENT_SETUP.md",
    "docs/integrations/opensearch/OPENSEARCH_QUICKSTART.md",
    "docs/integrations/opensearch/README.md",
    "docs/integrations/opensearch/SCHEMA_TEMPLATES.md",
    "docs/integrations/prefect/DISTRIBUTED_EXECUTION_GUIDE.md",
    "docs/integrations/vault/README.md",
    # docs/internals
    "docs/internals/DOCUMENT_LIBRARIES_ARCHITECTURE.md",
    "docs/internals/NODE_METADATA_AGGREGATION_STRATEGY.md",
    "docs/internals/UNIFIED_ASSET_ARCHITECTURE.md",
    # docs/operators — extract
    "docs/operators/extract/acl_readme.md",
    "docs/operators/extract/extract_operator_readme.md",
    # docs/operators — functional
    "docs/operators/functional/branching_operator_readme.md",
    "docs/operators/functional/chunker_readme.md",
    "docs/operators/functional/doc_id_hash_readme.md",
    "docs/operators/functional/embeddings_readme.md",
    "docs/operators/functional/entity_curation_readme.md",
    "docs/operators/functional/merge_readme.md",
    "docs/operators/functional/noop_readme.md",
    # docs/operators — ingest
    "docs/operators/ingest/ingest_source_readme.md",
    # docs/operators — quality
    "docs/operators/quality/doc_quality_readme.md",
    "docs/operators/quality/document_classifier_readme.md",
    "docs/operators/quality/ededup_readme.md",
    "docs/operators/quality/language_detection_readme.md",
    "docs/operators/quality/ml_enrichment_readme.md",
    "docs/operators/quality/pii_and_hap_readme.md",
    "docs/operators/quality/readability_readme.md",
    "docs/operators/quality/redaction_readme.md",
    "docs/operators/quality/sql_filter_readme.md",
    # docs/operators — storage
    "docs/operators/storage/README.md",
    "docs/operators/storage/document_set_readme.md",
    "docs/operators/storage/storage_output_readme.md",
    # docs/operators — vectordb
    "docs/operators/vectordb/milvus.md",
    "docs/operators/vectordb/opensearch.md",
    "docs/operators/vectordb/vectordb_readme.md",
    # docs/reference
    "docs/reference/DOCUMENT_SCHEMAS.md",
    "docs/reference/GLOBAL_CONFIG.md",
    "docs/reference/OPERATORS.md",
]

# ── Path helpers ─────────────────────────────────────────────────────────────


def css_path(html_file: Path) -> str:
    """Return relative path from html_file's directory to docs/assets/docs.css."""
    css = ROOT / "docs" / "assets" / "docs.css"
    return os.path.relpath(css, html_file.parent)


def docs_index_path(html_file: Path) -> str:
    docs_index = ROOT / "docs" / "index.html"
    return os.path.relpath(docs_index, html_file.parent)


def rel(html_file: Path, target: str) -> str:
    """Relative URL from html_file's dir to a repo-root-relative target path."""
    return os.path.relpath(ROOT / target, html_file.parent)


# ── Fixed site-wide left nav (generated per output file so paths are relative) ──


def build_site_nav(html_file: Path, current_rel: str) -> str:
    """
    Returns the HTML for the fixed left sidebar nav with collapsible sections.
    current_rel is the path of the output file relative to ROOT.
    The section containing the current page auto-expands; all others collapse.
    """
    cur = current_rel.replace("\\", "/")

    def link(href_target: str, label: str, cls: str = "") -> str:
        url = os.path.relpath(ROOT / href_target, html_file.parent)
        is_active = href_target == cur
        active = " active" if is_active else ""
        extra = f" {cls}" if cls else ""
        return f'        <a class="nav-link{extra}{active}" href="{url}"><span class="dot"></span>{label}</a>'

    def sublabel(text: str) -> str:
        return f'        <span class="nav-sublabel">{text}</span>'

    def divider() -> str:
        return '      <hr class="nav-divider">'

    def group(title: str, members: list, id_: str) -> list:
        """Wrap members in a collapsible .nav-group div."""
        has_active = any('class="nav-link' in m and "active" in m for m in members)
        open_cls = " open" if has_active else ""
        out = [
            f'      <div class="nav-group{open_cls}" id="ng-{id_}">',
            f'        <button class="nav-group-toggle" data-group="ng-{id_}">',
            f"          <span>{title}</span>",
            '          <span class="chev">&#x276F;</span>',
            "        </button>",
            '        <div class="nav-group-body">',
        ]
        out.extend(members)
        out.append("        </div>")
        out.append("      </div>")
        return out

    di = rel(html_file, "docs/index.html")
    lines = []

    # ── Overview (always visible, no toggle) ──────────────────────────────────
    lines.append('      <span class="nav-label">Overview</span>')
    is_home = cur == "docs/index.html"
    lines.append(
        f'      <a class="nav-link{" active" if is_home else ""}" href="{di}"><span class="dot"></span>Docs Home</a>'
    )

    # ── Getting Started (collapsible) ─────────────────────────────────────────
    lines.append(divider())
    gs_members = [
        link("QUICKSTART.html", "Quick Start"),
        link("USER_GUIDE_PIPELINE_SETUP.html", "Setup Guide"),
        link("TROUBLESHOOTING.html", "Troubleshooting"),
    ]
    lines.extend(group("Getting Started", gs_members, "getting-started"))

    # ── Documentation Book (collapsible) ──────────────────────────────────────
    book_members = [
        f'        <a class="nav-link" href="{rel(html_file, "docs/book/site/docling-pipelines/1.0/index.html")}"><span class="dot"></span>Book Home</a>',
    ]
    for slug, label in [
        ("01_introduction_and_architecture", "1. Introduction &amp; Architecture"),
        ("02_installation_and_quick_start", "2. Installation &amp; Quick Start"),
        ("03_authoring_flows", "3. Authoring Flows"),
        ("04_ingesting_data", "4. Ingesting Data"),
        ("05_extracting_and_processing_documents", "5. Extracting &amp; Processing"),
        ("06_data_quality_and_enrichment", "6. Data Quality &amp; Enrichment"),
        ("07_vector_storage_and_retrieval", "7. Vector Storage &amp; Retrieval"),
        ("08_llm_integration", "8. LLM Integration"),
        ("09_python_api_and_programmatic_usage", "9. Python API"),
        ("10_extending_docling_pipelines", "10. Extending"),
        ("11_production_deployment_and_observability", "11. Production Deployment"),
        ("12_troubleshooting_and_contributing", "12. Troubleshooting"),
    ]:
        target = f"docs/book/site/docling-pipelines/1.0/{slug}.html"
        url = os.path.relpath(ROOT / target, html_file.parent)
        book_members.append(f'        <a class="nav-link chapter" href="{url}"><span class="dot"></span>{label}</a>')
    lines.extend(group("Documentation Book", book_members, "book"))

    # ── Collapsible sections ──────────────────────────────────────────────────
    lines.append(divider())

    # Guides
    guides_members = [
        sublabel("Core"),
        link("docs/guides/FLOW_AUTHORING_FORMAT.html", "Flow Authoring Format", "chapter"),
        link("docs/guides/FLOW_CONFIGURATION_GUIDE.html", "Flow Configuration", "chapter"),
        link("docs/guides/PYTHON_API_GUIDE.html", "Python API Guide", "chapter"),
        sublabel("Developer"),
        link("docs/guides/CUSTOM_OPERATORS_GUIDE.html", "Custom Operators", "chapter"),
        link("docs/guides/CREATE_CONNECTOR_GUIDE.html", "Create Connector", "chapter"),
        link("docs/guides/EXTERNAL_OPERATOR_INTEGRATION.html", "External Operators", "chapter"),
        link("docs/guides/TESTING_STANDARDS.html", "Testing Standards", "chapter"),
        sublabel("Advanced"),
        link("docs/guides/ADVANCED_CONFIGURATION.html", "Advanced Configuration", "chapter"),
        link("docs/guides/SECURITY_BEST_PRACTICES.html", "Security Best Practices", "chapter"),
        link("docs/guides/UNIFIED_LLM_ARCHITECTURE_GUIDE.html", "Unified LLM Architecture", "chapter"),
        link("docs/guides/USER_GUIDE_DOCUMENT_LIBRARIES.html", "Document Libraries", "chapter"),
        link("docs/guides/VAULT_INTEGRATION_GUIDE.html", "Vault Integration", "chapter"),
        link("docs/guides/UI_USER_GUIDE.html", "UI User Guide", "chapter"),
        link("docs/guides/TELEMETRY_SETUP.html", "Telemetry Setup", "chapter"),
        link("docs/guides/SLIM_VARIANT.html", "Slim Variant", "chapter"),
        sublabel("Best Practices"),
        link("docs/guides/LOGGING_BEST_PRACTICES.html", "Logging Best Practices", "chapter"),
        link("docs/guides/DOCUMENTATION_STYLE_GUIDE.html", "Documentation Style", "chapter"),
        link("docs/guides/DEPRECATION_POLICY.html", "Deprecation Policy", "chapter"),
    ]
    lines.extend(group("Guides", guides_members, "guides"))

    # Operators
    op_members = [
        sublabel("Ingest"),
        link("docs/operators/ingest/ingest_source_readme.html", "IngestSource", "chapter"),
        sublabel("Extract"),
        link("docs/operators/extract/extract_operator_readme.html", "Extract", "chapter"),
        link("docs/operators/extract/acl_readme.html", "ACL Operator", "chapter"),
        sublabel("Functional"),
        link("docs/operators/functional/chunker_readme.html", "Chunker", "chapter"),
        link("docs/operators/functional/embeddings_readme.html", "Embeddings", "chapter"),
        link("docs/operators/functional/branching_operator_readme.html", "Branching", "chapter"),
        link("docs/operators/functional/merge_readme.html", "Merge", "chapter"),
        link("docs/operators/functional/doc_id_hash_readme.html", "Doc ID Hash", "chapter"),
        link("docs/operators/functional/entity_curation_readme.html", "Entity Curation", "chapter"),
        link("docs/operators/functional/noop_readme.html", "NOOP", "chapter"),
        sublabel("Quality"),
        link("docs/operators/quality/language_detection_readme.html", "Language Detection", "chapter"),
        link("docs/operators/quality/pii_and_hap_readme.html", "PII &amp; HAP", "chapter"),
        link("docs/operators/quality/redaction_readme.html", "Redaction", "chapter"),
        link("docs/operators/quality/doc_quality_readme.html", "Doc Quality", "chapter"),
        link("docs/operators/quality/ededup_readme.html", "Exact Deduplication", "chapter"),
        link("docs/operators/quality/sql_filter_readme.html", "SQL Filter", "chapter"),
        link("docs/operators/quality/ml_enrichment_readme.html", "ML Enrichment", "chapter"),
        link("docs/operators/quality/document_classifier_readme.html", "Document Classifier", "chapter"),
        link("docs/operators/quality/readability_readme.html", "Readability", "chapter"),
        sublabel("Storage"),
        link("docs/operators/storage/document_set_readme.html", "Document Set", "chapter"),
        link("docs/operators/storage/storage_output_readme.html", "Storage Output", "chapter"),
        sublabel("VectorDB"),
        link("docs/operators/vectordb/vectordb_readme.html", "VectorDB", "chapter"),
        link("docs/operators/vectordb/opensearch.html", "OpenSearch adapter", "chapter"),
        link("docs/operators/vectordb/milvus.html", "Milvus adapter", "chapter"),
    ]
    lines.extend(group("Operators", op_members, "operators"))

    # Reference
    ref_members = [
        link("docs/reference/GLOBAL_CONFIG.html", "Global Config"),
        link("docs/reference/OPERATORS.html", "Operator Reference"),
        link("docs/reference/DOCUMENT_SCHEMAS.html", "Document Schemas"),
    ]
    lines.extend(group("Reference", ref_members, "reference"))

    # REST API
    api_members = [
        link("docs/api/REST_API_SERVER.html", "REST API Server"),
        link("docs/api/ACL_DOCUMENT_RETRIEVAL.html", "Document Retrieval"),
        link("docs/api/OAUTH2_AUTHENTICATION.html", "OAuth2 / OIDC"),
    ]
    lines.extend(group("REST API", api_members, "restapi"))

    # Integrations
    int_members = [
        sublabel("OpenSearch"),
        link("docs/integrations/opensearch/OPENSEARCH_QUICKSTART.html", "Quick Start", "chapter"),
        link("docs/integrations/opensearch/ENVIRONMENT_SETUP.html", "Environment Setup", "chapter"),
        link("docs/integrations/opensearch/SCHEMA_TEMPLATES.html", "Schema Templates", "chapter"),
        link("docs/integrations/opensearch/README.html", "Overview", "chapter"),
        sublabel("Milvus"),
        link("docs/integrations/milvus/README.html", "Milvus Overview", "chapter"),
        sublabel("Prefect"),
        link("docs/integrations/prefect/DISTRIBUTED_EXECUTION_GUIDE.html", "Distributed Execution", "chapter"),
        sublabel("Vault"),
        link("docs/integrations/vault/README.html", "Vault Overview", "chapter"),
    ]
    lines.extend(group("Integrations", int_members, "integrations"))

    # Deployment
    dep_members = [
        link("docs/deployment/OPENSHIFT.html", "OpenShift Deployment"),
    ]
    lines.extend(group("Deployment", dep_members, "deployment"))

    # Internals
    int2_members = [
        link("docs/internals/DOCUMENT_LIBRARIES_ARCHITECTURE.html", "Document Libraries Arch"),
        link("docs/internals/NODE_METADATA_AGGREGATION_STRATEGY.html", "Metadata Aggregation"),
        link("docs/internals/UNIFIED_ASSET_ARCHITECTURE.html", "Unified Asset Arch"),
    ]
    lines.extend(group("Internals", int2_members, "internals"))

    # Contributing
    contrib_members = [
        link("ARCHITECTURE.html", "Architecture Overview"),
        link("CONTRIBUTING.html", "Contributing Guide"),
        link("CHANGELOG.html", "Changelog"),
        link("COMMUNITY.html", "Community"),
    ]
    lines.extend(group("Contributing", contrib_members, "contributing"))

    return "\n".join(lines)


# ── Rewrite .md → .html in href/src attributes ──────────────────────────────


def rewrite_md_links(html: str) -> str:
    """Turn href="foo.md" into href="foo.html" (keeps anchors intact)."""
    return re.sub(
        r'(href=["\'])([^"\'#?]+)\.md([#?][^"\']*)?(["\'])',
        lambda m: f"{m.group(1)}{m.group(2)}.html{m.group(3) or ''}{m.group(4)}",
        html,
    )


# ── Nav item extraction (h2 headings become TOC + sidebar) ──────────────────


def extract_toc(html: str):
    """Return list of (id, text) for every <h2> in the rendered HTML."""
    return re.findall(r'<h2[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</h2>', html, re.IGNORECASE)


# ── HTML wrapper ─────────────────────────────────────────────────────────────

TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" id="html-root">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title} — Docling Pipelines</title>
  <meta name="description" content="{title} — Docling Pipelines documentation.">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%2333b1ff'/><text x='16' y='22' font-family='IBM Plex Sans,system-ui,sans-serif' font-size='14' font-weight='700' fill='%230f1117' text-anchor='middle'>DP</text></svg>">
  <link rel="stylesheet" href="{css_path}">
  <style>
    /* ── Markdown content overrides ── */
    .main p  {{ margin: 0 0 .9em; font-size: 14px; }}
    .main ul, .main ol {{ padding-left: 1.5em; margin: 0 0 1em; }}
    .main li {{ margin: .35em 0; font-size: 14px; }}
    .main strong {{ color: var(--text-head); }}
    .main em {{ color: var(--text-dim); font-style: italic; }}
    .main blockquote {{
      border-left: 4px solid var(--accent-dim);
      background: var(--bg-card); border-radius: 0 var(--radius) var(--radius) 0;
      padding: 12px 18px; margin: 16px 0; color: var(--text-dim); font-size: 13.5px;
    }}
    .main pre {{
      background: var(--code-bg); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 18px 20px;
      overflow-x: auto; font-family: var(--mono);
      font-size: .85rem; line-height: 1.6; color: #e2e8f0;
      margin: 16px 0; position: relative;
    }}
    html.light .main pre {{ color: var(--text); }}
    .main code {{
      font-family: var(--mono); font-size: .85em;
      background: var(--code-bg); color: var(--accent);
      padding: 1px 5px; border-radius: 4px;
      border: 1px solid var(--border);
    }}
    .main pre code {{
      background: none; border: none; color: inherit;
      padding: 0; font-size: inherit;
    }}
    .main table {{
      width: 100%; border-collapse: collapse;
      margin: 16px 0 28px; font-size: 13.5px;
    }}
    .main table th {{
      background: var(--surface); color: var(--text-head); font-weight: 600;
      padding: 8px 14px; text-align: left; border: 1px solid var(--border);
      font-size: 11px; text-transform: uppercase; letter-spacing: .4px;
    }}
    .main table td {{
      padding: 8px 14px; border: 1px solid var(--border); vertical-align: top;
    }}
    .main table tr:nth-child(even) td {{ background: var(--bg-card); }}
    .main table tr:hover td {{ background: var(--surface); }}
    .main hr {{
      border: none; border-top: 1px solid var(--border); margin: 2em 0;
    }}
    /* breadcrumb */
    .breadcrumb {{
      font-size: 12px; color: var(--text-dim);
      display: flex; align-items: center; gap: 6px;
      margin-bottom: 28px; flex-wrap: wrap;
    }}
    .breadcrumb a {{ color: var(--text-dim); text-decoration: none; }}
    .breadcrumb a:hover {{ color: var(--accent); }}
    .breadcrumb .sep {{ color: var(--border); }}
    .breadcrumb .cur {{ color: var(--text); }}
    /* copy button */
    .main pre {{ position: relative; }}
    .copy-btn {{
      position: absolute; top: 10px; right: 10px;
      background: var(--surface); border: 1px solid var(--border);
      color: var(--text-dim); border-radius: 4px; cursor: pointer;
      padding: 3px 8px; font-size: 11px; font-family: var(--font);
      display: flex; align-items: center; gap: 4px;
      transition: color .15s, border-color .15s; opacity: 0;
    }}
    .main pre:hover .copy-btn {{ opacity: 1; }}
    .copy-btn:hover {{ color: var(--accent); border-color: var(--accent-dim); }}
    .copy-btn.copied {{ color: #34d399; border-color: #34d399; opacity: 1; }}
  </style>
</head>
<body>
<div class="shell">

  <header class="hdr">
    <a href="{docs_index}" class="logo">
      <div class="logo-mark">DP</div>
      <div>
        <div class="logo-text">Docling Pipelines</div>
        <div class="logo-sub">Documentation</div>
      </div>
    </a>
    <div class="hdr-right">
      <span class="badge-ver">{version}</span>
      <a href="https://github.com/IBM/docling-pipelines" target="_blank" rel="noopener" class="gh-link">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>
        IBM/docling-pipelines
      </a>
      <button class="theme-btn" id="theme-btn" title="Toggle light/dark mode" aria-label="Toggle theme">
        <svg class="icon-moon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg class="icon-sun"  width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      </button>
    </div>
  </header>

  <div class="body">

    <nav class="nav" aria-label="Site navigation">
{site_nav}
    </nav>

    <main class="main" id="top">
      <nav class="breadcrumb" aria-label="breadcrumb">
        <a href="{docs_index}">Docs</a>
        <span class="sep">&rsaquo;</span>
        <span class="cur">{title}</span>
      </nav>
      {body}
    </main>

    <aside class="toc" aria-label="On this page">
      <div class="toc-title">On this page</div>
{toc_aside}
    </aside>

  </div>

  <footer>
    <span>Docling Pipelines Documentation</span>
    <span>&middot;</span>
    <a href="{docs_index}">Docs Home</a>
    <span>&middot;</span>
    <a href="https://github.com/IBM/docling-pipelines" target="_blank" rel="noopener">GitHub</a>
    <span>&middot;</span>
    <a href="https://github.com/IBM/docling-pipelines/blob/main/LICENSE" target="_blank" rel="noopener">Apache 2.0</a>
  </footer>

</div>
<script>
(function(){{
  'use strict';
  var html=document.getElementById('html-root'),btn=document.getElementById('theme-btn'),KEY='dp-theme';
  function apply(t){{if(t==='light')html.classList.add('light');else html.classList.remove('light');try{{localStorage.setItem(KEY,t);}}catch(e){{}}}}
  var s=null;try{{s=localStorage.getItem(KEY);}}catch(e){{}}
  if(s)apply(s);else if(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches)apply('light');
  btn.addEventListener('click',function(){{apply(html.classList.contains('light')?'dark':'light');}});
  // TOC scroll spy
  var secs=document.querySelectorAll('h2[id]'),tl=document.querySelectorAll('.toc a');
  if(secs.length&&tl.length){{
    var obs=new IntersectionObserver(function(e){{e.forEach(function(x){{if(x.isIntersecting){{var id=x.target.id;tl.forEach(function(a){{a.classList.toggle('active',a.getAttribute('href')==='#'+id);}});}}}})}},{{rootMargin:'-60px 0px -70% 0px'}});
    secs.forEach(function(s){{obs.observe(s);}});
  }}
  // Nav group toggles
  document.querySelectorAll('.nav-group-toggle').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var g=btn.closest('.nav-group');
      if(g)g.classList.toggle('open');
    }});
  }});
  // Copy buttons
  document.querySelectorAll('.main pre').forEach(function(pre){{
    var b=document.createElement('button');b.className='copy-btn';
    b.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy';
    pre.appendChild(b);
    b.addEventListener('click',function(){{
      navigator.clipboard.writeText(pre.innerText||pre.textContent).then(function(){{
        b.classList.add('copied');b.textContent='Copied!';
        setTimeout(function(){{b.classList.remove('copied');b.innerHTML='<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg> Copy';}},2000);
      }});
    }});
  }});
}})();
</script>
</body>
</html>
"""


def slugify(text: str, sep: str = "-") -> str:
    text = re.sub(r"<[^>]+>", "", text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", sep, text)


def convert(md_path: Path, html_path: Path) -> None:
    src = md_path.read_text(encoding="utf-8")

    # Strip explicit [TOC] / [[_TOC_]] markers from source
    src = re.sub(r"^\s*\[{1,2}_?TOC_?\]{1,2}\s*$", "", src, flags=re.MULTILINE | re.IGNORECASE)

    # Render Markdown → HTML (no toc extension — we build our own right TOC from h2s)
    body = markdown.markdown(
        src,
        extensions=["fenced_code", "tables", "attr_list", "def_list", "nl2br"],
    )

    # Remove any rendered "Table of Contents" section (h2 heading + following list)
    body = re.sub(
        r"<h2[^>]*>\s*(?:<[^>]+>)*\s*Table of Contents\s*(?:</[^>]+>)*\s*</h2>\s*(<(?:ol|ul)[^>]*>.*?</(?:ol|ul)>)",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Add id attributes to h2/h3 headings so the right TOC anchors work
    def add_heading_ids(html: str) -> str:
        def replacer(m):
            tag, text = m.group(1), m.group(2)
            slug = slugify(re.sub(r"<[^>]+>", "", text))
            return f'<{tag} id="{slug}">{text}</{tag}>'

        return re.sub(r"<(h[23])>(.*?)</\1>", replacer, html, flags=re.IGNORECASE)

    body = add_heading_ids(body)

    # Rewrite .md links → .html
    body = rewrite_md_links(body)

    # Wrap tables in a scrollable container so they don't overflow into the right TOC
    body = re.sub(r"(<table)", r'<div class="table-scroll">\1', body)
    body = re.sub(r"(</table>)", r"\1</div>", body)

    # Extract title from first <h1>
    m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.IGNORECASE)
    title = re.sub(r"<[^>]+>", "", m.group(1)) if m else md_path.stem.replace("_", " ").title()

    # Right TOC — h2 headings for this page only
    toc_items = extract_toc(body)
    toc_aside_lines = [f'      <a href="#{slug}">{re.sub(r"<[^>]+>", "", text)}</a>' for slug, text in toc_items]

    # Current file path relative to root (used to highlight active nav item)
    current_rel = str(html_path.relative_to(ROOT)).replace("\\", "/")

    css = css_path(html_path)
    docs = docs_index_path(html_path)

    html_out = TEMPLATE.format(
        title=title,
        css_path=css,
        docs_index=docs,
        body=body,
        site_nav=build_site_nav(html_path, current_rel),
        toc_aside="\n".join(toc_aside_lines),
        version=VERSION,
    )

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html_out, encoding="utf-8")
    print(f"  ✓  {html_path.relative_to(ROOT)}")


def main():
    args = sys.argv[1:]

    if "--all" in args:
        print(f"Converting {len(FILES)} files...")
        for rel_path in FILES:
            md = ROOT / rel_path
            if not md.exists():
                print(f"  ✗  {rel_path} (not found, skipping)")
                continue
            html = md.with_suffix(".html")
            convert(md, html)
        print("Done.")
        return

    if not args:
        print("Usage: md2html.py <file.md> [output.html]  OR  md2html.py --all")
        sys.exit(1)

    md = Path(args[0])
    html = Path(args[1]) if len(args) > 1 else md.with_suffix(".html")
    if not md.exists():
        print(f"Error: {md} not found")
        sys.exit(1)
    convert(md, html)


if __name__ == "__main__":
    main()
