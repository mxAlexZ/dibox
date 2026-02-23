# Binding grouping and reuse

As projects grow, managing dependency bindings becomes more complex. A large application might have dozens or even hundreds of bindings. Without a way to organize them, the setup code can become a monolithic, unmanageable block. This makes it difficult to understand, test, and reuse parts of the application's dependency graph.

For example, different parts of an application (e.g., `billing`, `notifications`, `analytics`) have their own sets of services and dependencies. Furthermore, we might need to swap implementations between environments (e.g., using a real `S3Storage` in production but a `LocalStorage` in tests).

## manual grouping (current approach, does not involve any new API)
Let's say our application has distinct "billing" and "notification" features. We can define their bindings in separate, co-located files.

```python
# billing/dependencies.py
def add_billing_bindings(box: DIBox):
	"""Registers all dependencies for the billing module."""
	box.bind(PaymentGateway, StripeGateway)
	box.bind(InvoiceStorage, S3InvoiceStorage)
# notifications/dependencies.py
def add_notification_bindings(box: DIBox):
	"""Registers all dependencies for the notification module."""
	box.bind(EmailSender, SendGridSender)

# main.py
async with DIBox() as box:
	add_billing_bindings(box)
	add_notification_bindings(box)
```

Cons:
- The rules are actually just created inside the box.

## Idea 1: Class-Based Modules (Guice/Injector style)

Introduce an explicit `Module` class that groups bindings. This is a common pattern in frameworks like Guice (Java) and Injector (Python).

```python
# A formal structure for binding groups
class BillingModule(dibox.Module):
	def configure(self, box: DIBox):
		box.bind(PaymentGateway, StripeGateway)
		box.bind(InvoiceStorage, S3InvoiceStorage)

# Installation is explicit
box.install(BillingModule())
box.install(NotificationsModule())
```

**Potential Benefits of an Explicit Module System:**
- Configuration & Reusability: A module can be instantiated with parameters (`BillingModule(api_key=...)`), allowing a configured set of bindings to be reused.
- Introspection & Debugging: It enables better ntime analysis. You could inspect the container to see which modules are installed (`box.installed_modules`) or trace a binding back to its source module, which is invaluable for debugging large dependency graphs.
- Namespacing: Modules could automatically prefix their bindings which helps with logical separation and troubleshooting in large applications. For example, it can be included in error messages, like `No binding found for 'billing.PaymentGateway'`.
- Conditional Loading: Provides a clear and declarative way to install or swap entire feature sets based on configuration (`if feature_enabled: box.install(FeatureModule())`).

## Idea 2: Convention-over-Configuration (Rails Initializers style)

Automatically discover and load bindings from predefined locations. For example, DIBox could be configured to scan for and execute all functions named `add_bindings` in files named `dependencies.py`.

```python
# billing/dependencies.py
@dibox.bindings
def add_billing_bindings(box: dibox.DIBox):
	"""This function will be discovered by box.scan()"""
	box.bind(PaymentGateway, StripeGateway)
	box.bind(InvoiceStorage, S3InvoiceStorage)

# main.py
async with DIBox() as box:
	# Scan the imported module for functions marked with @dibox.bindings
	box.scan(billing.dependencies)
```

It still involves a degree of "magic" in the scan method and introduces a new decorator to the public API, which must be weighed against the goal of keeping the core API minimal.
