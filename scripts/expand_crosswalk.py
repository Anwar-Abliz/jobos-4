"""Expand crosswalk to 100% T-2 coverage and add new agent T-1 programs."""
import json
from pathlib import Path

SPEC_PATH = Path(__file__).parent.parent / "spec" / "jobos-ai-spec.json"

def main():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    # Expand agent T-1 programs to cover the full enterprise
    new_programs = [
        {"id": "A-T1-06", "program_name": "Market Intelligence Automation", "description": "Automated market research, competitive analysis, and trend detection"},
        {"id": "A-T1-07", "program_name": "Product Lifecycle Intelligence", "description": "Automated product roadmap analysis, feature prioritization, and lifecycle stage assessment"},
        {"id": "A-T1-08", "program_name": "Supply Chain Optimization", "description": "Demand forecasting, logistics optimization, and supplier management automation"},
        {"id": "A-T1-09", "program_name": "Service Delivery Automation", "description": "Automated service provisioning, quality monitoring, and SLA management"},
        {"id": "A-T1-10", "program_name": "Customer Experience Automation", "description": "Automated support routing, sentiment analysis, and retention workflows"},
        {"id": "A-T1-11", "program_name": "Talent Management Automation", "description": "Recruiting pipeline, skills assessment, learning path automation"},
        {"id": "A-T1-12", "program_name": "IT Operations Automation", "description": "Infrastructure monitoring, incident response, deployment automation"},
        {"id": "A-T1-13", "program_name": "Financial Planning Automation", "description": "Forecasting, budgeting, variance analysis automation"},
        {"id": "A-T1-14", "program_name": "Asset Management Automation", "description": "Facilities monitoring, equipment maintenance scheduling, resource allocation"},
        {"id": "A-T1-15", "program_name": "Compliance & Risk Automation", "description": "Regulatory monitoring, risk assessment, audit trail automation"},
        {"id": "A-T1-16", "program_name": "Stakeholder Communication Automation", "description": "PR monitoring, partnership coordination, government relations tracking"},
        {"id": "A-T1-17", "program_name": "Knowledge & Improvement Automation", "description": "Knowledge extraction, process mining, continuous improvement recommendations"},
    ]

    # Only add programs that don't already exist
    existing_ids = {p["id"] for p in spec["agent_catalog"]["t1_programs"]}
    for prog in new_programs:
        if prog["id"] not in existing_ids:
            spec["agent_catalog"]["t1_programs"].append(prog)

    # Full crosswalk: 36 entries, one per T-2
    full_crosswalk = [
        # T-1-01: Vision & Strategy
        {"id": "CW-01", "managerial": "M-T2-01", "agent": "A-T1-06", "mapping_rule": "Define Business Concept → Market Intelligence Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent automates market validation and concept testing subprocess"},
        {"id": "CW-02", "managerial": "M-T2-02", "agent": "A-T1-06", "mapping_rule": "Assess Internal Environment → Market Intelligence Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles data gathering and benchmarking; strategic interpretation remains human"},
        {"id": "CW-03", "managerial": "M-T2-03", "agent": "A-T1-06", "mapping_rule": "Assess External Environment → Market Intelligence Automation", "translation_type": "analog", "lossless": False, "notes": "Competitive intelligence and trend detection are core agent capabilities"},
        # T-1-02: Products & Services
        {"id": "CW-04", "managerial": "M-T2-04", "agent": "A-T1-07", "mapping_rule": "Develop Product Strategy → Product Lifecycle Intelligence", "translation_type": "decomposition", "lossless": False, "notes": "Agent provides feature prioritization data; strategic decisions remain human"},
        {"id": "CW-05", "managerial": "M-T2-05", "agent": "A-T1-07", "mapping_rule": "Design Products/Services → Product Lifecycle Intelligence", "translation_type": "decomposition", "lossless": False, "notes": "Agent assists with requirements analysis and design validation"},
        {"id": "CW-06", "managerial": "M-T2-06", "agent": "A-T1-07", "mapping_rule": "Manage Product Lifecycle → Product Lifecycle Intelligence", "translation_type": "analog", "lossless": True, "notes": "Lifecycle stage tracking and transition triggers map directly"},
        # T-1-03: Marketing & Sales
        {"id": "CW-07", "managerial": "M-T2-07", "agent": "A-T1-01", "mapping_rule": "Acquire Customers → Lead Qualification Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles qualification subprocess of full acquisition funnel"},
        {"id": "CW-08", "managerial": "M-T2-08", "agent": "A-T1-06", "mapping_rule": "Develop Marketing Strategy → Market Intelligence Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent provides market data and campaign performance analytics"},
        {"id": "CW-09", "managerial": "M-T2-09", "agent": "A-T1-04", "mapping_rule": "Manage Sales Pipeline → Order-to-Cash Optimization", "translation_type": "analog", "lossless": False, "notes": "O2C spans from sales pipeline through delivery and payment"},
        # T-1-04: Supply Chain
        {"id": "CW-10", "managerial": "M-T2-10", "agent": "A-T1-08", "mapping_rule": "Plan Supply Chain → Supply Chain Optimization", "translation_type": "analog", "lossless": True, "notes": "Demand forecasting and supply planning are core agent capabilities"},
        {"id": "CW-11", "managerial": "M-T2-11", "agent": "A-T1-05", "mapping_rule": "Procure Materials → Procure-to-Pay Automation", "translation_type": "analog", "lossless": True, "notes": "Near-direct mapping between procurement and P2P agent program"},
        {"id": "CW-12", "managerial": "M-T2-12", "agent": "A-T1-08", "mapping_rule": "Manage Logistics → Supply Chain Optimization", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles route optimization and tracking; physical logistics remain external"},
        # T-1-05: Service Delivery
        {"id": "CW-13", "managerial": "M-T2-13", "agent": "A-T1-09", "mapping_rule": "Deliver Services → Service Delivery Automation", "translation_type": "analog", "lossless": False, "notes": "Agent automates provisioning and scheduling; physical delivery remains human"},
        {"id": "CW-14", "managerial": "M-T2-14", "agent": "A-T1-09", "mapping_rule": "Manage Service Quality → Service Delivery Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent monitors SLAs and flags quality deviations"},
        # T-1-06: Customer Management
        {"id": "CW-15", "managerial": "M-T2-15", "agent": "A-T1-10", "mapping_rule": "Manage Customer Support → Customer Experience Automation", "translation_type": "analog", "lossless": False, "notes": "Agent handles ticket routing, FAQ responses, and escalation detection"},
        {"id": "CW-16", "managerial": "M-T2-16", "agent": "A-T1-03", "mapping_rule": "Retain Customers → Customer Onboarding Automation", "translation_type": "decomposition", "lossless": False, "notes": "Onboarding is a subprocess of retention strategy"},
        # T-1-07: Human Capital
        {"id": "CW-17", "managerial": "M-T2-17", "agent": "A-T1-11", "mapping_rule": "Acquire Talent → Talent Management Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles resume screening, scheduling, and initial assessment"},
        {"id": "CW-18", "managerial": "M-T2-18", "agent": "A-T1-11", "mapping_rule": "Develop Workforce → Talent Management Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent automates learning path recommendations and skills gap analysis"},
        {"id": "CW-19", "managerial": "M-T2-19", "agent": "A-T1-11", "mapping_rule": "Retain Employees → Talent Management Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent detects attrition signals and recommends engagement actions"},
        # T-1-08: Information Technology
        {"id": "CW-20", "managerial": "M-T2-20", "agent": "A-T1-12", "mapping_rule": "Manage IT Infrastructure → IT Operations Automation", "translation_type": "analog", "lossless": True, "notes": "Infrastructure monitoring and incident response are fully automatable"},
        {"id": "CW-21", "managerial": "M-T2-21", "agent": "A-T1-12", "mapping_rule": "Govern Data → IT Operations Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles data quality checks and lineage tracking; governance policy is human"},
        {"id": "CW-22", "managerial": "M-T2-22", "agent": "A-T1-12", "mapping_rule": "Manage Applications → IT Operations Automation", "translation_type": "analog", "lossless": False, "notes": "Agent automates deployment, monitoring, and performance optimization"},
        # T-1-09: Financial Management
        {"id": "CW-23", "managerial": "M-T2-23", "agent": "A-T1-13", "mapping_rule": "Manage Financial Planning → Financial Planning Automation", "translation_type": "analog", "lossless": False, "notes": "Agent automates forecasting models and variance analysis"},
        {"id": "CW-24", "managerial": "M-T2-24", "agent": "A-T1-02", "mapping_rule": "Process Transactions → Invoice Processing Automation", "translation_type": "decomposition", "lossless": False, "notes": "Invoice processing is one subprocess within transaction processing"},
        {"id": "CW-25", "managerial": "M-T2-25", "agent": "A-T1-13", "mapping_rule": "Manage Treasury → Financial Planning Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles cash flow forecasting; investment decisions remain human"},
        # T-1-10: Property Management
        {"id": "CW-26", "managerial": "M-T2-26", "agent": "A-T1-14", "mapping_rule": "Manage Facilities → Asset Management Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles scheduling, monitoring, and maintenance prediction"},
        {"id": "CW-27", "managerial": "M-T2-27", "agent": "A-T1-14", "mapping_rule": "Manage Equipment → Asset Management Automation", "translation_type": "analog", "lossless": False, "notes": "Predictive maintenance and lifecycle tracking are automatable"},
        # T-1-11: Legal & Compliance
        {"id": "CW-28", "managerial": "M-T2-28", "agent": "A-T1-15", "mapping_rule": "Manage Legal → Compliance & Risk Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles contract review and clause extraction; legal judgment is human"},
        {"id": "CW-29", "managerial": "M-T2-29", "agent": "A-T1-15", "mapping_rule": "Manage Compliance → Compliance & Risk Automation", "translation_type": "analog", "lossless": True, "notes": "Regulatory monitoring and audit trail generation are core agent capabilities"},
        {"id": "CW-30", "managerial": "M-T2-30", "agent": "A-T1-15", "mapping_rule": "Manage Risk → Compliance & Risk Automation", "translation_type": "analog", "lossless": False, "notes": "Agent performs risk scoring and monitoring; risk appetite decisions remain human"},
        # T-1-12: External Relationships
        {"id": "CW-31", "managerial": "M-T2-31", "agent": "A-T1-16", "mapping_rule": "Manage Government Relations → Stakeholder Communication Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent tracks regulatory changes and stakeholder communications"},
        {"id": "CW-32", "managerial": "M-T2-32", "agent": "A-T1-16", "mapping_rule": "Manage Partnerships → Stakeholder Communication Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent handles partner performance tracking and communication scheduling"},
        {"id": "CW-33", "managerial": "M-T2-33", "agent": "A-T1-16", "mapping_rule": "Manage Public Relations → Stakeholder Communication Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent monitors media, sentiment, and drafts communications"},
        # T-1-13: Enterprise Management
        {"id": "CW-34", "managerial": "M-T2-34", "agent": "A-T1-17", "mapping_rule": "Develop Business Capabilities → Knowledge & Improvement Automation", "translation_type": "decomposition", "lossless": False, "notes": "Agent identifies capability gaps via process mining"},
        {"id": "CW-35", "managerial": "M-T2-35", "agent": "A-T1-17", "mapping_rule": "Manage Knowledge → Knowledge & Improvement Automation", "translation_type": "analog", "lossless": True, "notes": "Knowledge extraction and organization are core agent capabilities"},
        {"id": "CW-36", "managerial": "M-T2-36", "agent": "A-T1-17", "mapping_rule": "Drive Continuous Improvement → Knowledge & Improvement Automation", "translation_type": "analog", "lossless": False, "notes": "Agent mines processes for improvement opportunities; implementation decisions are human"},
    ]

    spec["crosswalk"] = full_crosswalk

    # Update spec version
    if "version" in spec:
        spec["version"] = "0.4.0"

    SPEC_PATH.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Agent T-1 programs: {len(spec['agent_catalog']['t1_programs'])}")
    print(f"Crosswalk entries: {len(full_crosswalk)} / 36 T-2 = {len(full_crosswalk)/36*100:.0f}% coverage")
    print("Spec updated to v0.4.0")


if __name__ == "__main__":
    main()
