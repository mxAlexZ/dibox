# Non-async support

Current non-async implementation can only resolve already instantiated objects since object creation is always async. It limits usability in sync contexts. One of the solutions is to add sync factory versions and throw exceptions when async-only features are used in sync mode.

```python
class DIBox:
    def get(...) -> T:
        ...

    async def provide(...) -> T:
        ...
8
    def provide_sync(...) -> T:
        ...
```
