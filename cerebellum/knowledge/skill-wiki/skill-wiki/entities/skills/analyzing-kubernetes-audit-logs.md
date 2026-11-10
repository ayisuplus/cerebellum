---
title: analyzing-kubernetes-audit-logs
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-azure-activity-logs-for-threats, analyzing-cloud-storage-access-patterns, analyzing-linux-audit-logs-for-intrusion, analyzing-linux-system-artifacts, analyzing-persistence-mechanisms-in-linux, auditing-tls-certificate-transparency-logs, detecting-privilege-escalation-in-kubernetes-pods, detecting-service-account-abuse, performing-cloud-native-forensics-with-falco, securing-kubernetes-on-cloud]
confidence: low
---

Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S

## Metadata

- **ID:** `analyzing-kubernetes-audit-logs`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-kubernetes-audit-logs/SKILL.md`
- **Score:** 33.0
- **Edges:** 10

## Related Skills

- [[analyzing-linux-audit-logs-for-intrusion]] *(similar)* — Uses the Linux Audit framework (auditd) with ausearch and aureport utilities to detect intrusion attempts, unauthorized access, privilege escalation, and suspicious system activity. Covers audit rule configuration, log querying, timeline reconstruction, and integration with SIEM platforms. Activates
- [[analyzing-linux-system-artifacts]] *(similar)* — Examine Linux system artifacts including auth logs, cron jobs, shell history, and system configuration to uncover evidence of compromise or unauthorized activity.
- [[detecting-privilege-escalation-in-kubernetes-pods]] *(similar)* — Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[performing-cloud-native-forensics-with-falco]] *(similar)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
- [[analyzing-azure-activity-logs-for-threats]] *(similar)* — Queries Azure Monitor activity logs and sign-in logs via azure-monitor-query to detect suspicious administrative operations, impossible travel, privilege escalation, and resource modifications. Builds KQL queries for threat hunting in Azure environments. Use when investigating suspicious Azure tenan
- [[analyzing-cloud-storage-access-patterns]] *(similar)* — Detect abnormal access patterns in AWS S3, GCS, and Azure Blob Storage by analyzing CloudTrail Data Events, GCS audit logs, and Azure Storage Analytics. Identifies after-hours bulk downloads, access from new IP addresses, unusual API calls (GetObject spikes), and potential data exfiltration using st
- [[analyzing-persistence-mechanisms-in-linux]] *(similar)* — Detect and analyze Linux persistence mechanisms including crontab entries, systemd service units, LD_PRELOAD hijacking, bashrc modifications, and authorized_keys backdoors using auditd and file integrity monitoring
- [[auditing-tls-certificate-transparency-logs]] *(similar)* — Monitors Certificate Transparency (CT) logs to detect unauthorized certificate issuance, discover subdomains via CT data, and alert on suspicious certificate activity for owned domains. Uses the crt.sh API and direct CT log querying based on RFC 6962 to build continuous monitoring pipelines that cat
- [[securing-kubernetes-on-cloud]] *(similar)* — This skill covers hardening managed Kubernetes clusters on EKS, AKS, and GKE by implementing Pod Security Standards, network policies, workload identity, RBAC scoping, image admission controls, and runtime security monitoring. It addresses cloud-specific security features including IRSA for EKS, Wor

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-active-directory-acl-abuse]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
