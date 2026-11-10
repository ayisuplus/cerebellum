---
title: detecting-privilege-escalation-attempts
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [detecting-azure-service-principal-abuse, detecting-dll-sideloading-attacks, detecting-insider-threat-with-ueba, detecting-secure-boot-bypass, detecting-suspicious-powershell-execution, detecting-t1548-abuse-elevation-control-mechanism, escaping-containers-to-host, exploiting-constrained-delegation-abuse, hunting-saas-sso-token-abuse, performing-container-escape-detection, performing-privilege-escalation-on-linux]
confidence: low
---

Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.

## Metadata

- **ID:** `detecting-privilege-escalation-attempts`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-privilege-escalation-attempts/SKILL.md`
- **Score:** 31.0
- **Edges:** 11

## Related Skills

- [[detecting-t1548-abuse-elevation-control-mechanism]] *(complement)* — Detect abuse of elevation control mechanisms including UAC bypass, sudo exploitation, and setuid/setgid manipulation by monitoring registry modifications, process elevation flags, and unusual parent-child process relationships.
- [[performing-privilege-escalation-on-linux]] *(complement)* — Linux privilege escalation involves elevating from a low-privilege user account to root access on a compromised system. Red teams exploit misconfigurations, vulnerable services, kernel exploits, and w
- [[detecting-suspicious-powershell-execution]] *(similar)* — Detect suspicious PowerShell execution patterns including encoded commands, download cradles, AMSI bypass attempts, and constrained language mode evasion.
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[performing-container-escape-detection]] *(similar)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[detecting-azure-service-principal-abuse]] *(complement)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[detecting-dll-sideloading-attacks]] *(similar)* — Detect DLL side-loading attacks where adversaries place malicious DLLs alongside legitimate applications to hijack execution flow for defense evasion.
- [[detecting-insider-threat-with-ueba]] *(similar)* — Implement User and Entity Behavior Analytics using Elasticsearch/OpenSearch to build behavioral baselines, calculate anomaly scores, perform peer group analysis, and detect insider threat indicators such as data exfiltration, privilege abuse, and unauthorized access patterns.
- [[detecting-secure-boot-bypass]] *(similar)* — Detect bootkits such as BlackLotus and Bootkitty and Secure Boot bypass via DBX and binary checks.
- [[escaping-containers-to-host]] *(similar)* — Exploit privileged pods, host mounts, runC CVEs, and exposed Docker sockets to break out of a container and reach the underlying host during authorized container-security assessments.
- [[hunting-saas-sso-token-abuse]] *(similar)* — Detect SSO and OAuth token replay and SaaS lateral movement.

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
