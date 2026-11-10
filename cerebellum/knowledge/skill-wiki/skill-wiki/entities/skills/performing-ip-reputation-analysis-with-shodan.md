---
title: performing-ip-reputation-analysis-with-shodan
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-apt-group-with-mitre-navigator, analyzing-indicators-of-compromise, analyzing-threat-landscape-with-misp, automating-ioc-enrichment, collecting-threat-intelligence-with-misp, performing-dns-tunneling-detection, performing-malware-hash-enrichment-with-virustotal, performing-malware-ioc-extraction]
confidence: low
---

Analyze IP address reputation using the Shodan API to identify open ports, running services, known vulnerabilities, and hosting context for threat intelligence enrichment and incident triage.

## Metadata

- **ID:** `performing-ip-reputation-analysis-with-shodan`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-ip-reputation-analysis-with-shodan/SKILL.md`
- **Score:** 38.0
- **Edges:** 8

## Related Skills

- [[analyzing-indicators-of-compromise]] *(similar)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[automating-ioc-enrichment]] *(similar)* — Automates the enrichment of raw indicators of compromise with multi-source threat intelligence context using SOAR platforms, Python pipelines, or TIP playbooks to reduce analyst triage time and standardize enrichment outputs. Use when building automated enrichment workflows integrated with SIEM aler
- [[collecting-threat-intelligence-with-misp]] *(similar)* — MISP (Malware Information Sharing Platform) is an open-source threat intelligence platform for gathering, sharing, storing, and correlating Indicators of Compromise (IOCs) of targeted attacks, threat
- [[performing-malware-hash-enrichment-with-virustotal]] *(similar)* — Enrich malware file hashes using the VirusTotal API to retrieve detection rates, behavioral analysis, YARA matches, and contextual threat intelligence for incident triage and IOC validation.
- [[performing-malware-ioc-extraction]] *(similar)* — Malware IOC extraction is the process of analyzing malicious software to identify actionable indicators of compromise including file hashes, network indicators (C2 domains, IP addresses, URLs), regist
- [[analyzing-apt-group-with-mitre-navigator]] *(similar)* — Analyze advanced persistent threat (APT) group techniques using MITRE ATT&CK Navigator to create layered heatmaps of adversary TTPs for detection gap analysis and threat-informed defense.
- [[analyzing-threat-landscape-with-misp]] *(similar)* — Analyze the threat landscape using MISP (Malware Information Sharing Platform) by querying event statistics, attribute distributions, threat actor galaxy clusters, and tag trends over time. Uses PyMISP to pull event data, compute IOC type breakdowns, identify top threat actors and malware families, 
- [[performing-dns-tunneling-detection]] *(similar)* — Detects DNS tunneling by computing Shannon entropy of DNS query names, analyzing query length distributions, inspecting TXT record payloads, and identifying high subdomain cardinality. Uses scapy for packet capture analysis and statistical methods to distinguish legitimate DNS from covert channels. 

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
