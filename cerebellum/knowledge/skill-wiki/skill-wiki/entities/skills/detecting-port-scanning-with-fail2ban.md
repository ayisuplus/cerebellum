---
title: detecting-port-scanning-with-fail2ban
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-linux-audit-logs-for-intrusion, analyzing-network-flow-data-with-netflow, analyzing-network-packets-with-scapy, configuring-suricata-for-network-monitoring, detecting-arp-poisoning-in-network-traffic, detecting-network-anomalies-with-zeek, detecting-network-scanning-with-ids-signatures, detecting-rdp-brute-force-attacks, implementing-file-integrity-monitoring-with-aide, performing-wireless-security-assessment-with-kismet, scanning-network-with-nmap-advanced]
confidence: medium
---

Configures Fail2ban with custom filters and actions to detect port scanning activity, SSH brute force attempts, and network reconnaissance, automatically banning offending IP addresses and alerting security teams to suspicious network probing.

## Metadata

- **ID:** `detecting-port-scanning-with-fail2ban`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-port-scanning-with-fail2ban/SKILL.md`
- **Score:** 51.0
- **Edges:** 11

## Related Skills

- [[analyzing-linux-audit-logs-for-intrusion]] *(similar)* — Uses the Linux Audit framework (auditd) with ausearch and aureport utilities to detect intrusion attempts, unauthorized access, privilege escalation, and suspicious system activity. Covers audit rule configuration, log querying, timeline reconstruction, and integration with SIEM platforms. Activates
- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[analyzing-network-packets-with-scapy]] *(similar)* — Craft, send, sniff, and dissect network packets using Scapy for protocol analysis, network reconnaissance, and traffic anomaly detection in authorized security testing
- [[detecting-rdp-brute-force-attacks]] *(similar)* — Detect RDP brute force attacks by analyzing Windows Security Event Logs for failed authentication patterns (Event ID 4625), successful logons after failures (Event ID 4624), NLA failures, and source IP frequency analysis.
- [[scanning-network-with-nmap-advanced]] *(similar)* — Performs advanced network reconnaissance using Nmap's scripting engine, timing controls, evasion techniques, and output parsing to discover hosts, enumerate services, detect vulnerabilities, and fingerprint operating systems across authorized target networks.

- [[detecting-network-scanning-with-ids-signatures]] *(complement)* — Detect network reconnaissance and port scanning using Suricata and Snort IDS signatures, threshold-based detection rules, and traffic anomaly analysis to identify Nmap, Masscan, and custom scanning activity.
- [[configuring-suricata-for-network-monitoring]] *(similar)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[detecting-arp-poisoning-in-network-traffic]] *(similar)* — Detect and prevent ARP spoofing attacks using ARPWatch, Dynamic ARP Inspection, Wireshark analysis, and custom monitoring scripts to protect against man-in-the-middle interception.
- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[implementing-file-integrity-monitoring-with-aide]] *(similar)* — Configure AIDE (Advanced Intrusion Detection Environment) for file integrity monitoring including baseline creation, scheduled integrity checks, change detection, and alerting
- [[performing-wireless-security-assessment-with-kismet]] *(similar)* — Conduct wireless network security assessments using Kismet to detect rogue access points, hidden SSIDs, weak encryption, and unauthorized clients through passive RF monitoring.

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
