"""Phase 2.3.3 weighted objective preparation; no Minimize or Solve is called here."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.scheduler.fairness_model import FairnessObjectiveModel
from app.scheduler.ot_model import OtObjectiveModel
from app.scheduler.preference_model import PreferenceObjectiveModel


FAIRNESS_WEIGHT = 20
PREFERENCE_WEIGHT = 10
OT_WEIGHT = 10
MAX_OBJECTIVE_COST = 1_000_000_000_000


@dataclass(frozen=True)
class ObjectiveComponent:
    """Explainable input to the future minimisation objective."""

    key: str
    weight: int
    score_variable: cp_model.IntVar | None
    score_term_count: int


@dataclass(frozen=True)
class ObjectiveCompositionModel:
    fairness_cost: cp_model.IntVar
    preference_cost: cp_model.IntVar
    ot_cost: cp_model.IntVar | None
    components: tuple[ObjectiveComponent, ...]
    total_objective_cost: cp_model.IntVar
    total_objective_terms: int
    constraint_count: int


def build_objective_composition(
    model: cp_model.CpModel,
    fairness: FairnessObjectiveModel,
    preferences: PreferenceObjectiveModel,
    overtime: OtObjectiveModel,
) -> ObjectiveCompositionModel:
    """Aggregate prepared soft costs without attaching an optimisation objective.

    All three source values are penalties, so their weighted values are added.  The
    later solver phase may call ``model.Minimize(total_objective_cost)``; this phase
    deliberately only builds the explainable expression.
    """
    components = [
        ObjectiveComponent("fairness", FAIRNESS_WEIGHT, fairness.total_workload_imbalance, len(fairness.pairwise_imbalances)),
        ObjectiveComponent("preference", PREFERENCE_WEIGHT, preferences.preference_penalty_score, preferences.score_term_count),
    ]
    if overtime.ot_penalty_score is not None:
        components.append(ObjectiveComponent("ot", OT_WEIGHT, overtime.ot_penalty_score, overtime.penalty_term_count))

    weighted_terms = [component.weight * component.score_variable for component in components if component.score_variable is not None]
    # This intentionally generous bound avoids model-proto introspection and remains
    # well within CP-SAT's integer range for the configured ICU month horizon.
    total_cost = model.NewIntVar(0, MAX_OBJECTIVE_COST, "total_objective_cost")
    model.Add(total_cost == sum(weighted_terms))
    return ObjectiveCompositionModel(
        fairness_cost=fairness.total_workload_imbalance,
        preference_cost=preferences.preference_penalty_score,
        ot_cost=overtime.ot_penalty_score,
        components=tuple(components),
        total_objective_cost=total_cost,
        total_objective_terms=len(weighted_terms),
        constraint_count=1,
    )
