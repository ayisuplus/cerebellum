---
title: automating-ioc-enrichment
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, analyzing-threat-intelligence-feeds, building-automated-malware-submission-pipeline, building-ioc-defanging-and-sharing-pipeline, building-ioc-enrichment-pipeline-with-opencti, building-threat-intelligence-enrichment-in-splunk, building-threat-intelligence-feed-integration, building-threat-intelligence-platform, collecting-indicators-of-compromise, correlating-threat-campaigns, detecting-aws-guardduty-findings-automation, evaluating-threat-intelligence-platforms, generating-threat-intelligence-reports, implementing-soar-automation-with-phantom, implementing-soar-playbook-for-phishing, implementing-soar-playbook-with-palo-alto-xsoar, performing-indicator-lifecycle-management, performing-ip-reputation-analysis-with-shodan, performing-malware-hash-enrichment-with-virustotal, processing-stix-taxii-feeds]
confidence: medium
---

Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler

## Metadata

- **ID:** `automating-ioc-enrichment`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/automating-ioc-enrichment/SKILL.md`
- **Score:** 67.0
- **Edges:** 20

## Related Skills

- [[building-ioc-defanging-and-sharing-pipeline]] *(complement)* — Build an automated pipeline to defang indicators of compromise (URLs, IPs, domains, emails) for safe sharing and distribute them in STIX format through TAXII feeds and threat intelligence platforms.
- [[building-ioc-enrichment-pipeline-with-opencti]] *(complement)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-feed-integration]] *(complement)* — Builds automated threat intelligence feed integration pipelines connecting STIX/TAXII feeds, open-source threat intel, and commercial TI platforms into SIEM and security tools for real-time IOC matching and alerting. Use when SOC teams need to operationalize threat intelligence by automating feed in
- [[implementing-soar-automation-with-phantom]] *(complement)* — Implements Security Orchestration, Automation, and Response (SOAR) workflows using Splunk SOAR (formerly Phantom) to automate alert triage, IOC enrichment, containment actions, and incident response playbooks. Use when SOC teams need to reduce manual analyst work, standardize response procedures, or
- [[building-threat-intelligence-enrichment-in-splunk]] *(similar)* — Build automated threat intelligence enrichment pipelines in Splunk Enterprise Security using lookup tables, modular inputs, and the Threat Intelligence Framework.
- [[analyzing-indicators-of-compromise]] *(complement)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[analyzing-threat-intelligence-feeds]] *(complement)* — Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a
- [[building-automated-malware-submission-pipeline]] *(similar)* — Builds an automated malware submission and analysis pipeline that collects suspicious files from endpoints and email gateways, submits them to sandbox environments and multi-engine scanners, and generates verdicts with IOCs for SIEM integration. Use when SOC teams need to scale malware analysis beyo
- [[building-threat-intelligence-platform]] *(similar)* — Building a Threat Intelligence Platform (TIP) involves deploying and integrating multiple CTI tools into a unified system for collecting, analyzing, enriching, and disseminating threat intelligence. T
- [[collecting-indicators-of-compromise]] *(similar)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[correlating-threat-campaigns]] *(similar)* — Correlates disparate security incidents, IOCs, and adversary behaviors across time and organizations to identify unified threat campaigns, attribute them to common threat actors, and extract shared indicators for improved detection. Use when multiple incidents exhibit overlapping indicators, when se
- [[detecting-aws-guardduty-findings-automation]] *(similar)* — Automate AWS GuardDuty threat detection findings processing using EventBridge and Lambda to enable real-time incident response, automatic quarantine of compromised resources, and security notification workflows.
- [[evaluating-threat-intelligence-platforms]] *(similar)* — Evaluates and selects Threat Intelligence Platform (TIP) products based on organizational requirements including feed integration capability, STIX/TAXII support, workflow automation, analyst interface, and total cost of ownership. Use when conducting a TIP procurement, migrating between TIP solution
- [[generating-threat-intelligence-reports]] *(similar)* — Generates structured cyber threat intelligence reports at strategic, operational, and tactical levels tailored to specific audiences including executives, security operations teams, and technical analysts. Use when producing finished intelligence products from raw collection data, creating sector th
- [[implementing-soar-playbook-for-phishing]] *(similar)* — Automate phishing incident response using Splunk SOAR REST API to create containers, add artifacts, and trigger playbooks
- [[implementing-soar-playbook-with-palo-alto-xsoar]] *(similar)* — Implement automated incident response playbooks in Cortex XSOAR to orchestrate security workflows across SOC tools and reduce manual response time.
- [[performing-indicator-lifecycle-management]] *(similar)* — Indicator lifecycle management tracks IOCs from initial discovery through validation, enrichment, deployment, monitoring, and eventual retirement. This skill covers implementing systematic processes f
- [[performing-ip-reputation-analysis-with-shodan]] *(similar)* — Analyze IP address reputation using the Shodan API to identify open ports, running services, known vulnerabilities, and hosting context for threat intelligence enrichment and incident triage.
- [[performing-malware-hash-enrichment-with-virustotal]] *(similar)* — Enrich malware file hashes using the VirusTotal API to retrieve detection rates, behavioral analysis, YARA matches, and contextual threat intelligence for incident triage and IOC validation.
- [[processing-stix-taxii-feeds]] *(similar)* — Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi

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
