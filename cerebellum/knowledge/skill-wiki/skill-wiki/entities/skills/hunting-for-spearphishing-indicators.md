---
title: hunting-for-spearphishing-indicators
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-email-account-compromise, detecting-entra-offensive-tools-in-graph-logs, detecting-evasion-techniques-in-endpoint-logs, detecting-ransomware-precursors-in-network, hunting-credential-stuffing-attacks, hunting-evtx-with-chainsaw, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing, hunting-for-ntlm-relay-attacks, hunting-for-unusual-network-connections, investigating-insider-threat-indicators, performing-threat-hunting-with-elastic-siem]
confidence: low
---

Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.

## Metadata

- **ID:** `hunting-for-spearphishing-indicators`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-spearphishing-indicators/SKILL.md`
- **Score:** 31.0
- **Edges:** 12

## Related Skills

- [[detecting-evasion-techniques-in-endpoint-logs]] *(similar)* — Detects defense evasion techniques used by adversaries in endpoint logs including log tampering, timestomping, process injection, and security tool disabling. Use when investigating suspicious endpoint behavior, building detection rules for evasion tactics, or conducting threat hunting for stealthy 
- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[hunting-for-unusual-network-connections]] *(similar)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[investigating-insider-threat-indicators]] *(similar)* — Investigates insider threat indicators including data exfiltration attempts, unauthorized access patterns, policy violations, and pre-departure behaviors using SIEM analytics, DLP alerts, and HR data correlation. Use when SOC teams receive insider threat referrals from HR, detect anomalous data move
- [[performing-threat-hunting-with-elastic-siem]] *(similar)* — Performs proactive threat hunting in Elastic Security SIEM using KQL/EQL queries, detection rules, and Timeline investigation to identify threats that evade automated detection. Use when SOC teams need to hunt for specific ATT&CK techniques, investigate anomalous behaviors, or validate detection cov
- [[detecting-email-account-compromise]] *(similar)* — Detect compromised O365 and Google Workspace email accounts by analyzing inbox rule creation, suspicious sign-in locations, mail forwarding rules, and unusual API access patterns via Microsoft Graph and audit logs.
- [[detecting-entra-offensive-tools-in-graph-logs]] *(similar)* — Hunt AADGraphActivityLogs and MicrosoftGraphActivityLogs in Microsoft Sentinel/Log Analytics for fingerprints of offensive Entra ID tools such as ROADtools, AADInternals, and AzureHound.
- [[detecting-ransomware-precursors-in-network]] *(similar)* — Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio
- [[hunting-credential-stuffing-attacks]] *(similar)* — Detects credential stuffing attacks by analyzing authentication logs for login velocity anomalies, ASN diversity, password spray patterns, and geographic distribution of failed logins. Uses statistical analysis on Splunk or raw log data. Use when investigating account takeover campaigns or building 
- [[hunting-evtx-with-chainsaw]] *(similar)* — Perform rapid Sigma and keyword hunting across Windows event logs with Chainsaw.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.

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
