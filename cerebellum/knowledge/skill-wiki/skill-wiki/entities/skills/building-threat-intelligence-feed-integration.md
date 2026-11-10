---
title: building-threat-intelligence-feed-integration
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-threat-intelligence-feeds, automating-ioc-enrichment, building-automated-malware-submission-pipeline, building-incident-response-dashboard, building-ioc-defanging-and-sharing-pipeline, building-ioc-enrichment-pipeline-with-opencti, building-soc-escalation-matrix, building-threat-intelligence-enrichment-in-splunk, building-threat-intelligence-platform, evaluating-threat-intelligence-platforms, generating-threat-intelligence-reports, implementing-soar-playbook-with-palo-alto-xsoar, implementing-stix-taxii-feed-integration, implementing-threat-intelligence-lifecycle-management, processing-stix-taxii-feeds]
confidence: medium
---

Builds automated threat intelligence feed integration pipelines connecting STIX/TAXII feeds, open-source threat intel, and commercial TI platforms into SIEM and security tools for real-time IOC matching and alerting. Use when SOC teams need to operationalize threat intelligence by automating feed in

## Metadata

- **ID:** `building-threat-intelligence-feed-integration`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/building-threat-intelligence-feed-integration/SKILL.md`
- **Score:** 40.0
- **Edges:** 15

## Related Skills

- [[building-threat-intelligence-platform]] *(complement)* — Building a Threat Intelligence Platform (TIP) involves deploying and integrating multiple CTI tools into a unified system for collecting, analyzing, enriching, and disseminating threat intelligence. T
- [[implementing-stix-taxii-feed-integration]] *(complement)* — STIX (Structured Threat Information eXpression) and TAXII (Trusted Automated eXchange of Intelligence Information) are OASIS open standards for representing and transporting cyber threat intelligence.
- [[processing-stix-taxii-feeds]] *(complement)* — Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi
- [[evaluating-threat-intelligence-platforms]] *(similar)* — Evaluates and selects Threat Intelligence Platform (TIP) products based on organizational requirements including feed integration capability, STIX/TAXII support, workflow automation, analyst interface, and total cost of ownership. Use when conducting a TIP procurement, migrating between TIP solution
- [[generating-threat-intelligence-reports]] *(similar)* — Generates structured cyber threat intelligence reports at strategic, operational, and tactical levels tailored to specific audiences including executives, security operations teams, and technical analysts. Use when producing finished intelligence products from raw collection data, creating sector th
- [[analyzing-threat-intelligence-feeds]] *(complement)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[automating-ioc-enrichment]] *(complement)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[building-ioc-defanging-and-sharing-pipeline]] *(complement)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[building-ioc-enrichment-pipeline-with-opencti]] *(complement)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-enrichment-in-splunk]] *(complement)* — Build automated threat intelligence enrichment pipelines in Splunk Enterprise Security using lookup tables, modular inputs, and the Threat Intelligence Framework.
- [[building-automated-malware-submission-pipeline]] *(similar)* — Builds an automated malware submission and analysis pipeline that collects suspicious files from endpoints and email gateways, submits them to sandbox environments and multi-engine scanners, and generates verdicts with IOCs for SIEM integration. Use when SOC teams need to scale malware analysis beyo
- [[building-incident-response-dashboard]] *(similar)* — Builds real-time incident response dashboards in Splunk, Elastic, or Grafana to provide SOC analysts and leadership with situational awareness during active incidents, tracking affected systems, containment status, IOC spread, and response timeline. Use when IR teams need unified visibility during i
- [[building-soc-escalation-matrix]] *(similar)* — Build a structured SOC escalation matrix defining severity tiers, response SLAs, escalation paths, and notification procedures for security incidents.
- [[implementing-soar-playbook-with-palo-alto-xsoar]] *(similar)* — Implement automated incident response playbooks in Cortex XSOAR to orchestrate security workflows across SOC tools and reduce manual response time.
- [[implementing-threat-intelligence-lifecycle-management]] *(similar)* — Implement a structured threat intelligence lifecycle encompassing planning, collection, processing, analysis, dissemination, and feedback stages to produce actionable intelligence for organizational decision-making.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
