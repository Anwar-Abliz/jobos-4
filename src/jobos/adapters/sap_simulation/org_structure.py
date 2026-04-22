"""SAP Organizational Structure Template.

Provides a default org structure hierarchy:
Company Code → Plants → Sales Orgs → Purchasing Orgs.
"""
from __future__ import annotations

DEFAULT_ORG_STRUCTURE: dict = {
    "company_code": {
        "name": "Global Corp",
        "sap_code": "1000",
        "country": "DE",
        "currency": "EUR",
        "plants": [
            {
                "name": "Main Plant",
                "sap_code": "1000",
                "country": "DE",
            },
            {
                "name": "US Plant",
                "sap_code": "2000",
                "country": "US",
            },
            {
                "name": "Asia Plant",
                "sap_code": "3000",
                "country": "CN",
            },
        ],
        "sales_orgs": [
            {
                "name": "Domestic Sales",
                "sap_code": "1000",
                "country": "DE",
                "currency": "EUR",
            },
            {
                "name": "Export Sales",
                "sap_code": "2000",
                "country": "US",
                "currency": "USD",
            },
        ],
        "purchasing_orgs": [
            {
                "name": "Central Purchasing",
                "sap_code": "1000",
                "country": "DE",
                "currency": "EUR",
            },
        ],
        "profit_centers": [
            {"name": "Product Line A", "sap_code": "PC1000"},
            {"name": "Product Line B", "sap_code": "PC2000"},
            {"name": "Services", "sap_code": "PC3000"},
        ],
        "cost_centers": [
            {"name": "Manufacturing", "sap_code": "CC1000"},
            {"name": "R&D", "sap_code": "CC2000"},
            {"name": "Sales & Marketing", "sap_code": "CC3000"},
            {"name": "Administration", "sap_code": "CC4000"},
        ],
    },
}
