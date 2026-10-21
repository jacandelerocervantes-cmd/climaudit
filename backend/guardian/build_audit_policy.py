"""Build the ClimAudit audit policy package from Guardian's own Hello World tutorial policy (Apache-2.0).

    python guardian/build_audit_policy.py "<path to Hello World.policy>" guardian/climaudit_audit.policy

The result is a Guardian policy with one request form (block tag `form`), the block that saves the document
(`save`) and a documents grid (`grid`), using a schema with the four fields ClimAudit anchors:
eventHash, eventType, batchId and seq. The package is generated once and committed; run this script only to
regenerate it. The export proof of the source package is dropped because the content changes.
"""
from __future__ import annotations

import json
import sys
import uuid
import zipfile

NAME = "ClimAudit Audit Anchor"
DESCRIPTION = "Anchors ClimAudit audit event hashes as verifiable credentials on Hedera through Guardian. SYNTHETIC_DEMO_DATA"

PROPERTIES = {
    "eventHash": ("Event hash", "Hex SHA-256 of the audit event", "string", 0),
    "eventType": ("Event type", "Type of the audit event", "string", 1),
    "batchId": ("Batch id", "ClimAudit batch identifier", "string", 2),
    "seq": ("Sequence", "Position of the event in the batch audit chain", "number", 3),
}


def build(source: str, target: str) -> None:
    src = zipfile.ZipFile(source)
    names = src.namelist()
    schema_name = next(n for n in names if n.startswith("schemas/#") and n.endswith(".json"))
    old_uuid = json.loads(src.read(schema_name))["uuid"]
    new_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "climaudit-audit-anchor-schema"))
    policy_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, "climaudit-audit-anchor-policy"))
    out = zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED)
    for name in names:
        if name == "proof.json" or name.endswith("/"):
            continue
        data = src.read(name)
        if name == schema_name:
            schema = json.loads(data)
            doc = schema["document"]
            doc = json.loads(doc) if isinstance(doc, str) else doc
            base = {k: v for k, v in doc["properties"].items() if k in ("@context", "type", "id", "policyId", "ref", "guardianVersion")}
            props = dict(base)
            for field, (title, description, kind, order) in PROPERTIES.items():
                props[field] = {
                    "title": title,
                    "description": description,
                    "readOnly": False,
                    "type": kind,
                    "$comment": json.dumps({"term": field, "@id": "https://www.schema.org/text", "orderPosition": order}),
                }
            doc["properties"] = props
            doc["required"] = ["@context", "type", "policyId", *PROPERTIES]
            doc["title"] = NAME
            schema["name"] = NAME
            schema["document"] = json.dumps(doc) if isinstance(schema["document"], str) else doc
            data = json.dumps(schema).encode()
            name = name.replace(old_uuid, new_uuid)
        text = data.decode("utf-8") if name.endswith(".json") else None
        if text is not None:
            text = text.replace(old_uuid, new_uuid)
            if name == "policy.json":
                policy = json.loads(text)
                policy.update({"uuid": policy_uuid, "name": NAME, "description": DESCRIPTION, "topicDescription": NAME})
                text = json.dumps(policy)
            data = text.encode("utf-8")
        out.writestr(name, data)
    out.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    build(sys.argv[1], sys.argv[2])
    print("written", sys.argv[2])
