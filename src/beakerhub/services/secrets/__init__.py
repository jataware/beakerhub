"""Shared constants for the secret channel between the hub and a spawned node.

`BeakerKubeSpawner` (hub side) writes these environment variables and
`BeakerhubSecretsManager` (node side) consumes them. Both import the names from here so
the two halves cannot drift apart — a mismatch would raise nothing, it would just
silently stop applying policies.

Names here must avoid the substrings the secrets manager treats as secret-looking
("secret", "private", "password", "passwd", "creds", "credentials", "token", "auth",
"passphrase") and must not end in "_key" or "_key_id". A matching name would be
auto-detected as a secret in its own right, and its value — an env var name, or a policy
name such as "allow" — would then be scrubbed out of notebook output wherever it
appeared.

Kept free of imports: the hub imports this module, and only the node has
beaker_notebook installed.
"""

#: Comma-separated list of the environment variables that came from the vault. The node
#: uses it to register vault secrets that upstream's name heuristics did not recognize.
VAULT_ENV_VAR_LIST_KEY = "BEAKERHUB_VAULT_ENV_VARS"
