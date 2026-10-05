"""Register selected JSON schema files with Schema Registry."""

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def register_schemas(*, schema_files: list[str]) -> None:
    registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081").rstrip("/")
    topic = os.environ["KAFKA_TOPIC"]
    subject = quote(f"{topic}-value", safe="")
    schema_dir = Path(__file__).parent / "schemas"

    for schema_file in schema_files:
        schema_path = schema_dir / schema_file
        if not schema_path.is_file():
            raise FileNotFoundError(f"Schema file does not exist: {schema_path}")
        schema = schema_path.read_text(encoding="utf-8")
        request = Request(
            f"{registry_url}/subjects/{subject}/versions",
            data=json.dumps({"schema": schema, "schemaType": "JSON"}).encode("utf-8"),
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=5) as response:
                result = json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(
                f"Failed to register schema {schema_file} for {topic}-value "
                f"with Schema Registry at {registry_url}: {error}"
            ) from error

        print(
            f"Registered schema {schema_file} for {topic}-value (id={result['id']})",
            flush=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Register one or more JSON schemas from the schemas directory.")
    parser.add_argument(
        "--schema-files",
        nargs="+",
        required=True,
        metavar="FILE",
        help="One or more JSON schema filenames in the schemas directory, registered in the order given.",
    )
    args = parser.parse_args()
    register_schemas(schema_files=args.schema_files)


if __name__ == "__main__":
    main()
