"""
Load environment variables from the .env file.
"""

from typing import Literal

from pydantic import AnyHttpUrl, Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the backend, loaded from a `.env` file.

    :param AnyHttpUrl api_base_url: Base URL of the backend API, used for generating absolute URLs.
    :param list[str] cors_allow_origins: List of allowed origins for CORS. Wildcard `*` allows all origins.
    :param bool cors_allow_credentials: Whether CORS requests can include credentials (e.g., cookies or headers).
    :param list[str] cors_allow_methods: List of HTTP methods allowed for CORS. Wildcard `*` allows all methods.
    :param list[str] cors_allow_headers: List of HTTP headers allowed in CORS requests. Wildcard `*` allows all headers.
    """

    api_base_url: AnyHttpUrl = AnyHttpUrl(url="http://localhost:8000/")

    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    qiskit_compat_mode: bool = False
    """Enable Qiskit compatibility adjustments (e.g. stripping literal nodes)."""

    nisq_analyzer_url: AnyHttpUrl = AnyHttpUrl(
        url="http://localhost:5010/nisq-analyzer/"
    )
    """Base URL of the NISQ Analyzer used for QPU selection and MCDA ranking."""

    nisq_analyzer_mcda_method: Literal["topsis", "promethee-II", "electre-III"] = (
        "topsis"
    )
    """MCDA method used by the NISQ Analyzer to rank compiled circuits."""

    nisq_analyzer_allowed_providers: list[str] = ["ibmq"]
    nisq_analyzer_compilers: list[str] = ["qiskit"]
    nisq_analyzer_tokens: dict[str, dict[str, str]] = {"ibmq": {"ibmq": ""}}
    """Provider tokens forwarded by the NISQ Analyzer to the compiler services."""

    nisq_analyzer_poll_interval_seconds: float = Field(default=3.0, gt=0)
    nisq_analyzer_timeout_seconds: float = Field(default=600.0, gt=0)
    """Maximum time to wait for one QPU selection or ranking job."""

    algorithm_selection_qaoa_layers: list[PositiveInt] = Field(
        default=[1, 2], min_length=1
    )
    """QAOA depths (p); each is a candidate of the algorithm selection."""

    algorithm_selection_vqe_layers: list[PositiveInt] = Field(
        default=[1, 2], min_length=1
    )
    """Hardware-efficient VQE depths (L); each is a candidate of the algorithm selection."""

    algorithm_selection_max_error_chance: float = Field(default=0.5, ge=0, le=1)
    """A candidate whose top-ranked QPU exceeds this error chance is not feasible."""

    algorithm_selection_history_variable_tolerance: float = Field(
        default=0.2, ge=0, le=1
    )
    """Relative difference in the number of variables for a QUBO to count as similar."""

    algorithm_selection_history_density_tolerance: float = Field(
        default=1.0, ge=0, le=1
    )
    """Absolute difference in coupling density for a QUBO to be considered as similar; by
    default no limit, the density enters the distance instead."""

    algorithm_selection_history_size_scale: float = Field(default=0.2, ge=0)
    algorithm_selection_history_density_scale: float = Field(default=0.1, ge=0)
    algorithm_selection_history_field_scale: float = Field(default=0.5, ge=0)
    """Scales of the relative size difference, the density difference and the difference of
    ``log(1 + field/coupling ratio)`` in the distance of similar QUBOs; 0 ignores a feature."""

    algorithm_selection_history_limit: PositiveInt = 50
    """Number of nearest records the history uses."""

    algorithm_selection_history_margin: float = Field(default=0.005, ge=0)
    """The history only votes if its best candidate leads the second best by this mean
    quality."""

    algorithm_selection_vqe_max_variables: PositiveInt = 14
    """Up to this number of variables the problem structure rule prefers VQE."""

    algorithm_selection_qaoa_min_variables: PositiveInt = 16
    """From this number of variables on the problem structure rule prefers QAOA for QUBOs with
    weak local fields and a low density; it does not vote for sizes in between."""

    algorithm_selection_qaoa_always_variables: PositiveInt = 18
    """From this number of variables on the problem structure rule prefers QAOA for every QUBO."""

    algorithm_selection_max_field_coupling_ratio: float = Field(default=0.78, ge=0)
    """Largest mean |local field| / mean |coupling| (Ising form) of a weak-field QUBO."""

    algorithm_selection_max_density: float = Field(default=0.625, ge=0, le=1)
    """Largest coupling density for which the structure rule prefers QAOA below
    ``algorithm_selection_qaoa_always_variables``."""

    algorithm_selection_qaoa_max_error_chance: float = Field(default=0.4, ge=0, le=1)
    """The structure rule only votes for QAOA if a feasible QAOA candidate has at most this
    error chance."""

    algorithm_selection_weight_history: float = Field(default=0.6, ge=0)
    algorithm_selection_weight_problem_structure: float = Field(default=0.4, ge=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
