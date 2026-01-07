from __future__ import annotations

import enum
import typing as t

from alembic.operations import MigrateOperation, Operations
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.types import Enum as EnumType


class EnumValuesType(EnumType):
    """SQLAlchemy's built-in EnumType uses the enum member's name as the bind param, not the value, so we use this"""

    def __init__(self, enum_class: type[enum.Enum], **kwargs: t.Any):
        kwargs["values_callable"] = self._get_values
        super().__init__(enum_class, **kwargs)

    @staticmethod
    def _get_values(meta: type[enum.Enum]) -> list[enum.Enum]:
        return [e.value for e in meta]


@Operations.register_operation("create_enum_type")
class CreateEnumTypeOp(MigrateOperation):
    def __init__(self, type_name: str, values: list[str], schema: str | None = None):
        self.type_name = type_name
        self.values = values
        self.schema = schema

    @classmethod
    def create_enum_type(cls, operations: Operations, type_name: str, values: list[str], schema: str | None = None):
        op = CreateEnumTypeOp(type_name, values)
        return operations.invoke(op)

    def reverse(self):
        return DropEnumTypeOp(self.type_name, values=self.values, schema=self.schema)


@Operations.implementation_for(CreateEnumTypeOp)
def create_enum_type(operations: Operations, op: CreateEnumTypeOp):
    name = f'"{op.schema}".{op.type_name}' if op.schema else op.type_name
    qw = [f"'{v}'" for v in op.values]
    values = "({})".format(", ".join(qw))
    stmt = f"CREATE TYPE {name} AS ENUM {values}"
    operations.execute(stmt)
    return ENUM(*op.values, name=op.type_name, create_type=False)


@Operations.register_operation("drop_enum_type")
class DropEnumTypeOp(MigrateOperation):
    def __init__(
        self, type_name: str, values: list[str] | None = None, checkfirst: bool = False, schema: str | None = None
    ):
        self.type_name = type_name
        self.values = values
        self.checkfirst = checkfirst
        self.schema = schema

    @classmethod
    def drop_enum_type(
        cls, operations: Operations, type_name: str, values: list[str] | None = None, schema: str | None = None
    ):
        op = DropEnumTypeOp(type_name, values)
        return operations.invoke(op)

    def reverse(self):
        if self.values is not None:
            return CreateEnumTypeOp(self.type_name, self.values, schema=self.schema)
        raise NotImplementedError()


@Operations.implementation_for(DropEnumTypeOp)
def drop_enum_type(operations: Operations, op: DropEnumTypeOp):
    checkfirst = "IF EXISTS " if op.checkfirst else ""
    name = f'"{op.schema}".{op.type_name}' if op.schema else op.type_name
    stmt = f"DROP TYPE {checkfirst}{name}"
    operations.execute(stmt)


@Operations.register_operation("alter_enum_type")
class AlterEnumTypeOp(MigrateOperation):
    rename = None
    add_value = None
    rename_value = None

    def __init__(
        self,
        type_name: str,
        rename: str | None = None,
        add_value: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
        rename_value: tuple[str, str] | None = None,
        checkfirst: bool = False,
        schema: str | None = None,
    ):
        self.schema = schema
        self.type_name = type_name

        if rename:
            self.rename = rename
        elif add_value:
            self.checkfirst = checkfirst  # thus named to follow alembic conventions
            self.add_value = add_value
            self.before_value = before_value
            self.after_value = after_value
        elif rename_value:
            self.rename_value, self.new_value_name = rename_value

    @classmethod
    def alter_enum_type(
        cls,
        operations: Operations,
        type_name: str,
        rename: str | None = None,
        add_value: str | None = None,
        before_value: str | None = None,
        after_value: str | None = None,
        rename_value: tuple[str, str] | None = None,
        schema: str | None = None,
    ):
        op = AlterEnumTypeOp(type_name, rename, add_value, before_value, after_value, rename_value, schema=schema)
        operations.invoke(op)

    def reverse(self):
        if self.rename:
            return AlterEnumTypeOp(self.rename, rename=self.type_name, schema=self.schema)
        elif self.rename_value:
            return AlterEnumTypeOp(
                self.type_name, rename_value=(self.new_value_name, self.rename_value), schema=self.schema
            )
        # TODO: (2024-02-28) if this ever matters, write a proper reverse for
        #                    alter enum by saving renamed named, positions, etc
        #                    elif self.add_value: ...
        raise NotImplementedError("reversing add new enum member is not implemented")


@Operations.implementation_for(AlterEnumTypeOp)
def alter_enum_type(operations: Operations, op: AlterEnumTypeOp):
    """supports three ALTER TYPE operations:

    ALTER TYPE name RENAME TO new_name
    ALTER TYPE name ADD VALUE [ IF NOT EXISTS ] new_enum_value [ { BEFORE | AFTER } neighbor_enum_value ]
    ALTER TYPE name RENAME VALUE existing_enum_value TO new_enum_value
    """
    name = f'"{op.schema}".{op.type_name}' if op.schema else op.type_name
    if op.rename:
        stmt = f"ALTER TYPE {name} RENAME TO {op.rename}"
    elif op.add_value:
        stmt = f"ALTER TYPE {name} ADD VALUE "
        if op.checkfirst:
            stmt += "IF NOT EXISTS"
        stmt += f"'{op.add_value}'"
        if op.before_value:
            stmt += f" BEFORE '{op.before_value}'"
        elif op.after_value:
            stmt += f" AFTER '{op.after_value}'"
    elif op.rename_value:
        stmt = f"ALTER TYPE {name} RENAME VALUE '{op.rename_value}' TO '{op.new_value_name}'"
    else:
        raise NotImplementedError()
    operations.execute(stmt)


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
            w.append("SCHEMA {}".format(op.schema))
        if op.version:
            w.append("VERSION '{}'".format(op.version))
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
        op = DropExtensionOp(extension_name, cascade, checkfirst)
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
