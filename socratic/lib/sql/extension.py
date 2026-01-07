from __future__ import annotations

from alembic.operations import MigrateOperation, Operations


@Operations.register_operation("create_extension")
class CreateExtensionOp(MigrateOperation):
    def __init__(
        self, extension_name: str, checkfirst: bool = False, schema: str | None = None, version: str | None = None
    ):
        self.extension_name = extension_name
        self.checkfirst = checkfirst
        self.schema = schema
        self.version = version

    @classmethod
    def create_extension(
        cls,
        operations: Operations,
        extension_name: str,
        checkfirst: bool = False,
        schema: str | None = None,
        version: str | None = None,
    ):
        op = CreateExtensionOp(extension_name, checkfirst=checkfirst, schema=schema, version=version)
        return operations.invoke(op)

    def reverse(self):
        return DropExtensionOp(self.extension_name, cascade=False, checkfirst=self.checkfirst)


@Operations.implementation_for(CreateExtensionOp)
def create_extension(operations: Operations, op: CreateExtensionOp):
    checkfirst = "IF NOT EXISTS " if op.checkfirst else ""
    stmt = 'CREATE EXTENSION {}"{}"'.format(checkfirst, op.extension_name)

    if op.schema or op.version:
        w: list[str] = []
        if op.schema:
            w.append(f"SCHEMA {op.schema}")
        if op.version:
            w.append(f"VERSION '{op.version}'")
        stmt += " WITH " + " ".join(w)
    operations.execute(stmt)


@Operations.register_operation("drop_extension")
class DropExtensionOp(MigrateOperation):
    def __init__(self, extension_name: str, cascade: bool, checkfirst: bool = False):
        self.extension_name = extension_name
        self.checkfirst = checkfirst
        self.cascade = cascade

    @classmethod
    def drop_extension(
        cls, operations: Operations, extension_name: str, cascade: bool = False, checkfirst: bool = False
    ):
        op = DropExtensionOp(extension_name, cascade=cascade, checkfirst=checkfirst)
        return operations.invoke(op)

    def reverse(self):
        return CreateExtensionOp(self.extension_name, checkfirst=self.checkfirst)


@Operations.implementation_for(DropExtensionOp)
def drop_extension(operations: Operations, op: DropExtensionOp):
    checkfirst = "IF EXISTS " if op.checkfirst else ""
    stmt = f'DROP EXTENSION {checkfirst}"{op.extension_name}"'
    if op.cascade:
        operations.execute(stmt + " CASCADE")
    operations.execute(stmt)
