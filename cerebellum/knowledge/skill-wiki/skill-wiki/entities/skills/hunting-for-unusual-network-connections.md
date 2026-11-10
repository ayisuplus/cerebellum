---
title: hunting-for-unusual-network-connections
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-network-flow-data-with-netflow, detecting-lateral-movement-with-zeek, detecting-network-anomalies-with-zeek, detecting-network-scanning-with-ids-signatures, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing, hunting-for-data-staging-before-exfiltration, hunting-for-domain-fronting-c2-traffic, hunting-for-ntlm-relay-attacks, hunting-for-spearphishing-indicators, hunting-for-unusual-service-installations, implementing-network-traffic-analysis-with-arkime, monitoring-scada-modbus-traffic-anomalies]
confidence: low
---

Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.

## Metadata

- **ID:** `hunting-for-unusual-network-connections`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-unusual-network-connections/SKILL.md`
- **Score:** 31.0
- **Edges:** 13

## Related Skills

- [[analyzing-network-flow-data-with-netflow]] *(similar)* — Parse NetFlow v9 and IPFIX records to detect volumetric anomalies, port scanning, data exfiltration, and C2 beaconing patterns. Uses the Python netflow library to decode flow records, builds traffic baselines, and applies statistical analysis to identify flows with abnormal byte counts, connection d
- [[detecting-lateral-movement-with-zeek]] *(similar)* — Detect lateral movement in network traffic using Zeek (formerly Bro) log analysis. Parses conn.log, smb_mapping.log, smb_files.log, dce_rpc.log, kerberos.log, and ntlm.log to identify SMB file transfers, NTLM account spray activity, remote service execution, and anomalous internal connections.

- [[detecting-network-anomalies-with-zeek]] *(similar)* — Deploys and configures Zeek (formerly Bro) network security monitor to passively analyze network traffic, generate structured logs, detect anomalous behavior, and create custom detection scripts for threat hunting and incident response.

- [[detecting-network-scanning-with-ids-signatures]] *(similar)* — Detect network reconnaissance and port scanning using Suricata and Snort IDS signatures, threshold-based detection rules, and traffic anomaly analysis to identify Nmap, Masscan, and custom scanning activity.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-command-and-control-beaconing]] *(complement)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.
- [[hunting-for-data-staging-before-exfiltration]] *(similar)* — Detect data staging activity before exfiltration by monitoring for archive creation with 7-Zip/RAR, unusual temp folder access, large file consolidation, and staging directory patterns via EDR and process telemetry
- [[hunting-for-domain-fronting-c2-traffic]] *(similar)* — Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection
- [[hunting-for-spearphishing-indicators]] *(similar)* — Hunt for spearphishing campaign indicators across email logs, endpoint telemetry, and network data to detect targeted email attacks.
- [[hunting-for-unusual-service-installations]] *(similar)* — Detect suspicious Windows service installations (MITRE ATT&CK T1543.003) by parsing System event logs for Event ID 7045, analyzing service binary paths, and identifying indicators of persistence mechanisms.
- [[implementing-network-traffic-analysis-with-arkime]] *(similar)* — Deploy and query Arkime (formerly Moloch) for full packet capture network traffic analysis. Uses the Arkime API v3 to search sessions, download PCAPs, analyze connection patterns, detect beaconing behavior, and identify suspicious network flows. Monitors DNS queries, HTTP traffic, and TLS certificat
- [[monitoring-scada-modbus-traffic-anomalies]] *(similar)* — Monitors Modbus TCP traffic on SCADA and ICS networks to detect anomalous function code usage, unauthorized register writes, and suspicious communication patterns. The analyst uses deep packet inspection with pymodbus, Scapy, and Zeek to baseline normal PLC/RTU communication behavior, then applies s

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
