## Project
DIBox is an async-native Python dependency injection library (early development, API is not yet stable).
Core idea: Simplify dependency injection by automatically wiring classes based on their type hints. The goal is to eliminate boilerplate for common use cases while providing a clear, powerful API for advanced scenarios. The mission is simplicity and developer experience.

Key points:
- Design principle: Progressive Disclosure of Complexity — prefer zero-configuration defaults for common cases while providing clearer, explicit APIs for advanced scenarios.
- Keep `README.md` high-level and reasonably up to date with usage examples and notable breaking changes; design proposals in `docs/eps/` are working notes and internal notes, treat them as context for open questions, not as specifications.
- Public surface: `DIBox`, `inject` helpers, `Injected`/`NotInjected` markers and high-level helpers.
- API is unstable and may change; suggestions for improvements and new features are welcome.
- When proposing solutions or API designs, prioritize simplicity and DIBox idioms. The ambition is full production-use-case coverage with a simpler, more intuitive experience than other frameworks — not reduced scope. Borrow ideas selectively, and flag when a design trades simplicity for power without clear justification, even if the user seems committed to it.

## Code style
- Use modern Python features supported by Python 3.11
- Code is strictly typed and checked with pyright; annotate all functions and methods, but omit return type when it's `None` or obvious from context
- Don't suggest quick hacks or workarounds; suggest the best solution even if more complex. If there are multiple solutions, provide a short summary and let the user choose.
- Before applying any changes: if they touch more than one function or class, or if there are multiple reasonable approaches, present a short summary of the plan/options and wait for user approval.
- Docstrings use Google style; be concise and non-obvious. Skip docstrings for self-explanatory functions.
- Both in communication, code and documentation, prioritize clarity, avoid hyperbole and marketing language, engineering jokes are fine as long as they are relevant to the context and help digesting a complex topic.
## Tools
- tests: `uv run pytest`
- type checking: `uv run pyright`