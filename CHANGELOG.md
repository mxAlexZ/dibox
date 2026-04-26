## v0.1.10 (2026-04-26)
### <!-- 0 -->🚀 Features & Enhancements
- Show resolution stack in errors and logs

### <!-- 3 -->📚 Documentation
- ADR concept documentation, ADR update agent skill
- Structured ADR index and proposal of semi-strict resolution mode

### <!-- 7 -->🛠️ Under the hood
- Clean up ci pipeline and improve triggers

## v0.1.9 (2026-04-16)
### <!-- 0 -->🚀 Features & Enhancements
- Support strict mode with disabled implicit self-binding

### <!-- 3 -->📚 Documentation
- Internal ADR updates - implicit binding, injection points
- Readme updates, better quickstart and entrypoint explanation

### <!-- 7 -->🛠️ Under the hood
- Don't create empty pipelines during release
- Condense-markdown, update-adr-index agent skills
- Cleanup pyproject.toml

## v0.1.8 (2026-03-19)
### <!-- 0 -->🚀 Features & Enhancements
- ContextVar-based `@inject` decorator

### <!-- 3 -->📚 Documentation
- Add badges to the readme

### <!-- 5 -->✨ Miscellaneous
- Remove @inject() support
- Remove opt-out strategy support

### <!-- 7 -->🛠️ Under the hood
- Update pypi projecti metadata
- Changelog and whitespaces

## v0.1.7 (2026-03-15)
### <!-- 0 -->🚀 Features & Enhancements
- Support context managers and yield (generator) factories
- Modules (BindingBox) support

### <!-- 2 -->🚜 Refactor
- Add InstanceBox tests, improve test structure, rename FactoryBox to BindingBox

### <!-- 3 -->📚 Documentation
- Eps updates: injection, scopes, binding boxes

### <!-- 7 -->🛠️ Under the hood
- Tweak uv settings for GitLab CI
- Automate changelog maintenance and versioning
- Improve job/stage grouping
- Use a deploy key for release commits

## v0.1.6 (2026-03-05)
### <!-- 0 -->🚀 Features & Enhancements
- Type hint updates

### <!-- 7 -->🛠️ Under the hood
- Add Zuban check to CI pipelines

## v0.1.5 (2026-03-04)
### <!-- 0 -->🚀 Features & Enhancements
- Injector and related decorator API updates

### <!-- 7 -->🛠️ Under the hood
- Copilot instructions

## v0.1.4 (2026-02-26)
### <!-- 0 -->🚀 Features & Enhancements
- Cleaner api: rename resolve to get + doc update
- Enable strict type checks

## v0.1.3 (2026-02-24)
### <!-- 0 -->🚀 Features & Enhancements
- New bind api

### <!-- 3 -->📚 Documentation
- Docs with ideas of the dibox enhancements
- Readme update, add comparison with Dishka
- Better intro example in the readme

### <!-- 7 -->🛠️ Under the hood
- Publish step for public pypi + toc for README.md
- Add manual trigger for publish stage

## v0.1.2a1 (2025-11-24)
### <!-- 1 -->🐛 Bug Fixes
- Fix pyright errors
- Fix import error during pyright run in CI

### <!-- 3 -->📚 Documentation
- Docstrings
- Readme and project metadata for pipy

## v0.1.1.dev2 (2025-11-16)
### <!-- 7 -->🛠️ Under the hood
- Run unit tests in Gitlab pipelines
- Run ruff and pyright quality checks in CI pipelines
- Provide code coverage report in CI
- Publish package to testpypi

## v0.1.0 (2025-11-11)
### <!-- 0 -->🚀 Features & Enhancements
- Initial commit
- First implementation draft
