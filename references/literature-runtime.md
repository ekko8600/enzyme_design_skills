# Literature Runtime

## CLI

The bundled Python runtime exposes `enzyme-design`.

```bash
enzyme-design ingest <path> --parser auto
enzyme-design analyze <document-id> --dry-run
enzyme-design ask --question "<question>" --dry-run --rebuild-index
enzyme-design explore --topic "<topic>" --depth deep --allow-network
enzyme-design build-wiki
enzyme-design search-status
enzyme-design doctor
```

Use the CLI as a local fallback or artifact generator. Prefer parallel research
agents for deep exploration when the host runtime supports them.

## Privacy

- Local ingestion and wiki generation do not require remote upload.
- Remote LLM analysis is enabled unless
  `ENZYME_DESIGN_ALLOW_PRIVATE_UPLOAD=false`.
- Network exploration is enabled unless `ENZYME_DESIGN_ALLOW_NETWORK=false`.
- Use `--dry-run` for local smoke tests and evidence inspection.

Use `ENZYME_DESIGN_ROOT`, `ENZYME_DESIGN_DATA_DIR`,
`ENZYME_DESIGN_PARSED_DIR`, `ENZYME_DESIGN_INDEX`, and
`ENZYME_DESIGN_VAULT_DIR` for runtime paths. Legacy `LITERATURE_WIKI_*`
environment variables remain supported as fallbacks.

## Outputs

- parsed documents: `data/parsed/`
- local SQLite index: `data/index/`
- wiki and research logs: `vault/`
