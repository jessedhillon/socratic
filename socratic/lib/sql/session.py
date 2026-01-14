import typing as t

import sql_formatter.core
import sqlalchemy.orm

import socratic.lib.util as util


class DebugSession(sqlalchemy.orm.Session):
    def format_query(self, q: sqlalchemy.orm.Query[t.Any]) -> str:
        conn = self.connection()
        compiler = q.statement.compile(conn, compile_kwargs={"literal_binds": True})
        cur = conn.connection.cursor()
        fs = cur.mogrify(compiler.string, compiler.params).decode("utf8")
        return sql_formatter.core.format_sql(fs)

    def print_query(self, q: sqlalchemy.orm.Query[t.Any], *args: t.Any, **kwargs: t.Any):
        print(self.format_query(q), *args, **kwargs)  # noqa: T201

    def copy_query(self, q: sqlalchemy.orm.Query[t.Any]):
        util.clipboard_notify("SQL query", self.format_query(q))


class DebugQuery(sqlalchemy.orm.Query[t.Any]):
    def __str__(self) -> str:
        if isinstance(self.session, DebugSession):
            fq = self.session.format_query(self)
            return fq.replace("< @", "<@").replace("@ >", "@>")
        return super().__str__()
