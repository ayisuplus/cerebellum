---
title: detecting-privilege-escalation-in-kubernetes-pods
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [analyzing-kubernetes-audit-logs, detecting-aws-cloudtrail-anomalies, detecting-aws-iam-privilege-escalation, detecting-container-drift-at-runtime, detecting-container-escape-attempts, detecting-service-account-abuse, detecting-suspicious-oauth-application-consent, implementing-security-monitoring-with-datadog, performing-cloud-native-forensics-with-falco, scanning-docker-images-with-trivy, securing-kubernetes-on-cloud]
confidence: medium
---

Detect and prevent privilege escalation in Kubernetes pods by monitoring security contexts, capabilities, and syscall patterns with Falco and OPA policies.

## Metadata

- **ID:** `detecting-privilege-escalation-in-kubernetes-pods`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/detecting-privilege-escalation-in-kubernetes-pods/SKILL.md`
- **Score:** 45.0
- **Edges:** 11

## Related Skills

- [[performing-cloud-native-forensics-with-falco]] *(complement)* — Uses Falco YAML rules for runtime threat detection in containers and Kubernetes, monitoring syscalls for shell spawns, file tampering, network anomalies, and privilege escalation. Manages Falco rules via the Falco gRPC API and parses Falco alert output. Use when building container runtime security o
- [[detecting-aws-cloudtrail-anomalies]] *(similar)* — Detect unusual API call patterns in AWS CloudTrail logs using boto3, statistical baselining, and behavioral analysis to identify credential compromise, privilege escalation, and unauthorized resource access.
- [[detecting-service-account-abuse]] *(similar)* — Detect abuse of service accounts through anomalous interactive logons, privilege escalation, lateral movement, and unauthorized access patterns.
- [[implementing-security-monitoring-with-datadog]] *(similar)* — Implements security monitoring using Datadog Cloud SIEM, Cloud Security Management (CSM), and Workload Protection to detect threats, enforce compliance, and respond to security events across cloud and hybrid infrastructure. Covers Agent deployment, log source ingestion, detection rule creation, secu
- [[securing-kubernetes-on-cloud]] *(similar)* — This skill covers hardening managed Kubernetes clusters on EKS, AKS, and GKE by implementing Pod Security Standards, network policies, workload identity, RBAC scoping, image admission controls, and runtime security monitoring. It addresses cloud-specific security features including IRSA for EKS, Wor
- [[analyzing-kubernetes-audit-logs]] *(similar)* — Parses Kubernetes API server audit logs (JSON lines) to detect exec-into-pod, secret access, RBAC modifications, privileged pod creation, and anonymous API access. Builds threat detection rules from audit event patterns. Use when investigating Kubernetes cluster compromise or building k8s-specific S
- [[detecting-aws-iam-privilege-escalation]] *(similar)* — Detect AWS IAM privilege escalation paths using boto3 and Cloudsplaining policy analysis to identify overly permissive policies, dangerous permission combinations, and least-privilege violations
- [[detecting-container-drift-at-runtime]] *(similar)* — Detect unauthorized modifications to running containers by monitoring for binary execution drift, file system changes, and configuration deviations from the original container image.
- [[detecting-container-escape-attempts]] *(similar)* — Container escape is a critical attack technique where an adversary breaks out of container isolation to access the host system or other containers. Detection involves monitoring for escape indicators
- [[detecting-suspicious-oauth-application-consent]] *(similar)* — Detect risky OAuth application consent grants in Azure AD / Microsoft Entra ID using Microsoft Graph API, audit logs, and permission analysis to identify illicit consent grant attacks.
- [[scanning-docker-images-with-trivy]] *(similar)* — Trivy is a comprehensive open-source vulnerability scanner by Aqua Security that detects vulnerabilities in OS packages, language-specific dependencies, misconfigurations, secrets, and license violati

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
