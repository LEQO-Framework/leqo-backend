# Alembic

## Usage

If you what to create a new table or change an existing one you should do this with a migration script:

```bash
alembic revision -m "your message"
```

In the created migration file populate your changes in the `upgrade()` and `downgrade()` functions.
Now you can upgrade the database through running:

```bash
alembic upgrade head
```
