"""Tests for SAP simulation adapter."""
from __future__ import annotations

from jobos.adapters.sap_simulation import (
    O2C_TEMPLATE,
    P2P_TEMPLATE,
    R2R_TEMPLATE,
    ALL_TEMPLATES,
    SAP_OBJECT_CATALOG,
    DEFAULT_ORG_STRUCTURE,
)
from jobos.adapters.sap_simulation.data_generator import (
    generate_metric_value,
    generate_process_metrics,
    generate_volume_data,
    generate_cycle_time_samples,
)


class TestProcessTemplates:
    def test_all_templates_present(self):
        assert "O2C" in ALL_TEMPLATES
        assert "P2P" in ALL_TEMPLATES
        assert "R2R" in ALL_TEMPLATES

    def test_o2c_structure(self):
        t = O2C_TEMPLATE
        assert t["name"] == "Order-to-Cash"
        assert t["sap_module"] == "SD"
        assert len(t["steps"]) == 8
        for step in t["steps"]:
            assert "name" in step
            assert "tcode" in step
            assert "objects" in step
            assert "kpis" in step

    def test_p2p_structure(self):
        t = P2P_TEMPLATE
        assert t["name"] == "Procure-to-Pay"
        assert len(t["steps"]) == 6

    def test_r2r_structure(self):
        t = R2R_TEMPLATE
        assert t["name"] == "Record-to-Report"
        assert len(t["steps"]) == 5

    def test_all_steps_have_imperfections(self):
        for name, template in ALL_TEMPLATES.items():
            for step in template["steps"]:
                assert "imperfections" in step, f"{name}/{step['name']} missing imperfections"
                assert len(step["imperfections"]) > 0


class TestObjectCatalog:
    def test_key_objects_present(self):
        for key in ["SalesOrder", "Customer", "Material", "Vendor", "PurchaseOrder"]:
            assert key in SAP_OBJECT_CATALOG
            obj = SAP_OBJECT_CATALOG[key]
            assert "sap_table" in obj
            assert "key_fields" in obj

    def test_all_objects_have_fields(self):
        for name, obj in SAP_OBJECT_CATALOG.items():
            assert "fields" in obj, f"{name} missing fields"
            assert len(obj["fields"]) > 0


class TestOrgStructure:
    def test_structure(self):
        cc = DEFAULT_ORG_STRUCTURE["company_code"]
        assert cc["name"] == "Global Corp"
        assert cc["sap_code"] == "1000"
        assert len(cc["plants"]) == 3
        assert len(cc["sales_orgs"]) == 2
        assert len(cc["purchasing_orgs"]) == 1


class TestDataGenerator:
    def test_generate_metric_value(self):
        val = generate_metric_value([0.5, 1.0])
        assert 0.5 <= val <= 1.0

    def test_generate_process_metrics(self):
        metrics = generate_process_metrics(O2C_TEMPLATE)
        assert "steps" in metrics
        assert "overall" in metrics
        assert "Create Sales Order" in metrics["steps"]
        assert "cycle_time_hours" in metrics["overall"]

    def test_generate_volume_data(self):
        data = generate_volume_data(num_days=7)
        assert len(data) == 7
        for d in data:
            assert "date" in d
            assert "volume" in d

    def test_generate_cycle_time_samples(self):
        samples = generate_cycle_time_samples(n=50)
        assert len(samples) == 50
        assert all(s > 0 for s in samples)
