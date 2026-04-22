"""SAP Business Object Catalog — Realistic object definitions.

Each object includes type, primary SAP table, key fields, and
representative field schemas.
"""
from __future__ import annotations

SAP_OBJECT_CATALOG: dict[str, dict] = {
    "SalesOrder": {
        "object_type": "SalesOrder",
        "sap_table": "VBAK",
        "key_fields": ["VBELN"],
        "fields": ["AUART", "KUNNR", "VKORG", "VTWEG", "SPART", "ERDAT", "NETWR", "WAERK"],
    },
    "Customer": {
        "object_type": "Customer",
        "sap_table": "KNA1",
        "key_fields": ["KUNNR"],
        "fields": ["NAME1", "LAND1", "ORT01", "STRAS", "PSTLZ", "KTOKD"],
    },
    "Material": {
        "object_type": "Material",
        "sap_table": "MARA",
        "key_fields": ["MATNR"],
        "fields": ["MTART", "MATKL", "MEINS", "BRGEW", "GEWEI", "SPART"],
    },
    "Vendor": {
        "object_type": "Vendor",
        "sap_table": "LFA1",
        "key_fields": ["LIFNR"],
        "fields": ["NAME1", "LAND1", "ORT01", "STRAS", "KTOKK"],
    },
    "PurchaseOrder": {
        "object_type": "PurchaseOrder",
        "sap_table": "EKKO",
        "key_fields": ["EBELN"],
        "fields": ["BSART", "LIFNR", "EKORG", "EKGRP", "BEDAT", "WAERS"],
    },
    "PurchaseRequisition": {
        "object_type": "PurchaseRequisition",
        "sap_table": "EBAN",
        "key_fields": ["BANFN"],
        "fields": ["BSART", "MATNR", "MENGE", "MEINS", "WERKS"],
    },
    "Delivery": {
        "object_type": "Delivery",
        "sap_table": "LIKP",
        "key_fields": ["VBELN"],
        "fields": ["LFART", "KUNNR", "WADAT", "KODAT", "BTGEW", "GEWEI"],
    },
    "BillingDocument": {
        "object_type": "BillingDocument",
        "sap_table": "VBRK",
        "key_fields": ["VBELN"],
        "fields": ["FKART", "KUNAG", "FKDAT", "NETWR", "WAERK"],
    },
    "Payment": {
        "object_type": "Payment",
        "sap_table": "BSEG",
        "key_fields": ["BUKRS", "BELNR", "GJAHR"],
        "fields": ["BUZEI", "SHKZG", "DMBTR", "WRBTR", "WAERS"],
    },
    "GLAccount": {
        "object_type": "GLAccount",
        "sap_table": "SKA1",
        "key_fields": ["KTOPL", "SAKNR"],
        "fields": ["XBILK", "GVTYP", "KTOKS"],
    },
    "CostCenter": {
        "object_type": "CostCenter",
        "sap_table": "CSKS",
        "key_fields": ["KOKRS", "KOSTL"],
        "fields": ["DATBI", "DATAB", "VERAK", "KOSAR", "WAERS"],
    },
    "Plant": {
        "object_type": "Plant",
        "sap_table": "T001W",
        "key_fields": ["WERKS"],
        "fields": ["NAME1", "STRAS", "PSTLZ", "ORT01", "LAND1", "BUKRS"],
    },
    "CompanyCode": {
        "object_type": "CompanyCode",
        "sap_table": "T001",
        "key_fields": ["BUKRS"],
        "fields": ["BUTXT", "LAND1", "WAERS", "KTOPL", "SPRAS"],
    },
}
