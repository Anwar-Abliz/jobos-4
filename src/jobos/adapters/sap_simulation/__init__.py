"""JobOS 4.0 — SAP Simulation Adapter.

Provides realistic SAP process templates, object catalogs, and org structures
for development and testing without requiring a live SAP system.
"""
from jobos.adapters.sap_simulation.object_catalog import SAP_OBJECT_CATALOG
from jobos.adapters.sap_simulation.org_structure import DEFAULT_ORG_STRUCTURE
from jobos.adapters.sap_simulation.process_templates import (
    ALL_TEMPLATES,
    O2C_TEMPLATE,
    P2P_TEMPLATE,
    R2R_TEMPLATE,
)

__all__ = [
    "O2C_TEMPLATE",
    "P2P_TEMPLATE",
    "R2R_TEMPLATE",
    "ALL_TEMPLATES",
    "SAP_OBJECT_CATALOG",
    "DEFAULT_ORG_STRUCTURE",
]
