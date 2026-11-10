---
title: auditing-tls-certificate-transparency-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, building-adversary-infrastructure-tracking-system, detecting-shadow-api-endpoints, hunting-for-domain-fronting-c2-traffic, performing-paste-site-monitoring-for-credentials, performing-ssl-certificate-lifecycle-management]
confidence: medium
---

Monitors Certificate Transparency (CT) logs to detect unauthorized certificate issuance, discover subdomains via CT data, and alert on suspicious certificate activity for owned domains. Uses the crt.sh API and direct CT log querying based on RFC 6962 to build continuous monitoring pipelines that cat

## Metadata

- **ID:** `auditing-tls-certificate-transparency-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-tls-certificate-transparency-logs/SKILL.md`
- **Score:** 55.0
- **Edges:** 6

## Related Skills

- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[building-adversary-infrastructure-tracking-system]] *(similar)* — Build an automated system to track adversary infrastructure using passive DNS, certificate transparency, WHOIS data, and IP enrichment to map and monitor threat actor command-and-control networks.
- [[detecting-shadow-api-endpoints]] *(similar)* — Discover and inventory shadow API endpoints that operate outside documented specifications using traffic analysis, code scanning, and API discovery platforms.
- [[hunting-for-domain-fronting-c2-traffic]] *(similar)* — Detect domain fronting C2 traffic by analyzing SNI vs HTTP Host header mismatches in proxy logs and TLS certificate discrepancies using pyOpenSSL for certificate inspection
- [[performing-ssl-certificate-lifecycle-management]] *(similar)* — SSL/TLS certificate lifecycle management encompasses the full process of requesting, issuing, deploying, monitoring, renewing, and revoking X.509 certificates. Poor certificate management is a leading
- [[performing-paste-site-monitoring-for-credentials]] *(similar)* — Monitor paste sites like Pastebin and GitHub Gists for leaked credentials, API keys, and sensitive data dumps using automated scraping and keyword matching to detect breaches early.

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
