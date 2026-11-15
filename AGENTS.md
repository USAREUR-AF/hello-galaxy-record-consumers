# AGENTS.md

Instructions for AI coding agents, and a short version for anyone working here. [CONTRIBUTING.md](CONTRIBUTING.md) is the full process.

## What this repository is

hello-galaxy-record-consumers shows what receives the records [first-bite](https://github.com/USAREUR-AF/first-bite) posts over HTTP: a receiver that makes its PostgreSQL tables from the dictionary's JSON Schema, and a latest-status board, deployed on Kubernetes with the rules for who may post and who may read. The source is simulated and the cluster is local.

It is one of the Hello Galaxy demonstrations: small, runnable examples, each showing one part of [goat](https://github.com/USAREUR-AF/goatcore). It holds no goat and no first-bite source code.

## Layout

| Path | What |
|---|---|
| `steps/` | one directory per step: `README.md` and `run.sh` |
| `bin/hello-consumers` | the runner: `build`, one step, `all`, `list`, `clean` |
| `lib/hello-consumers.sh` | shared shell functions |
| `app/` | the receiver and the board (Python), their tests and image |
| `deploy/` | Kustomize base and overlays, the decoder Job, the probe namespaces, the Bicep file |
| `samples/`, `dictionaries/` | the synthetic capture, schema and records; the dictionary |
| `tools/` | the record poster, the sample makers, the tool pins |

## Before you push

CI (`.github/workflows/ci.yml`) runs these; none needs a goatnet or a cloud account:

```bash
shellcheck -e SC1090,SC1091,SC2034 lib/hello-consumers.sh steps/*/run.sh bin/hello-consumers
bin/hello-consumers build
NO_COLOR=1 bin/hello-consumers all
```

The receiver and the board name no message and no field: what they know of a message set comes from the schema file. A change that adds a message or field name to `app/record_consumers/` is wrong. `samples/harbour-buoy.schema.json` and `deploy/base/harbour-buoy.schema.json` are the same file, the output of `bite schema dictionaries/harbour-buoy`; step 1 checks both. The "What you should see" block of a step's README is pasted from a run, never written by hand.

## Rules

1. **Nothing from a real deployment.** No hostname, domain, address, key or person of a real goatnet or cluster goes into a file or a commit message. Use made-up names, documentation addresses (RFC 5737) and `example.org` mail. No fielded message format goes into `dictionaries/` or `samples/`.
2. **No secret value in a file.** A manifest refers to a key of a Secret; the Secret is made in the cluster. CI refuses an overlay that renders a Secret.
3. **Who may read is the owner's to grant.** A change that opens the receiver, the board or the database to callers the owner has not named is wrong.
4. **Commits.** Conventional Commits subject of 100 characters or fewer, with a scope (`fix(<component>): …`). Every commit is signed off (`git commit -s`, the DCO) and signed with a key GitHub verifies. The organization's required check `verified-commits` refuses a pull request that holds an unverified commit.
5. **One logical change per pull request.**
6. **Vulnerabilities** go through [SECURITY.md](SECURITY.md), never a public issue.

The contribution guide for goat as a whole is [goatcore CONTRIBUTING.md](https://github.com/USAREUR-AF/goatcore/blob/main/CONTRIBUTING.md).
