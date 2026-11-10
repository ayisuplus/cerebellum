---
title: detecting-network-anomalies-with-zeek
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-network-flow-data-with-netflow, analyzing-network-packets-with-scapy, configuring-suricata-for-network-monitoring, deploying-honeytokens-and-canarytokens, deploying-osquery-for-endpoint-monitoring, detecting-arp-poisoning-in-network-traffic, detecting-beaconing-patterns-with-zeek, detecting-lateral-movement-with-zeek, detecting-mobile-malware-behavior, detecting-network-scanning-with-ids-signatures, detecting-port-scanning-with-fail2ban, detecting-ransomware-precursors-in-network, hunting-for-unusual-network-connections, implementing-network-traffic-analysis-with-arkime, implementing-network-traffic-baselining, monitoring-scada-modbus-traffic-anomalies, operationalizing-misp-threat-feeds, performing-user-behavior-analytics, performing-wireless-security-assessment-with-kismet, scanning-network-with-nmap-advanced]
confidence: medium
---

Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

## Metadata

- **ID:** `detecting-network-anomalies-with-zeek`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-network-anomalies-with-zeek/SKILL.md`
- **Score:** 48.0
- **Edges:** 20

## Related Skills

- [[detecting-ransomware-precursors-in-network]] *(complement)* — Detects early-stage ransomware indicators in network traffic before encryption begins, including initial access broker activity, command-and-control beaconing, credential harvesting, reconnaissance scanning, and staging behavior. Uses network detection tools (Zeek, Suricata, Arkime), SIEM correlatio
- [[implementing-network-traffic-analysis-with-arkime]] *(complement)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat
- [[analyzing-network-packets-with-scapy]] *(similar)* — Craft, send, sniff, and dissect network packets using Scapy for protocol analysis, network reconnaissance, and traffic anomaly detection in authorized security testing
- [[detecting-network-scanning-with-ids-signatures]] *(similar)* — Detect network reconnaissance and port scanning using Suricata and Snort IDS signatures, threshold-based detection rules, and traffic anomaly analysis to identify Nmap, Masscan, and custom scanning activity.
- [[detecting-port-scanning-with-fail2ban]] *(similar)* — Configures Fail2ban with custom filters and actions to detect port scanning activity, SSH brute force attempts, and network reconnaissance, automatically banning offending IP addresses and alerting security teams to suspicious network probing.

- [[configuring-suricata-for-network-monitoring]] *(complement)* — Deploys and configures Suricata IDS/IPS with Emerging Threats rulesets, EVE JSON logging, and custom rules for real-time network traffic inspection, threat detection, and integration with SIEM platforms for centralized security monitoring.

- [[detecting-lateral-movement-with-zeek]] *(complement)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[deploying-honeytokens-and-canarytokens]] *(similar)* — Plant canarytokens and honey credentials and alert on breach.
- [[deploying-osquery-for-endpoint-monitoring]] *(similar)* — Deploys and configures osquery for real-time endpoint monitoring using SQL-based queries to inspect running processes, open ports, installed software, and system configuration. Use when building visibility into endpoint state, threat hunting across fleet, or implementing compliance monitoring. Activ
- [[detecting-arp-poisoning-in-network-traffic]] *(similar)* — Detect and prevent ARP spoofing attacks using ARPWatch, Dynamic ARP Inspection, Wireshark analysis, and custom monitoring scripts to protect against man-in-the-middle interception.
- [[detecting-beaconing-patterns-with-zeek]] *(similar)* — Performs statistical analysis of Zeek conn.log connection intervals to detect C2 beaconing patterns. Uses the ZAT library to load Zeek logs into Pandas DataFrames, calculates inter-arrival time standard deviation, and flags periodic connections with low jitter. Use when hunting for command-and-contr
- [[detecting-mobile-malware-behavior]] *(similar)* — Detects and analyzes malicious behavior in mobile applications through behavioral analysis, permission abuse detection, network traffic monitoring, and dynamic instrumentation. Use when analyzing suspicious mobile applications for data exfiltration, command-and-control communication, credential stea
- [[hunting-for-unusual-network-connections]] *(similar)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[implementing-network-traffic-baselining]] *(similar)* — Build network traffic baselines from NetFlow/IPFIX data using Python pandas for statistical analysis, z-score anomaly detection, and hourly/daily traffic pattern profiling
- [[monitoring-scada-modbus-traffic-anomalies]] *(similar)* — Monitors Modbus TCP traffic on SCADA and ICS networks to detect anomalous function code usage, unauthorized register writes, and suspicious communication patterns. The analyst uses deep packet inspection with pymodbus, Scapy, and Zeek to baseline normal PLC/RTU communication behavior, then applies s
- [[operationalizing-misp-threat-feeds]] *(similar)* — Run MISP, curate feeds, and auto-generate detections for Wazuh, Sigma, and Suricata.
- [[performing-user-behavior-analytics]] *(similar)* — Performs User and Entity Behavior Analytics (UEBA) to detect anomalous user activities including impossible travel, unusual access patterns, privilege abuse, and insider threats using SIEM-based behavioral baselines and statistical analysis. Use when SOC teams need to identify compromised accounts o
- [[performing-wireless-security-assessment-with-kismet]] *(similar)* — Conduct wireless network security assessments using Kismet to detect rogue access points, hidden SSIDs, weak encryption, and unauthorized clients through passive RF monitoring.
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
