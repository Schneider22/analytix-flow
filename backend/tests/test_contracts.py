from __future__ import annotations

import json
from pathlib import Path

import pytest


CONTRACT_ROOT = Path(__file__).parents[2] / "contracts"


def _walk_refs(value):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith(("#", "http://", "https://")):
            yield ref
        for child in value.values():
            yield from _walk_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_refs(child)


def _module_ids(value):
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            module_id = properties.get("module_id")
            if isinstance(module_id, dict) and "const" in module_id:
                yield module_id["const"]
        for child in value.values():
            yield from _module_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _module_ids(child)


def test_contract_json_files_and_local_references_are_valid():
    files = sorted(CONTRACT_ROOT.rglob("*.json"))
    assert len(files) == 22
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        for ref in _walk_refs(schema):
            assert (path.parent / ref).resolve().is_file(), f"Missing reference {ref} from {path}"

    for number in range(1, 9):
        input_path = CONTRACT_ROOT / f"m{number}" / "input.schema.json"
        output_path = CONTRACT_ROOT / f"m{number}" / "output.schema.json"
        input_schema = json.loads(input_path.read_text(encoding="utf-8"))
        output_schema = json.loads(output_path.read_text(encoding="utf-8"))
        assert list(_module_ids(input_schema)) == [f"m{number}"]
        assert list(_module_ids(output_schema)) == [f"m{number}"]
        assert "execution-envelope.schema.json" in json.dumps(input_schema)
        assert "execution-result.schema.json" in json.dumps(output_schema)


def test_contract_schemas_pass_draft_2020_12_meta_validation():
    try:
        import jsonschema as validator_module
        import referencing as referencing_module
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Contract validation requires jsonschema and referencing; "
            "install backend/requirements.txt before running the suite. "
            f"Missing module: {exc.name}",
            pytrace=False,
        )
    validator = validator_module.Draft202012Validator
    schemas = {}
    for path in CONTRACT_ROOT.rglob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        validator.check_schema(schema)
        schemas[schema["$id"]] = schema

    registry = referencing_module.Registry().with_resources(
        (uri, referencing_module.Resource.from_contents(schema))
        for uri, schema in schemas.items()
    )
    for uri, schema in schemas.items():
        resolver = registry.resolver(base_uri=uri)
        for ref in _walk_refs(schema):
            resolver.lookup(ref)
