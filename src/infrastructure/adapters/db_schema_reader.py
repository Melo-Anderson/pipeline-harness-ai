"""SQLAlchemy read-only adapter implementing MetadataPort."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class ColumnMeta:
    name: str
    data_type: str
    is_primary_key: bool
    description: str
    policy_tags: list[str] = field(default_factory=list)


@dataclass
class ObjectMeta:
    asset_name: str
    object_name: str
    object_type: str
    asset_id: str = ""
    object_id: str = ""
    columns: list[ColumnMeta] = field(default_factory=list)
    required_stewards: list[str] = field(default_factory=list)
    owner_email: str = ""


class DbSchemaReader:
    def __init__(self, db_url: str) -> None:
        self._engine: Engine = create_engine(db_url, pool_pre_ping=True)

    def get_object_metadata(self, asset_name: str, object_name: str) -> ObjectMeta | None:
        with self._engine.connect() as conn:
            stmt = text(
                "SELECT "
                "  a.name AS asset_name, "
                "  o.name AS object_name, "
                "  e.type AS object_type, "
                "  a.id   AS asset_id, "
                "  o.id   AS object_id "
                "FROM data_objects o "
                "JOIN data_assets a ON a.id = o.asset_id "
                "JOIN endpoints e ON e.id = a.endpoint_id "
                "WHERE a.name = :asset_name AND o.name = :object_name"
            )
            row = conn.execute(
                stmt,
                {"asset_name": asset_name, "object_name": object_name},
            ).fetchone()

            if row is None:
                return None

            m = row._mapping
            obj_id = str(m["object_id"])
            return ObjectMeta(
                asset_name=str(m["asset_name"]),
                object_name=str(m["object_name"]),
                object_type=str(m["object_type"]),
                asset_id=str(m["asset_id"]),
                object_id=obj_id,
                columns=self._cols(conn, obj_id),
            )

    def list_objects_for_asset(self, asset_name: str) -> list[ObjectMeta]:
        with self._engine.connect() as conn:
            stmt = text(
                "SELECT "
                "  a.name AS asset_name, "
                "  o.name AS object_name, "
                "  e.type AS object_type, "
                "  a.id   AS asset_id, "
                "  o.id   AS object_id "
                "FROM data_objects o "
                "JOIN data_assets a ON a.id = o.asset_id "
                "JOIN endpoints e ON e.id = a.endpoint_id "
                "WHERE a.name = :asset_name"
            )
            rows = conn.execute(stmt, {"asset_name": asset_name}).fetchall()

            result: list[ObjectMeta] = []
            for r in rows:
                m = r._mapping
                obj_id = str(m["object_id"])
                result.append(
                    ObjectMeta(
                        asset_name=str(m["asset_name"]),
                        object_name=str(m["object_name"]),
                        object_type=str(m["object_type"]),
                        asset_id=str(m["asset_id"]),
                        object_id=obj_id,
                        columns=self._cols(conn, obj_id),
                    )
                )
            return result


    def _cols(self, conn: Any, obj_id: str) -> list[ColumnMeta]:
        rows = conn.execute(
            text(
                "SELECT name, source_type AS data_type, is_primary_key, description, policy_tag "
                "FROM data_elements WHERE object_id = :o"
            ),
            {"o": obj_id},
        ).fetchall()

        def _map_col(r: Any) -> ColumnMeta:
            m = r._mapping
            raw_tag = m.get("policy_tag")
            
            if raw_tag is None:
                tags: list[str] = []
            elif isinstance(raw_tag, (list, tuple)):
                tags = [str(x) for x in raw_tag]
            elif isinstance(raw_tag, str):
                tags = [x.strip() for x in raw_tag.split(",") if x.strip()]
            else:
                tags = [str(raw_tag)]

            return ColumnMeta(
                name=str(m.get("name") or ""),
                data_type=str(m.get("data_type") or ""),
                is_primary_key=bool(m.get("is_primary_key")),
                description=str(m.get("description") or ""),
                policy_tags=tags,
            )

        return [_map_col(r) for r in rows]
