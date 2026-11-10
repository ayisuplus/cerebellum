---
title: escaping-containers-to-host
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-privilege-escalation-attempts, exploiting-aws-with-pacu, performing-container-escape-detection, performing-kubernetes-penetration-testing, performing-privilege-escalation-on-linux]
confidence: medium
---

Exploit privileged pods, host mounts, runC CVEs, and exposed Docker sockets to break out of a container and reach the underlying host during authorized container-security assessments.

## Metadata

- **ID:** `escaping-containers-to-host`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/escaping-containers-to-host/SKILL.md`
- **Score:** 45.0
- **Edges:** 5

## Related Skills

- [[performing-container-escape-detection]] *(complement)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[detecting-privilege-escalation-attempts]] *(similar)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[exploiting-aws-with-pacu]] *(similar)* — Use Pacu modules for AWS privilege escalation, persistence, and backdooring.
- [[performing-kubernetes-penetration-testing]] *(similar)* — Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools
- [[performing-privilege-escalation-on-linux]] *(similar)* — Linux privilege escalation involves elevating from a low-privilege user account to root access on a compromised system. Red teams exploit misconfigurations, vulnerable services, kernel exploits, and w

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
