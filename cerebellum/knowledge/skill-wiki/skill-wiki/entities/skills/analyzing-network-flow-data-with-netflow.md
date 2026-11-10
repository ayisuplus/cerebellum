---
title: analyzing-network-flow-data-with-netflow
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-cobaltstrike-malleable-c2-profiles, analyzing-network-packets-with-scapy, analyzing-ransomware-network-indicators, analyzing-windows-prefetch-with-python, detecting-beaconing-patterns-with-zeek, detecting-dnp3-protocol-anomalies, detecting-mobile-malware-behavior, detecting-network-anomalies-with-zeek, detecting-network-scanning-with-ids-signatures, detecting-port-scanning-with-fail2ban, detecting-shadow-it-cloud-usage, hunting-for-command-and-control-beaconing, hunting-for-unusual-network-connections, implementing-network-traffic-analysis-with-arkime, implementing-network-traffic-baselining, monitoring-scada-modbus-traffic-anomalies, scanning-network-with-nmap-advanced]
confidence: low
---

Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d

## Metadata

- **ID:** `analyzing-network-flow-data-with-netflow`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-network-flow-data-with-netflow/SKILL.md`
- **Score:** 37.0
- **Edges:** 17

## Related Skills

- [[implementing-network-traffic-baselining]] *(complement)* — Build network traffic baselines from NetFlow/IPFIX data using Python pandas for statistical analysis, z-score anomaly detection, and hourly/daily traffic pattern profiling
- [[analyzing-network-packets-with-scapy]] *(similar)* — Craft, send, sniff, and dissect network packets using Scapy for protocol analysis, network reconnaissance, and traffic anomaly detection in authorized security testing
- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[implementing-network-traffic-analysis-with-arkime]] *(similar)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat
- [[monitoring-scada-modbus-traffic-anomalies]] *(similar)* — Monitors Modbus TCP traffic on SCADA and ICS networks to detect anomalous function code usage, unauthorized register writes, and suspicious communication patterns. The analyst uses deep packet inspection with pymodbus, Scapy, and Zeek to baseline normal PLC/RTU communication behavior, then applies s
- [[analyzing-ransomware-network-indicators]] *(bridge)* — Identify ransomware network indicators including C2 beaconing patterns, TOR exit node connections, data exfiltration flows, and encryption key exchange via Zeek conn.log and NetFlow analysis
- [[analyzing-cobaltstrike-malleable-c2-profiles]] *(similar)* — Parse and analyze Cobalt Strike Malleable C2 profiles using dissect.cobaltstrike and pyMalleableC2 to extract C2 indicators, detect evasion techniques, and generate network detection signatures.
- [[analyzing-windows-prefetch-with-python]] *(similar)* — Parse Windows Prefetch files using the windowsprefetch Python library to reconstruct application execution history, detect renamed or masquerading binaries, and identify suspicious program execution patterns.
- [[detecting-beaconing-patterns-with-zeek]] *(similar)* — Performs statistical analysis of Zeek conn.log connection intervals to detect C2 beaconing patterns. Uses the ZAT library to load Zeek logs into Pandas DataFrames, calculates inter-arrival time standard deviation, and flags periodic connections with low jitter. Use when hunting for command-and-contr
- [[detecting-dnp3-protocol-anomalies]] *(similar)* — Detect anomalies in DNP3 (Distributed Network Protocol 3) communications used in SCADA systems by monitoring for unauthorized control commands, firmware update attempts, protocol violations, and deviations from baseline traffic patterns using deep packet inspection and machine learning approaches.

- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[detecting-network-scanning-with-ids-signatures]] *(similar)* — Detect network reconnaissance and port scanning using Suricata and Snort IDS signatures, threshold-based detection rules, and traffic anomaly analysis to identify Nmap, Masscan, and custom scanning activity.
- [[detecting-port-scanning-with-fail2ban]] *(similar)* — Configures Fail2ban with custom filters and actions to detect port scanning activity, SSH brute force attempts, and network reconnaissance, automatically banning offending IP addresses and alerting security teams to suspicious network probing.

- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[hunting-for-unusual-network-connections]] *(similar)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[scanning-network-with-nmap-advanced]] *(similar)* — Performs advanced network reconnaissance using Nmap's scripting engine, timing controls, evasion techniques, and output parsing to discover hosts, enumerate services, detect vulnerabilities, and fingerprint operating systems across authorized target networks.


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
