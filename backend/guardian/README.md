# Guardian audit policy

`climaudit_audit.policy` is the Guardian policy package ClimAudit uses to anchor audit event hashes (one request
form, one save block, one documents grid; schema fields `eventHash`, `eventType`, `batchId`, `seq`). It is generated
from Guardian's Hello World tutorial policy (Apache-2.0) by `build_audit_policy.py` and committed.

Load it into a running Guardian as the Standard Registry (the user whose credentials are in `backend/.env`):

1. Import: `POST /api/v1/policies/import/file`, body = the raw `.policy` file, `Content-Type: binary/octet-stream`
   (the Guardian UI import button works too).
2. Publish: `PUT /api/v1/policies/{id}/publish` with `{"policyVersion": "1.0.0"}` (or the Publish button in the UI).
3. Put the policy id in `backend/.env` as `CP_GUARDIAN_POLICY_ID`.

Use one fresh policy instance per environment. The audit verifier compares the hashes in the policy with the local
chain, so credentials submitted by anything else make it report a mismatch.
