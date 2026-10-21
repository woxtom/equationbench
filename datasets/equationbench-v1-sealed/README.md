# EquationBench v1 — sealed holdout

This directory contains an encrypted holdout. The key is **not** in the
repository. Do not publish decrypted tasks or answers.

- Tasks: **140**
- Plaintext hash commitment: `972c067191c49dec51b4d89f1faab27ee175ff771ba987b58b71e15e6928a0f0`
- Seed commitment: `f8ff0f693846c8de6688ddf91f28c8df0e53e2e55df446c469be9a054eada2c6`
- File: `sealed.enc`

Use `eqb dataset decrypt --path datasets/equationbench-v1-sealed --out /tmp/eqb-sealed` with
`EQB_SEALED_KEY` or a local key file to evaluate a model. After the season,
publish the key and the plaintext task file so the commitment can be verified.
