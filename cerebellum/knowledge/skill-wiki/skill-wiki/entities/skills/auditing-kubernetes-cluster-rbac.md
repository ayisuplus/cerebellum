---
title: auditing-kubernetes-cluster-rbac
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-active-directory-acl-abuse, detecting-azure-service-principal-abuse, implementing-rbac-hardening-for-kubernetes, performing-container-escape-detection, performing-gcp-penetration-testing-with-gcpbucketbrute, performing-kubernetes-penetration-testing, scanning-kubernetes-manifests-with-kubesec]
confidence: medium
---

Auditing Kubernetes cluster RBAC configurations to identify overly permissive roles, wildcard permissions, dangerous ClusterRoleBindings, service account abuse, and privilege escalation paths using kubectl, rbac-tool, KubiScan, and Kubeaudit.

## Metadata

- **ID:** `auditing-kubernetes-cluster-rbac`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/auditing-kubernetes-cluster-rbac/SKILL.md`
- **Score:** 48.0
- **Edges:** 7

## Related Skills

- [[performing-kubernetes-penetration-testing]] *(complement)* — Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools
- [[analyzing-active-directory-acl-abuse]] *(similar)* — Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[performing-container-escape-detection]] *(similar)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[performing-gcp-penetration-testing-with-gcpbucketbrute]] *(similar)* — Perform GCP security testing using GCPBucketBrute for storage bucket enumeration, gcloud IAM privilege escalation path analysis, and service account permission auditing
- [[implementing-rbac-hardening-for-kubernetes]] *(bridge)* — Harden Kubernetes Role-Based Access Control by implementing least-privilege policies, auditing role bindings, eliminating cluster-admin sprawl, and integrating external identity providers.
- [[scanning-kubernetes-manifests-with-kubesec]] *(bridge)* — Perform security risk analysis on Kubernetes resource manifests using Kubesec to identify misconfigurations, privilege escalation risks, and deviations from security best practices.

## See Also

- [[abusing-dpapi-for-credential-access]] — Anthropic-Cybersecurity-Skills
- [[abusing-shadow-credentials-for-privesc]] — Anthropic-Cybersecurity-Skills
- [[achieving-cmmc-level-2-compliance]] — Anthropic-Cybersecurity-Skills
- [[acquiring-disk-image-with-dd-and-dcfldd]] — Anthropic-Cybersecurity-Skills
- [[analyzing-android-malware-with-apktool]] — Anthropic-Cybersecurity-Skills
- [[analyzing-api-gateway-access-logs]] — Anthropic-Cybersecurity-Skills
- [[analyzing-apt-group-with-mitre-navigator]] — Anthropic-Cybersecurity-Skills
- [[analyzing-azure-activity-logs-for-threats]] — Anthropic-Cybersecurity-Skills
- [[analyzing-bootkit-and-rootkit-samples]] — Anthropic-Cybersecurity-Skills
- [[analyzing-campaign-attribution-evidence]] — Anthropic-Cybersecurity-Skills
