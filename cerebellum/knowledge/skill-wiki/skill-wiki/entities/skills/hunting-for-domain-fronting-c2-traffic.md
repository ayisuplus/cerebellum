---
title: hunting-for-domain-fronting-c2-traffic
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-tls-certificate-transparency-logs, detecting-command-and-control-over-dns, detecting-shadow-it-cloud-usage, hunting-for-cobalt-strike-beacons, hunting-for-command-and-control-beaconing, hunting-for-ntlm-relay-attacks, hunting-for-unusual-network-connections]
confidence: low
---

Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection

## Metadata

- **ID:** `hunting-for-domain-fronting-c2-traffic`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/hunting-for-domain-fronting-c2-traffic/SKILL.md`
- **Score:** 27.0
- **Edges:** 7

## Related Skills

- [[detecting-command-and-control-over-dns]] *(similar)* — Detects command-and-control (C2) communications tunneled through DNS protocol including DNS tunneling tools (Iodine, dnscat2, dns2tcp, Cobalt Strike DNS beacon), domain generation algorithms (DGA), encoded payload delivery via TXT/CNAME records, and DNS beaconing patterns. Covers Shannon entropy ana
- [[detecting-shadow-it-cloud-usage]] *(similar)* — Detect unauthorized SaaS and cloud service usage (shadow IT) by analyzing proxy logs, DNS query logs, and netflow data using Python pandas for traffic pattern analysis and domain classification.
- [[hunting-for-command-and-control-beaconing]] *(similar)* — Detect C2 beaconing patterns in network traffic using frequency analysis, jitter detection, and domain reputation to identify compromised endpoints communicating with adversary infrastructure.
- [[hunting-for-ntlm-relay-attacks]] *(similar)* — Detect NTLM relay attacks by analyzing Windows Event 4624 logon type 3 with NTLMSSP authentication, identifying IP-to-hostname mismatches, Responder traffic signatures, SMB signing status, and suspicious authentication patterns across the domain.
- [[hunting-for-unusual-network-connections]] *(similar)* — Hunt for unusual network connections by analyzing outbound traffic patterns, rare destinations, non-standard ports, and anomalous connection frequencies from endpoints.
- [[auditing-tls-certificate-transparency-logs]] *(similar)* — Monitors Certificate Transparency (CT) logs to detect unauthorized certificate issuance, discover subdomains via CT data, and alert on suspicious certificate activity for owned domains. Uses the crt.sh API and direct CT log querying based on RFC 6962 to build continuous monitoring pipelines that cat
- [[hunting-for-cobalt-strike-beacons]] *(similar)* — Detect Cobalt Strike beacon network activity using default TLS certificate signatures (serial 8BB00EE), JA3/JA3S/JARM fingerprints, HTTP C2 profile pattern matching, beacon jitter analysis, and named pipe detection via Zeek, Suricata, and Python PCAP analysis.

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
