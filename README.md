populate-secrets
================

## Overview

One command-line tool for pushing environment variables and secrets from a local
`.env` or JSON file into the places that need them: Gitlab CI/CD variables, AWS
SSM Parameter Store, Azure Pipelines variables, and Azure App Service settings.

It replaces three separate tools (`populate-secrets-gitlab`, `populate-ssm` and
`populate-secrets-azure`), so the input handling and filtering now work the same
way everywhere.

Each target is a subcommand:

- `populate-secrets gitlab` — write, list, get and download a Gitlab project's
  CI/CD variables, scoped to a Gitlab
  [environment](https://docs.gitlab.com/ee/ci/environments/).
- `populate-secrets aws-ssm` — write parameters to SSM Parameter Store under a
  path prefix, and diff a local file against what's already there.
- `populate-secrets azure-pipelines` — write Azure Pipelines variables.
- `populate-secrets azure-appservice` — write Azure App Service app settings.

## Install

Install as a global user tool, which gives it an isolated environment and puts
the command on your PATH:

```shell
# From git
uv tool install "git+https://github.com/deploymode/populate-secrets.git"

# From a local checkout
uv tool install .
```

Run `uv tool update-shell` once if `~/.local/bin` is not yet on your PATH.
`pipx install` works the same way if you prefer pipx.

To install into the current project's virtualenv instead:

```shell
uv pip install "git+https://github.com/deploymode/populate-secrets.git"
```

## Things that work the same everywhere

**Input files.** Every `write` command reads a `.env` file with `--env-file` and
a JSON file with `--json-file`. The JSON is an array of single key/value
objects:

```json
[{"APP_NAME": "my-app"}, {"DB_HOST": "localhost"}]
```

You can pass both, and JSON values win where a key appears in both files. You
have to pass at least one. A path that doesn't exist is an error, so a typo
fails immediately rather than quietly writing nothing.

**Filtering.** `--include` and `--exclude` both take a CSV list of variable
names, e.g. `--exclude APP_NAME,LOG_CHANNEL`. `--include` drops everything you
haven't named. A name in both lists is excluded.

**Sensitive names.** A variable whose name contains `KEY`, `SECRET`, `TOKEN` or
`PASSWORD` is treated as a credential, e.g. `APP_KEY`, `AUTH_TOKEN`,
`DB_PASSWORD`. Gitlab masks those variables when you pass `--mask`. Azure
Pipelines marks them `--secret true` automatically. SSM writes everything as a
`SecureString`, so the heuristic isn't used there.

## Gitlab

Set a personal access token first:

```shell
export GITLAB_TOKEN=...
```

Commands target the environment you name plus globally-scoped (`*`) variables.

### Write variables from a .env file

```shell
populate-secrets gitlab write \
  --env-file path/to/.env \
  --environment uat \
  --gitlab-host gitlab.example.com \
  --project my-group/my-project \
  --mask \
  --exclude APP_NAME,LOG_CHANNEL
```

Masking is one-way. An already-masked variable is never un-masked by this tool.

### List variables

```shell
# Keys and non-masked values
populate-secrets gitlab list --environment uat --gitlab-host gitlab.example.com --project my-group/my-project

# All values, including masked ones
populate-secrets gitlab list --environment uat --gitlab-host gitlab.example.com --project my-group/my-project --sensitive
```

### Get or export variables

```shell
populate-secrets gitlab get --environment uat --gitlab-host gitlab.example.com --project my-group/my-project --export
```

`--export` writes each scope to its own `<scope>.env` file.

### Download variables to an .env file

```shell
populate-secrets gitlab download --environment uat --gitlab-host gitlab.example.com --project my-group/my-project --output-dir .
```

It prompts before overwriting an existing file.

## AWS SSM Parameter Store

Authentication uses the standard boto3 chain, so set `AWS_PROFILE` or the usual
`AWS_ACCESS_KEY_ID` and friends in your environment. The region comes from the
same place. Missing credentials fail before anything is written.

```shell
populate-secrets aws-ssm write \
  --env-file path/to/.env \
  --json-file path/to/vars.json \
  --prefix /my-app/uat \
  --exclude APP_NAME
```

Every parameter is written as a `SecureString` at `<prefix>/<key>`, overwriting
any existing value. A trailing slash on `--prefix` is stripped, and variables
with an empty value are skipped because SSM rejects them.

To fill in only what's missing and leave everything already in Parameter Store
alone, add `--skip-existing`:

```shell
populate-secrets aws-ssm write --env-file path/to/.env --prefix /my-app/uat --skip-existing
```

That reads the prefix first, so it needs the same extra permissions as `diff`
below. A variable already in Parameter Store is skipped even if your local value
differs.

### Check what a write would change

```shell
populate-secrets aws-ssm diff --env-file path/to/.env --prefix /my-app/uat
```

It takes the same input and filter options as `write`, so what you see is what
that write would do. Output is grouped into vars to add (`+`), vars to change
(`~`), vars that only exist in Parameter Store (`-`) and unchanged ones (`=`).

Only keys are printed. Add `--sensitive` to see values, including both sides of
each change. This reads decrypted parameters, so it needs `ssm:GetParametersByPath`
and `kms:Decrypt` on top of what `write` needs.

## Azure

Both Azure subcommands shell out to the `az` CLI, so run `az login` first and
they'll use that session. `azure-pipelines` also needs the devops extension:

```shell
az extension add --name azure-devops
```

Azure keys have to be upper snake case (`^[A-Z][A-Z0-9_]*$`), and values can't
contain newlines or null bytes. Anything else is skipped with a message, since
those characters would break the `az` command line.

### Azure Pipelines variables

```shell
populate-secrets azure-pipelines write \
  --env-file path/to/.env \
  --pipeline-name my-pipeline \
  --exclude APP_NAME
```

Variables are created with `--allow-override true`, and an existing variable is
updated instead.

### Azure App Service settings

```shell
populate-secrets azure-appservice write \
  --env-file path/to/.env \
  --app-name my-app \
  --resource-group my-group
```

If you previously used `populate-secrets-azure`, note that it wrote to Pipelines
and App Service in one pass. Run both subcommands to get the same result.

## Development

```shell
uv sync
uv run --group dev pytest
uv run --group dev ruff check .
```
