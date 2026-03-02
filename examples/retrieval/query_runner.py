"""
Query Runner — invoked as a subprocess by the Reflex UI chat_state.py.

Usage:
    python query_runner.py --query "your question here"

Prints a single JSON line to stdout:
    {"content": "...", "sources": [...], "error": null}
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from retrieval_main import CompleteQuerySystem


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9200)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="MyStrongPass123!")
    parser.add_argument("--index", default="datasift_documents")
    parser.add_argument("--model", default="granite4")
    args = parser.parse_args()

    try:
        system = CompleteQuerySystem(
            opensearch_host=args.host,
            opensearch_port=args.port,
            opensearch_username=args.username,
            opensearch_password=args.password,
            opensearch_use_ssl=False,
            ollama_model=args.model,
            index_name=args.index,
        )

        result = system.query(
            user_question=args.query,
            use_sql=True,
            use_hybrid=True,
        )

        answer = result.get("answer") or "No answer returned."
        if result.get("errors") and not result.get("answer"):
            answer = "Retrieval error: " + "; ".join(result["errors"])

        sources = []
        for hit in result.get("hybrid_results", [])[:3]:
            # Index fields are: pk (hash), text (content), vector_embeddings
            # Use a short snippet of the text as the source reference
            text = hit.get("text") or hit.get("pk") or ""
            if text:
                # Truncate to first 80 chars as a readable source snippet
                snippet = str(text)[:80].strip()
                if snippet and snippet not in sources:
                    sources.append(snippet)

        print(json.dumps({"content": answer, "sources": sources, "error": None}), flush=True)

    except Exception as e:
        print(json.dumps({"content": f"Error: {str(e)}", "sources": [], "error": str(e)}), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()