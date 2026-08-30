# Access control

The intended production flow is:

`User identity → source ACL → document ACL → retrieval filter → context → generation`

Never rely on a prompt instruction such as “do not reveal confidential data” as the primary authorization control.

The POC's `allowed_sensitivity` setting is a coarse policy mechanism and should not be mistaken for user-level document authorization.
