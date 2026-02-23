# Advanced Factory parameters

Currently, factory functions can only accept created type parameter. If we extend them to be able to accept other arguments that were passed to the function (in analogy with the idea of dynamic container selection in @inject decorator), we can open up new possibilities that allow more dynamic and context-aware factory functions probably making scopes less necessary.

```python
async def user_factory(user_id: int, box: DIBox) -> User:
    # Factory can access the container to resolve other dependencies
    db = await box.provide(Database)
    return await db.get_user(user_id)

box.bind(User, to=user_factory)
box.provide(User, user_id=123)  # Pass additional arguments to the factory

@inject
async def handle_user_request(user: Injected[User], user_id: int):
    # The factory can use request data to create the user instance
    print(f"Handling request for user: {user.name}")
```


# Yielding objects from factories
If a factory function is a generator (using `yield`), the container can manage its lifecycle using an async context manager.