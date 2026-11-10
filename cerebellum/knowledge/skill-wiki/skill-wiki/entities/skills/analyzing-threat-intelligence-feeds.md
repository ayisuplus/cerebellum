---
title: analyzing-threat-intelligence-feeds
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-apt-group-with-mitre-navigator, analyzing-indicators-of-compromise, analyzing-ransomware-network-indicators, analyzing-threat-landscape-with-misp, automating-ioc-enrichment, building-ioc-enrichment-pipeline-with-opencti, building-threat-intelligence-enrichment-in-splunk, building-threat-intelligence-feed-integration, building-threat-intelligence-platform, collecting-indicators-of-compromise, collecting-threat-intelligence-with-misp, correlating-threat-campaigns, evaluating-threat-intelligence-platforms, generating-threat-intelligence-reports, hunting-advanced-persistent-threats, implementing-security-information-sharing-with-stix2, implementing-stix-taxii-feed-integration, implementing-threat-intelligence-lifecycle-management, performing-malware-ioc-extraction, performing-threat-hunting-with-yara-rules, processing-stix-taxii-feeds]
confidence: medium
---

Analyzes structured and unstructured threat intelligence feeds to extract actionable indicators, adversary tactics, and campaign context. Use when ingesting commercial or open-source CTI feeds, evaluating feed quality, normalizing data into STIX 2.1 format, or enriching existing IOCs with campaign a

## Metadata

- **ID:** `analyzing-threat-intelligence-feeds`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-threat-intelligence-feeds/SKILL.md`
- **Score:** 43.0
- **Edges:** 21

## Related Skills

- [[automating-ioc-enrichment]] *(complement)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[building-threat-intelligence-feed-integration]] *(complement)* — Builds automated threat intelligence feed integration pipelines connecting STIX/TAXII feeds, open-source threat intel, and commercial TI platforms into SIEM and security tools for real-time IOC matching and alerting. Use when SOC teams need to operationalize threat intelligence by automating feed in
- [[correlating-threat-campaigns]] *(complement)* — Correlates disparate security incidents, IOCs, and adversary behaviors across time and organizations to identify unified threat campaigns, attribute them to common threat actors, and extract shared indicators for improved detection. Use when multiple incidents exhibit overlapping indicators, when se
- [[processing-stix-taxii-feeds]] *(complement)* — Processes STIX 2.1 threat intelligence bundles delivered via TAXII 2.1 servers, normalizing objects into platform-native schemas and routing them to appropriate consuming systems. Use when onboarding new TAXII collection endpoints, automating bi-directional intelligence sharing with ISACs, or buildi
- [[generating-threat-intelligence-reports]] *(similar)* — Generates structured cyber threat intelligence reports at strategic, operational, and tactical levels tailored to specific audiences including executives, security operations teams, and technical analysts. Use when producing finished intelligence products from raw collection data, creating sector th
- [[analyzing-indicators-of-compromise]] *(complement)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[analyzing-apt-group-with-mitre-navigator]] *(similar)* — Analyze advanced persistent threat (APT) group techniques using MITRE ATT&CK Navigator to create layered heatmaps of adversary TTPs for detection gap analysis and threat-informed defense.
- [[analyzing-ransomware-network-indicators]] *(similar)* — Identify ransomware network indicators including C2 beaconing patterns, TOR exit node connections, data exfiltration flows, and encryption key exchange via Zeek conn.log and NetFlow analysis
- [[analyzing-threat-landscape-with-misp]] *(similar)* — Analyze the threat landscape using MISP (Malware Information Sharing Platform) by querying event statistics, attribute distributions, threat actor galaxy clusters, and tag trends over time. Uses PyMISP to pull event data, compute IOC type breakdowns, identify top threat actors and malware families, 
- [[building-ioc-enrichment-pipeline-with-opencti]] *(similar)* — OpenCTI is an open-source platform for managing cyber threat intelligence knowledge, built on STIX 2.1 as its native data model. This skill covers building an automated IOC enrichment pipeline using O
- [[building-threat-intelligence-enrichment-in-splunk]] *(similar)* — Build automated threat intelligence enrichment pipelines in Splunk Enterprise Security using lookup tables, modular inputs, and the Threat Intelligence Framework.
- [[building-threat-intelligence-platform]] *(similar)* — Building a Threat Intelligence Platform (TIP) involves deploying and integrating multiple CTI tools into a unified system for collecting, analyzing, enriching, and disseminating threat intelligence. T
- [[collecting-indicators-of-compromise]] *(similar)* — Systematically collects, categorizes, and distributes indicators of compromise (IOCs) during and after security incidents to enable detection, blocking, and threat intelligence sharing. Covers network, host, email, and behavioral indicators using STIX/TAXII formats and threat intelligence platforms.
- [[collecting-threat-intelligence-with-misp]] *(similar)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[evaluating-threat-intelligence-platforms]] *(similar)* — Evaluates and selects Threat Intelligence Platform (TIP) products based on organizational requirements including feed integration capability, STIX/TAXII support, workflow automation, analyst interface, and total cost of ownership. Use when conducting a TIP procurement, migrating between TIP solution
- [[hunting-advanced-persistent-threats]] *(similar)* — Proactively hunts for Advanced Persistent Threat (APT) activity within enterprise environments using hypothesis-driven searches across endpoint telemetry, network logs, and memory artifacts. Use when conducting scheduled threat hunting cycles, investigating anomalous behavior flagged by UEBA, or val
- [[implementing-security-information-sharing-with-stix2]] *(similar)* — Create, validate, and share STIX 2.1 threat intelligence objects using the stix2 Python library. Covers indicators, malware, campaigns, relationships, bundles, and TAXII 2.1 publishing.

- [[implementing-stix-taxii-feed-integration]] *(similar)* — STIX (Structured Threat Information eXpression) and TAXII (Trusted Automated eXchange of Intelligence Information) are OASIS open standards for representing and transporting cyber threat intelligence.
- [[implementing-threat-intelligence-lifecycle-management]] *(similar)* — Implement a structured threat intelligence lifecycle encompassing planning, collection, processing, analysis, dissemination, and feedback stages to produce actionable intelligence for organizational decision-making.
- [[performing-malware-ioc-extraction]] *(similar)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist
- [[performing-threat-hunting-with-yara-rules]] *(similar)* — Use YARA pattern-matching rules to hunt for malware, suspicious files, and indicators of compromise across filesystems and memory dumps. Covers rule authoring, yara-python scanning, and integration with threat intel feeds.


## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
