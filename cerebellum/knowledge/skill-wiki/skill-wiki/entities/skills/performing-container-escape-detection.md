---
title: performing-container-escape-detection
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-kubernetes-cluster-rbac, detecting-azure-service-principal-abuse, detecting-privilege-escalation-attempts, emulating-cloud-attacks-with-stratus-red-team, escaping-containers-to-host, implementing-container-image-minimal-base-with-distroless, performing-gcp-penetration-testing-with-gcpbucketbrute, performing-graphql-security-assessment, performing-kubernetes-penetration-testing]
confidence: low
---

Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in

## Metadata

- **ID:** `performing-container-escape-detection`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-container-escape-detection/SKILL.md`
- **Score:** 33.0
- **Edges:** 9

## Related Skills

- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[emulating-cloud-attacks-with-stratus-red-team]] *(similar)* — Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.
- [[performing-gcp-penetration-testing-with-gcpbucketbrute]] *(similar)* — Perform GCP security testing using GCPBucketBrute for storage bucket enumeration, gcloud IAM privilege escalation path analysis, and service account permission auditing
- [[performing-graphql-security-assessment]] *(similar)* — Assessing GraphQL API endpoints for introspection leaks, injection attacks, authorization flaws, and denial-of-service vulnerabilities during authorized security tests.
- [[performing-kubernetes-penetration-testing]] *(similar)* — Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools
- [[escaping-containers-to-host]] *(complement)* — Exploit privileged pods, host mounts, runC CVEs, and exposed Docker sockets to break out of a container and reach the underlying host during authorized container-security assessments.
- [[auditing-kubernetes-cluster-rbac]] *(similar)* — Auditing Kubernetes cluster RBAC configurations to identify overly permissive roles, wildcard permissions, dangerous ClusterRoleBindings, service account abuse, and privilege escalation paths using kubectl, rbac-tool, KubiScan, and Kubeaudit.

- [[detecting-privilege-escalation-attempts]] *(similar)* — Detect privilege escalation attempts including token manipulation, UAC bypass, unquoted service paths, kernel exploits, and sudo/doas abuse across Windows and Linux.
- [[implementing-container-image-minimal-base-with-distroless]] *(similar)* — Reduce container attack surface by building application images on Google distroless base images that contain only the application runtime with no shell, package manager, or unnecessary OS utilities.

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
