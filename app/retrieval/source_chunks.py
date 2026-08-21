"""Read-only, permission-first retrieval over approved public source chunks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agent.contracts import StudyKitCourseIdentity
from app.generation.model import ModelError, StructuredModel


class AccessScope(BaseModel):
    """Retrieval boundary.  The current runtime intentionally supports public only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["public"] = "public"
    owner: str | None = None
    session: str | None = None
    material_set: str | None = None

    def model_post_init(self, __context: object) -> None:
        if any((self.owner, self.session, self.material_set)):
            raise ValueError("private retrieval scopes are not available")


class SourceChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(min_length=1, max_length=300)
    course_id: str
    course_version: str
    unit_id: str
    source_id: str
    page: int | None = Field(default=None, ge=1)
    anchor_type: (
        Literal["page", "heading", "slide", "paragraph", "sheet", "image"] | None
    ) = None
    anchor_value: str | None = Field(default=None, min_length=1, max_length=1000)
    heading: str | None = Field(default=None, max_length=1000)
    text: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: Literal["public"] = "public"
    build_id: str
    build_status: Literal["succeeded"] = "succeeded"
    review_status: Literal["approved"] = "approved"
    index_allowed: Literal[True] = True

    def verify_hash(self) -> bool:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest() == self.sha256


@dataclass(frozen=True, slots=True)
class SourceChunkHit:
    chunk: SourceChunk
    score: float


class SourceChunkStore(Protocol):
    def search(
        self,
        query: str,
        access_scope: AccessScope,
        course_context: StudyKitCourseIdentity | None = None,
        page_filter: int | None = None,
        limit: int = 8,
    ) -> list[SourceChunkHit]: ...

    def resolve_exact(
        self,
        references: list["SourceChunkReference"],
        access_scope: AccessScope,
        course_context: StudyKitCourseIdentity,
        limit: int = 16,
    ) -> list[SourceChunk]: ...


class SourceChunkReference(BaseModel):
    """An author-supplied exact reference, never a search query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str | None = Field(default=None, min_length=1, max_length=300)
    source_id: str | None = Field(default=None, min_length=1, max_length=300)
    anchor_type: (
        Literal["page", "heading", "slide", "paragraph", "sheet", "image"] | None
    ) = None
    anchor_value: str | None = Field(default=None, min_length=1, max_length=1000)

    def model_post_init(self, __context: object) -> None:
        if self.chunk_id is None and not (
            self.source_id and self.anchor_type and self.anchor_value
        ):
            raise ValueError("an exact source reference needs chunk_id or source_id + anchor")


class SQLiteSourceChunkStore:
    """Open an offline-built FTS5 index in immutable read-only mode."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def search(
        self,
        query: str,
        access_scope: AccessScope,
        course_context: StudyKitCourseIdentity | None = None,
        page_filter: int | None = None,
        limit: int = 8,
    ) -> list[SourceChunkHit]:
        terms = _fts_query(query)
        if not terms or limit < 1:
            return []
        limit = min(limit, 50)
        if not self.path.is_file():
            return []
        clauses = [
            "c.scope = ?",
            "c.build_status = 'succeeded'",
            "c.review_status = 'approved'",
            "c.index_allowed = 1",
        ]
        parameters: list[object] = [access_scope.scope]
        if course_context is not None:
            clauses.extend(["c.course_id = ?", "c.course_version = ?"])
            parameters.extend([course_context.course_id, course_context.course_version])
            if course_context.unit_id is not None:
                clauses.append("c.unit_id = ?")
                parameters.append(course_context.unit_id)
        if page_filter is not None:
            clauses.append("c.page = ?")
            parameters.append(page_filter)
        # Scope and identity predicates are part of the same SQL query as FTS recall;
        # unauthorized rows never enter Python-side candidate ranking.
        sql = f"""
            SELECT c.*, bm25(source_chunks_fts) AS rank
            FROM source_chunks_fts
            JOIN source_chunks AS c ON c.rowid = source_chunks_fts.rowid
            WHERE {' AND '.join(clauses)}
              AND source_chunks_fts MATCH ?
            ORDER BY rank, c.chunk_id
            LIMIT ?
        """
        parameters.extend([terms, limit])
        uri = f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.Error:
            return []
        hits: list[SourceChunkHit] = []
        for row in rows:
            try:
                values = dict(row)
                rank = float(values.pop("rank"))
                chunk = SourceChunk.model_validate(values)
            except ValueError:
                continue
            if chunk.verify_hash():
                hits.append(SourceChunkHit(chunk=chunk, score=-rank))
        return hits

    def resolve_exact(
        self,
        references: list[SourceChunkReference],
        access_scope: AccessScope,
        course_context: StudyKitCourseIdentity,
        limit: int = 16,
    ) -> list[SourceChunk]:
        """Resolve cited chunks without FTS, after scope and identity filtering."""

        if not self.path.is_file() or limit < 1 or course_context.unit_id is None:
            return []
        bounded = references[: min(limit, 16)]
        if not bounded:
            return []
        uri = f"{self.path.resolve().as_uri()}?mode=ro&immutable=1"
        resolved: list[SourceChunk] = []
        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                for reference in bounded:
                    clauses = [
                        "scope = ?",
                        "course_id = ?",
                        "course_version = ?",
                        "unit_id = ?",
                        "build_status = 'succeeded'",
                        "review_status = 'approved'",
                        "index_allowed = 1",
                    ]
                    parameters: list[object] = [
                        access_scope.scope,
                        course_context.course_id,
                        course_context.course_version,
                        course_context.unit_id,
                    ]
                    if reference.chunk_id is not None:
                        clauses.append("chunk_id = ?")
                        parameters.append(reference.chunk_id)
                    if reference.source_id is not None:
                        clauses.append("source_id = ?")
                        parameters.append(reference.source_id)
                    if reference.anchor_type is not None:
                        clauses.append("anchor_type = ?")
                        parameters.append(reference.anchor_type)
                    if reference.anchor_value is not None:
                        clauses.append("anchor_value = ?")
                        parameters.append(reference.anchor_value)
                    rows = connection.execute(
                        f"SELECT * FROM source_chunks WHERE {' AND '.join(clauses)} "
                        "ORDER BY chunk_id LIMIT 2",
                        parameters,
                    ).fetchall()
                    # An ambiguous anchor is no more trustworthy than a missing one.
                    if len(rows) != 1:
                        continue
                    try:
                        chunk = SourceChunk.model_validate(dict(rows[0]))
                    except ValueError:
                        continue
                    if not chunk.verify_hash() or not _reference_matches(reference, chunk):
                        continue
                    resolved.append(chunk)
        except sqlite3.Error:
            return []
        return resolved


class SourceChunkRetriever:
    """Optional model rewrite/rerank around permission-filtered BM25 recall."""

    def __init__(
        self, store: SourceChunkStore, model: StructuredModel | None = None
    ) -> None:
        self.store = store
        self.model = model

    async def retrieve(
        self,
        query: str,
        access_scope: AccessScope,
        course_context: StudyKitCourseIdentity | None = None,
        page_filter: int | None = None,
        limit: int = 8,
    ) -> list[SourceChunkHit]:
        queries = [query]
        if self.model is not None:
            try:
                response = await self.model.generate_json(
                    system_prompt=(
                        "你是课程材料检索查询改写器。保留用户含义、专有名词和页码意图；"
                        "最多返回 3 个短查询，不回答问题。只输出 JSON。"
                    ),
                    user_prompt=json.dumps(
                        {
                            "query": query[:2000],
                            "output_contract": {"queries": ["short query"]},
                        },
                        ensure_ascii=False,
                    ),
                    thinking_enabled=False,
                    max_tokens=512,
                    timeout_seconds=20,
                )
                raw_queries = response.output.get("queries")
                if isinstance(raw_queries, list):
                    rewritten = [
                        item.strip()[:500]
                        for item in raw_queries[:3]
                        if isinstance(item, str) and item.strip()
                    ]
                    if rewritten:
                        queries = list(dict.fromkeys([query, *rewritten]))[:3]
            except (ModelError, ValueError):
                pass

        by_id: dict[str, SourceChunkHit] = {}
        for rewritten_query in queries:
            for hit in self.store.search(
                rewritten_query,
                access_scope,
                course_context,
                page_filter,
                min(max(limit * 2, limit), 50),
            ):
                existing = by_id.get(hit.chunk.chunk_id)
                if existing is None or hit.score > existing.score:
                    by_id[hit.chunk.chunk_id] = hit
        recalled = sorted(
            by_id.values(), key=lambda hit: (-hit.score, hit.chunk.chunk_id)
        )
        if self.model is None or len(recalled) < 2:
            return recalled[:limit]

        try:
            response = await self.model.generate_json(
                system_prompt=(
                    "你是课程材料候选重排器。只能排列 candidate IDs，不能添加 ID，"
                    "不得依据候选以外的课程事实。只输出 JSON。"
                ),
                user_prompt=json.dumps(
                    {
                        "query": query[:2000],
                        "candidates": [
                            {
                                "chunk_id": hit.chunk.chunk_id,
                                "text": hit.chunk.text[:1200],
                                "page": hit.chunk.page,
                            }
                            for hit in recalled[:20]
                        ],
                        "output_contract": {"ranked_chunk_ids": ["candidate ID"]},
                    },
                    ensure_ascii=False,
                ),
                thinking_enabled=False,
                max_tokens=512,
                timeout_seconds=20,
            )
            ranked_ids = response.output.get("ranked_chunk_ids")
            allowed = {hit.chunk.chunk_id: hit for hit in recalled}
            if (
                not isinstance(ranked_ids, list)
                or not ranked_ids
                or any(not isinstance(item, str) or item not in allowed for item in ranked_ids)
                or len(ranked_ids) != len(set(ranked_ids))
            ):
                raise ValueError("invalid source chunk reranking")
            ranked = [allowed[item] for item in ranked_ids]
            ranked.extend(hit for hit in recalled if hit.chunk.chunk_id not in set(ranked_ids))
            return ranked[:limit]
        except (ModelError, ValueError):
            return recalled[:limit]


def initialize_source_chunk_index(path: Path | str, chunks: list[SourceChunk]) -> None:
    """Offline helper: validate and build a fresh public FTS index."""

    target = Path(path)
    if target.exists():
        raise FileExistsError(target)
    if any(not chunk.verify_hash() or chunk.scope != "public" for chunk in chunks):
        raise ValueError("every source chunk must be public and hash-valid")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        connection.executescript(
            """
            CREATE TABLE source_chunks (
                chunk_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                course_version TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                page INTEGER,
                anchor_type TEXT CHECK (
                    anchor_type IN ('page', 'heading', 'slide', 'paragraph', 'sheet', 'image')
                ),
                anchor_value TEXT,
                heading TEXT,
                text TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                scope TEXT NOT NULL CHECK (scope = 'public'),
                build_id TEXT NOT NULL
                ,build_status TEXT NOT NULL CHECK (build_status = 'succeeded')
                ,review_status TEXT NOT NULL CHECK (review_status = 'approved')
                ,index_allowed INTEGER NOT NULL CHECK (index_allowed = 1)
            );
            CREATE UNIQUE INDEX source_chunks_exact_identity
            ON source_chunks (
                course_id, course_version, unit_id, chunk_id, source_id,
                IFNULL(anchor_type, ''), IFNULL(anchor_value, '')
            );
            CREATE VIRTUAL TABLE source_chunks_fts USING fts5(
                text, content='source_chunks', content_rowid='rowid', tokenize='unicode61'
            );
            """
        )
        for chunk in chunks:
            values = chunk.model_dump()
            if values["anchor_type"] is None and chunk.page is not None:
                values["anchor_type"] = "page"
                values["anchor_value"] = str(chunk.page)
            connection.execute(
                """INSERT INTO source_chunks
                (chunk_id, course_id, course_version, unit_id, source_id, page,
                 anchor_type, anchor_value, heading,
                 text, sha256, scope, build_id, build_status, review_status, index_allowed)
                VALUES (:chunk_id, :course_id, :course_version, :unit_id, :source_id,
                        :page, :anchor_type, :anchor_value, :heading,
                        :text, :sha256, :scope, :build_id, :build_status,
                        :review_status, :index_allowed)""",
                values,
            )
        connection.execute("INSERT INTO source_chunks_fts(source_chunks_fts) VALUES('rebuild')")


def _fts_query(query: str) -> str:
    # Quoted tokens prevent user input from becoming FTS operators or column filters.
    tokens = [token for token in query.replace("\x00", " ").split() if token][:24]
    return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _reference_matches(reference: SourceChunkReference, chunk: SourceChunk) -> bool:
    if reference.chunk_id is not None and reference.chunk_id != chunk.chunk_id:
        return False
    if reference.source_id is not None and reference.source_id != chunk.source_id:
        return False
    if reference.anchor_type is not None and reference.anchor_type != chunk.anchor_type:
        return False
    if reference.anchor_value is not None and reference.anchor_value != chunk.anchor_value:
        return False
    return True
