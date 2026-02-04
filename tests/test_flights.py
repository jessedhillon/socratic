"""Tests for flights storage functions."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import PromptTemplate
from socratic.storage import flight as flight_storage


class TestResolveTemplateNameOnly(object):
    """Tests for resolve_template in name-only mode."""

    def test_returns_latest_active_version(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        with db_session.begin():
            template_factory(name="test_tpl", content="v1 content")
            t2 = template_factory(name="test_tpl", content="v2 content")

            result = flight_storage.resolve_template(name="test_tpl", session=db_session)

            assert result.template_id == t2.template_id
            assert result.version == 2

    def test_raises_key_error_for_missing_template(
        self,
        db_session: Session,
    ) -> None:
        with db_session.begin():
            with pytest.raises(KeyError, match="nonexistent"):
                flight_storage.resolve_template(name="nonexistent", session=db_session)


class TestResolveTemplateWithContent(object):
    """Tests for resolve_template in name + content mode."""

    def test_creates_first_version_for_new_name(
        self,
        db_session: Session,
    ) -> None:
        with db_session.begin():
            result = flight_storage.resolve_template(
                name="brand_new",
                content="Hello {{ name }}!",
                session=db_session,
            )

            assert result.version == 1
            assert result.name == "brand_new"
            assert result.content == "Hello {{ name }}!"

    def test_returns_existing_version_for_matching_content(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        with db_session.begin():
            t1 = template_factory(name="test_tpl", content="Hello {{ name }}!")

            result = flight_storage.resolve_template(
                name="test_tpl",
                content="Hello {{ name }}!",
                session=db_session,
            )

            assert result.template_id == t1.template_id
            assert result.version == 1

    def test_creates_new_version_for_different_content(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        with db_session.begin():
            t1 = template_factory(name="test_tpl", content="Hello {{ name }}!")

            result = flight_storage.resolve_template(
                name="test_tpl",
                content="Hi {{ name }}!",
                session=db_session,
            )

            assert result.template_id != t1.template_id
            assert result.version == 2

    def test_matches_normalized_jinja2_syntax(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        with db_session.begin():
            t1 = template_factory(name="test_tpl", content="Hello {{ name }}!")

            # Same template with different Jinja2 whitespace
            result = flight_storage.resolve_template(
                name="test_tpl",
                content="Hello {{name}}!",
                session=db_session,
            )

            assert result.template_id == t1.template_id

    def test_finds_earlier_version_by_content(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        with db_session.begin():
            t1 = template_factory(name="test_tpl", content="Hello {{ name }}!")
            template_factory(name="test_tpl", content="Hi {{ name }}!")

            # Resolve with v1 content — should find v1, not create v3
            result = flight_storage.resolve_template(
                name="test_tpl",
                content="Hello {{ name }}!",
                session=db_session,
            )

            assert result.template_id == t1.template_id
            assert result.version == 1
