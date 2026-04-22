"""SAP Process Templates — Realistic E2E process definitions.

Each template includes named steps with T-codes, Fiori app IDs,
business objects touched, KPIs, and common imperfections.
"""
from __future__ import annotations

O2C_TEMPLATE: dict = {
    "name": "Order-to-Cash",
    "short_name": "O2C",
    "sap_module": "SD",
    "process_type": "e2e",
    "steps": [
        {
            "name": "Create Sales Order",
            "tcode": "VA01",
            "fiori_app_id": "F2342",
            "objects": ["SalesOrder", "Customer", "Material"],
            "kpis": {"order_accuracy": [0.95, 1.0], "order_time_min": [0, 15]},
            "imperfections": [
                "Incorrect pricing due to stale condition records",
                "Manual data entry errors in customer PO reference",
            ],
        },
        {
            "name": "Check Availability",
            "tcode": "VA01",
            "fiori_app_id": "F2342",
            "objects": ["Material", "Plant"],
            "kpis": {"atp_accuracy": [0.9, 1.0], "check_time_sec": [0, 5]},
            "imperfections": [
                "ATP check fails to account for reserved stock",
            ],
        },
        {
            "name": "Approve Credit",
            "tcode": "VKM1",
            "fiori_app_id": "F0300",
            "objects": ["Customer", "CreditManagement"],
            "kpis": {"approval_time_hours": [0, 4], "auto_approval_rate": [0.6, 1.0]},
            "imperfections": [
                "Credit blocks delay shipment unnecessarily",
                "Manual credit checks for low-risk customers",
            ],
        },
        {
            "name": "Create Delivery",
            "tcode": "VL01N",
            "fiori_app_id": "F5303",
            "objects": ["Delivery", "SalesOrder", "Material"],
            "kpis": {"delivery_time_hours": [0, 24], "pick_accuracy": [0.98, 1.0]},
            "imperfections": [
                "Partial deliveries due to inventory discrepancies",
            ],
        },
        {
            "name": "Pick and Pack",
            "tcode": "LT03",
            "fiori_app_id": "F1654",
            "objects": ["Delivery", "Material", "StorageLocation"],
            "kpis": {"pick_time_min": [0, 30], "pack_accuracy": [0.99, 1.0]},
            "imperfections": [
                "Warehouse mislocation causes pick errors",
            ],
        },
        {
            "name": "Post Goods Issue",
            "tcode": "VL02N",
            "fiori_app_id": "F5303",
            "objects": ["Delivery", "Material"],
            "kpis": {"gi_time_min": [0, 5], "gi_accuracy": [0.99, 1.0]},
            "imperfections": [
                "Goods issue posted before physical shipment",
            ],
        },
        {
            "name": "Create Invoice",
            "tcode": "VF01",
            "fiori_app_id": "F5400",
            "objects": ["BillingDocument", "SalesOrder", "Customer"],
            "kpis": {"invoice_accuracy": [0.98, 1.0], "invoice_time_hours": [0, 2]},
            "imperfections": [
                "Pricing discrepancies between order and invoice",
                "Delayed invoicing due to missing proof of delivery",
            ],
        },
        {
            "name": "Receive Payment",
            "tcode": "F-28",
            "fiori_app_id": "F0711",
            "objects": ["Payment", "Customer", "BillingDocument"],
            "kpis": {"dso_days": [0, 45], "payment_match_rate": [0.9, 1.0]},
            "imperfections": [
                "Manual payment matching for partial payments",
                "Unidentified incoming payments",
            ],
        },
    ],
    "overall_kpis": {
        "cycle_time_hours": [24, 168],
        "first_pass_rate": [0.85, 1.0],
        "automation_rate": [0.3, 0.9],
        "customer_satisfaction": [1, 10],
    },
}


P2P_TEMPLATE: dict = {
    "name": "Procure-to-Pay",
    "short_name": "P2P",
    "sap_module": "MM",
    "process_type": "e2e",
    "steps": [
        {
            "name": "Create Purchase Requisition",
            "tcode": "ME51N",
            "fiori_app_id": "F1637",
            "objects": ["PurchaseRequisition", "Material"],
            "kpis": {"req_time_min": [0, 15], "auto_req_rate": [0.4, 1.0]},
            "imperfections": [
                "Free-text requisitions bypass catalog compliance",
            ],
        },
        {
            "name": "Source and Select Vendor",
            "tcode": "ME47",
            "fiori_app_id": "F2220",
            "objects": ["Vendor", "SourceList"],
            "kpis": {"sourcing_time_days": [0, 5], "contract_coverage": [0.7, 1.0]},
            "imperfections": [
                "Maverick buying outside preferred vendor list",
            ],
        },
        {
            "name": "Create Purchase Order",
            "tcode": "ME21N",
            "fiori_app_id": "F2417",
            "objects": ["PurchaseOrder", "Vendor", "Material"],
            "kpis": {"po_accuracy": [0.95, 1.0], "po_time_min": [0, 10]},
            "imperfections": [
                "PO price deviations from contract terms",
            ],
        },
        {
            "name": "Receive Goods",
            "tcode": "MIGO",
            "fiori_app_id": "F0842",
            "objects": ["GoodsReceipt", "PurchaseOrder", "Material"],
            "kpis": {"gr_time_hours": [0, 4], "gr_accuracy": [0.98, 1.0]},
            "imperfections": [
                "Quantity discrepancies between PO and delivery",
            ],
        },
        {
            "name": "Verify Invoice",
            "tcode": "MIRO",
            "fiori_app_id": "F0862",
            "objects": ["InvoiceReceipt", "PurchaseOrder", "Vendor"],
            "kpis": {"three_way_match_rate": [0.85, 1.0], "invoice_time_min": [0, 20]},
            "imperfections": [
                "Three-way match failures require manual intervention",
                "Duplicate invoice submissions",
            ],
        },
        {
            "name": "Process Payment",
            "tcode": "F110",
            "fiori_app_id": "F0710",
            "objects": ["Payment", "Vendor"],
            "kpis": {
                "payment_on_time_rate": [0.9, 1.0],
                "early_payment_discount_capture": [0.5, 1.0],
            },
            "imperfections": [
                "Missed early payment discounts",
                "Payment run errors due to blocked invoices",
            ],
        },
    ],
    "overall_kpis": {
        "cycle_time_hours": [48, 336],
        "first_pass_rate": [0.8, 1.0],
        "automation_rate": [0.25, 0.85],
        "vendor_satisfaction": [1, 10],
    },
}


R2R_TEMPLATE: dict = {
    "name": "Record-to-Report",
    "short_name": "R2R",
    "sap_module": "FI",
    "process_type": "e2e",
    "steps": [
        {
            "name": "Record Journal Entry",
            "tcode": "FB50",
            "fiori_app_id": "F0717",
            "objects": ["JournalEntry", "GLAccount"],
            "kpis": {"posting_accuracy": [0.98, 1.0], "posting_time_min": [0, 5]},
            "imperfections": [
                "Incorrect GL account assignment",
            ],
        },
        {
            "name": "Process Intercompany",
            "tcode": "FB01",
            "fiori_app_id": "F0717",
            "objects": ["JournalEntry", "CompanyCode"],
            "kpis": {"ic_reconciliation_rate": [0.95, 1.0]},
            "imperfections": [
                "Intercompany imbalances require manual reconciliation",
            ],
        },
        {
            "name": "Reconcile Accounts",
            "tcode": "FAGLB03",
            "fiori_app_id": "F3677",
            "objects": ["GLAccount", "CompanyCode"],
            "kpis": {"reconciliation_time_hours": [0, 8], "exception_rate": [0, 0.05]},
            "imperfections": [
                "High volume of manual clearing items",
            ],
        },
        {
            "name": "Close Period",
            "tcode": "AJAB",
            "fiori_app_id": "F2543",
            "objects": ["FiscalPeriod", "CompanyCode"],
            "kpis": {"close_time_days": [0, 5], "adjustment_rate": [0, 0.03]},
            "imperfections": [
                "Late postings delay period close",
            ],
        },
        {
            "name": "Generate Reports",
            "tcode": "S_ALR_87012284",
            "fiori_app_id": "F2187",
            "objects": ["FinancialReport", "CompanyCode"],
            "kpis": {"report_time_hours": [0, 4], "report_accuracy": [0.99, 1.0]},
            "imperfections": [
                "Manual adjustments to financial statements",
            ],
        },
    ],
    "overall_kpis": {
        "close_cycle_days": [3, 15],
        "first_pass_rate": [0.9, 1.0],
        "automation_rate": [0.2, 0.75],
        "audit_readiness": [1, 10],
    },
}


ALL_TEMPLATES: dict[str, dict] = {
    "O2C": O2C_TEMPLATE,
    "P2P": P2P_TEMPLATE,
    "R2R": R2R_TEMPLATE,
}
