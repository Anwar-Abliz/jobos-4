"""Tests for GenerativeModel tier mapping.

Covers:
- Each tier maps to correct GenerativeModel fields
- T3 injects T3_STANDARD_STEPS
- T4 Micro-Job sets primary_goal (functional), not prior_aspiration
- Serialisation to dict
"""
from __future__ import annotations

import pytest

from jobos.kernel.hierarchy import HierarchyJob, JobTier, T3_STANDARD_STEPS
from jobos.kernel.generative_model import (
    GenerativeModel,
    generative_model_to_dict,
    map_tier_to_generative_model,
)


def make_job(tier: JobTier, statement: str, job_id: str = "j001") -> HierarchyJob:
    return HierarchyJob(id=job_id, tier=tier, statement=statement)


class TestMapTierToGenerativeModel:
    def test_t1_sets_prior_aspiration(self):
        job = make_job(JobTier.STRATEGIC, "Define the long-term vision")
        model = map_tier_to_generative_model(job)
        assert model.tier == 1
        assert model.prior_aspiration == "Define the long-term vision"
        assert model.primary_goal == ""
        assert model.execution_steps == []

    def test_t2_sets_primary_goal(self):
        job = make_job(JobTier.CORE_FUNCTIONAL, "Reduce customer churn rate")
        model = map_tier_to_generative_model(job)
        assert model.tier == 2
        assert model.primary_goal == "Reduce customer churn rate"
        assert model.prior_aspiration == ""
        assert model.execution_steps == []

    def test_t3_sets_execution_steps_to_standard(self):
        job = make_job(JobTier.EXECUTION, "Prepare onboarding materials")
        model = map_tier_to_generative_model(job)
        assert model.tier == 3
        assert model.execution_steps == T3_STANDARD_STEPS
        assert len(model.execution_steps) == 8
        assert "Define" in model.execution_steps
        assert "Conclude" in model.execution_steps

    def test_t3_also_sets_primary_goal(self):
        job = make_job(JobTier.EXECUTION, "Execute deployment pipeline")
        model = map_tier_to_generative_model(job)
        assert model.primary_goal == "Execute deployment pipeline"

    def test_t4_sets_primary_goal(self):
        """T4 Micro-Job sets primary_goal (functional), not prior_aspiration."""
        job = make_job(JobTier.MICRO_JOB, "Verify deployment health check passes")
        model = map_tier_to_generative_model(job)
        assert model.tier == 4
        assert model.primary_goal == "Verify deployment health check passes"
        assert model.prior_aspiration == ""
        assert model.micro_actions == []

    def test_t4_micro_actions_starts_empty(self):
        job = make_job(JobTier.MICRO_JOB, "Archive stale pipeline entries")
        model = map_tier_to_generative_model(job)
        assert model.micro_actions == []

    def test_job_id_and_statement_preserved(self):
        job = make_job(JobTier.STRATEGIC, "Achieve market leadership", job_id="j_xyz")
        model = map_tier_to_generative_model(job)
        assert model.job_id == "j_xyz"
        assert model.job_statement == "Achieve market leadership"


class TestGenerativeModelToDict:
    def test_returns_dict_with_all_keys(self):
        job = make_job(JobTier.STRATEGIC, "Define the strategy")
        model = map_tier_to_generative_model(job)
        d = generative_model_to_dict(model)
        assert "tier" in d
        assert "job_id" in d
        assert "job_statement" in d
        assert "prior_aspiration" in d
        assert "primary_goal" in d
        assert "execution_steps" in d
        assert "micro_actions" in d

    def test_t3_dict_has_8_execution_steps(self):
        job = make_job(JobTier.EXECUTION, "Execute the workflow")
        model = map_tier_to_generative_model(job)
        d = generative_model_to_dict(model)
        assert len(d["execution_steps"]) == 8

    def test_tier_is_int(self):
        for tier, expected in [
            (JobTier.STRATEGIC, 1),
            (JobTier.CORE_FUNCTIONAL, 2),
            (JobTier.EXECUTION, 3),
            (JobTier.MICRO_JOB, 4),
        ]:
            job = make_job(tier, "Define something")
            model = map_tier_to_generative_model(job)
            assert model.tier == expected
