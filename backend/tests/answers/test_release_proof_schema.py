# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Identity contracts reject partial, ambiguous and oversized attestations."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from koinon.answers.release_proof_dtos import ReleaseProofSource
from koinon.answers.release_proof_entities import AnswerReleaseProjectionJob


def test_projection_job_metadata_creates_on_sqlite_for_service_tests():
    engine = sa.create_engine("sqlite://")
    try:
        AnswerReleaseProjectionJob.__table__.create(engine)
        with engine.connect() as connection:
            assert connection.execute(sa.select(AnswerReleaseProjectionJob)).all() == []
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("error_sample", [{}, ["error"] * 26, ["x" * 4096]])
def test_projection_job_metadata_keeps_postgres_error_bounds(error_sample):
    uri = os.environ.get("KOINON_ACCOUNT_OPERATION_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires explicitly owned account-operation PostgreSQL fixture")
    url = sa.engine.make_url(uri)
    assert url.host == "127.0.0.1" and url.port == 55439
    engine = sa.create_engine(url.set(drivername="postgresql+psycopg"))
    table = AnswerReleaseProjectionJob.__table__.to_metadata(
        sa.MetaData(), name="projection_bounds_" + uuid4().hex[:12]
    )
    now = datetime.now(UTC)
    values = dict(
        job_id="job",
        projection_version=1,
        state="ready",
        revision=1,
        scanned=0,
        projected=0,
        already_present=0,
        invalid=0,
        blocked=0,
        error_sample=[],
        created_at=now,
        updated_at=now,
    )
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                table.create(connection)
                connection.execute(table.insert().values(values))
                with pytest.raises(sa.exc.IntegrityError) as error, connection.begin_nested():
                    connection.execute(table.update().values(error_sample=error_sample))
                assert error.value.orig.diag.constraint_name == "ck_release_job_errors"
                assert connection.scalar(sa.select(table.c.error_sample)) == []
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_supporting_results_are_sorted_and_unique():
    with pytest.raises(ValidationError, match="sorted unique"):
        ReleaseProofSource(
            source_reference_id="s", kind="dataset", asset_id="a", supporting_result_ids=("z", "a", "a")
        )


def test_document_identity_cannot_be_partially_supplied():
    with pytest.raises(ValidationError, match="document identity"):
        ReleaseProofSource(
            source_reference_id="s",
            kind="document",
            asset_id="a",
            source_part_id="part",
            supporting_result_ids=("pin",),
        )


def test_document_revision_must_bind_the_exact_part_hash():
    with pytest.raises(ValidationError, match="document identity"):
        ReleaseProofSource(
            source_reference_id="s",
            kind="document",
            asset_id="a",
            source_version_id="v",
            extraction_id="e",
            source_part_id="part",
            source_part_sha256="a" * 64,
            used_revision="source-part-sha256:" + "b" * 64,
            page_basis="recorded_loader",
            supporting_result_ids=("pin",),
        )
