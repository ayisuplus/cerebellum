---
title: triaging-security-incident
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-indicators-of-compromise, building-incident-response-playbook, building-patch-tuesday-response-process, building-soc-escalation-matrix, conducting-cloud-incident-response, conducting-malware-incident-response, conducting-phishing-incident-response, conducting-post-incident-lessons-learned, implementing-ot-incident-response-playbook, implementing-soar-automation-with-phantom, investigating-phishing-email-incident, performing-endpoint-forensics-investigation, performing-insider-threat-investigation, performing-ransomware-response, performing-soc-tabletop-exercise]
confidence: medium
---

Performs initial triage of security incidents to determine severity, scope, and required response actions using the NIST SP 800-61r3 and SANS PICERL frameworks. Classifies incidents by type, assigns priority based on business impact, and routes to appropriate response teams. Activates for requests i

## Metadata

- **ID:** `triaging-security-incident`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/triaging-security-incident/SKILL.md`
- **Score:** 52.0
- **Edges:** 15

## Related Skills

- [[analyzing-indicators-of-compromise]] *(similar)* — Analyzes indicators of compromise (IOCs) including IP addresses, domains, file hashes, URLs, and email artifacts to determine maliciousness confidence, campaign attribution, and blocking priority. Use when triaging IOCs from phishing emails, security alerts, or external threat feeds; enriching raw I
- [[building-incident-response-playbook]] *(similar)* — Designs and documents structured incident response playbooks that define step-by-step procedures for specific incident types aligned with NIST SP 800-61r3 and SANS PICERL frameworks. Covers playbook structure, decision trees, escalation criteria, RACI matrices, and integration with SOAR platforms. A
- [[conducting-phishing-incident-response]] *(similar)* — Responds to phishing incidents by analyzing reported emails, extracting indicators, assessing credential compromise, quarantining malicious messages across the organization, and remediating affected accounts. Covers email header analysis, URL/attachment sandboxing, and mailbox-wide purge operations.
- [[implementing-soar-automation-with-phantom]] *(similar)* — Implements Security Orchestration, Automation, and Response (SOAR) workflows using Splunk SOAR (formerly Phantom) to automate alert triage, IOC enrichment, containment actions, and incident response playbooks. Use when SOC teams need to reduce manual analyst work, standardize response procedures, or
- [[performing-endpoint-forensics-investigation]] *(similar)* — Performs digital forensics investigation on compromised endpoints including memory acquisition, disk imaging, artifact analysis, and timeline reconstruction. Use when investigating security incidents, collecting evidence for legal proceedings, or analyzing endpoint compromise scope. Activates for re
- [[building-patch-tuesday-response-process]] *(similar)* — Establish a structured operational process to triage, test, and deploy Microsoft Patch Tuesday security updates within risk-based remediation SLAs.
- [[building-soc-escalation-matrix]] *(similar)* — Build a structured SOC escalation matrix defining severity tiers, response SLAs, escalation paths, and notification procedures for security incidents.
- [[conducting-cloud-incident-response]] *(similar)* — Responds to security incidents in cloud environments (AWS, Azure, GCP) by performing identity-based containment, cloud-native log analysis, resource isolation, and forensic evidence acquisition adapted for ephemeral cloud infrastructure. Activates for requests involving cloud incident response, AWS 
- [[conducting-malware-incident-response]] *(similar)* — Responds to malware infections across enterprise endpoints by identifying the malware family, determining infection vectors, assessing spread, and executing eradication procedures. Covers the full lifecycle from detection through containment, analysis, removal, and recovery. Activates for requests i
- [[conducting-post-incident-lessons-learned]] *(similar)* — Facilitate structured post-incident reviews to identify root causes, document what worked and failed, and produce actionable recommendations to improve future incident response.
- [[implementing-ot-incident-response-playbook]] *(similar)* — Develop and implement OT-specific incident response playbooks aligned with SANS PICERL framework, IEC 62443, and NIST SP 800-82 that address unique ICS challenges including safety-critical systems, limited downtime tolerance, and coordination between IT SOC, OT engineering, and plant operations team
- [[investigating-phishing-email-incident]] *(similar)* — Investigates phishing email incidents from initial user report through header analysis, URL/attachment detonation, impacted user identification, and containment actions using SOC tools like Splunk, Microsoft Defender, and sandbox analysis platforms. Use when a reported phishing email requires full i
- [[performing-insider-threat-investigation]] *(similar)* — Investigates insider threat incidents involving employees, contractors, or trusted partners who misuse authorized access to steal data, sabotage systems, or violate security policies. Combines digital forensics, user behavior analytics, and HR/legal coordination to build an evidence-based case. Acti
- [[performing-ransomware-response]] *(similar)* — Executes a structured ransomware incident response from initial detection through containment, forensic analysis, decryption assessment, recovery, and post-incident hardening. Addresses ransom negotiation considerations, backup integrity verification, and regulatory notification requirements. Activa
- [[performing-soc-tabletop-exercise]] *(similar)* — Performs tabletop exercises for SOC teams simulating security incidents through discussion-based scenarios to test incident response procedures, communication workflows, and decision-making under pressure without impacting production systems. Use when organizations need to validate IR playbooks, tra

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
