---
title: hunting-for-dns-based-persistence
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-email-headers-for-phishing-investigation, analyzing-network-covert-channels-in-malware, exploiting-broken-link-hijacking, hunting-for-data-exfiltration-indicators, hunting-for-dcsync-attacks, hunting-for-living-off-the-cloud-techniques, hunting-for-suspicious-scheduled-tasks, hunting-saas-sso-token-abuse, performing-dns-enumeration-and-zone-transfer, performing-subdomain-enumeration-with-subfinder, tracking-threat-actor-infrastructure]
confidence: low
---

Hunt for DNS-based persistence mechanisms including DNS hijacking, dangling CNAME records, wildcard DNS abuse, and unauthorized zone modifications using passive DNS databases, SecurityTrails API, and DNS audit log analysis.

## Metadata

- **ID:** `hunting-for-dns-based-persistence`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-dns-based-persistence/SKILL.md`
- **Score:** 21.0
- **Edges:** 11

## Related Skills

- [[performing-dns-enumeration-and-zone-transfer]] *(complement)* — Enumerates DNS records, attempts zone transfers, brute-forces subdomains, and maps DNS infrastructure during authorized reconnaissance to identify attack surface, misconfigurations, and information disclosure in target domains.

- [[exploiting-broken-link-hijacking]] *(similar)* — Discover and exploit broken link hijacking vulnerabilities by identifying references to expired domains, decommissioned cloud resources, and dead external services that can be claimed by an attacker.
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.
- [[hunting-for-suspicious-scheduled-tasks]] *(similar)* — Hunt for adversary persistence and execution via Windows scheduled tasks by analyzing task creation events, suspicious task properties, and unusual execution patterns that indicate T1053.005 abuse.
- [[tracking-threat-actor-infrastructure]] *(similar)* — Threat actor infrastructure tracking involves monitoring and mapping adversary-controlled assets including command-and-control (C2) servers, phishing domains, exploit kit hosts, bulletproof hosting, a
- [[analyzing-email-headers-for-phishing-investigation]] *(similar)* — Parse and analyze email headers to trace the origin of phishing emails, verify sender authenticity, and identify spoofing through SPF, DKIM, and DMARC validation.
- [[analyzing-network-covert-channels-in-malware]] *(similar)* — Detect and analyze covert communication channels used by malware including DNS tunneling, ICMP exfiltration, steganographic HTTP, and protocol abuse for C2 and data exfiltration.
- [[hunting-for-data-exfiltration-indicators]] *(similar)* — Hunt for data exfiltration through network traffic analysis, detecting unusual data flows, DNS tunneling, cloud storage uploads, and encrypted channel abuse.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.
- [[performing-subdomain-enumeration-with-subfinder]] *(similar)* — Enumerate subdomains of target domains using ProjectDiscovery's Subfinder passive reconnaissance tool to map the attack surface during security assessments.

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
