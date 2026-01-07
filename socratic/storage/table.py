import enum

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, MappedAsDataclass
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import String

from socratic.model import ExampleID

from .type import ShortUUIDKeyType, ValueEnumMapper

metadata = MetaData()


class base(MappedAsDataclass, DeclarativeBase):
    type_annotation_map = {
        ExampleID: ShortUUIDKeyType(ExampleID),
        list[str]: ARRAY(String),
        enum.Enum: ValueEnumMapper,
    }


class example(base):
    __tablename__ = "example"

    example_id: Mapped[ExampleID] = mapped_column(primary_key=True)
