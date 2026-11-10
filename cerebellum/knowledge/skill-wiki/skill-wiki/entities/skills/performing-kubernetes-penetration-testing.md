---
title: performing-kubernetes-penetration-testing
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-kubernetes-cluster-rbac, conducting-cloud-penetration-testing, conducting-internal-network-penetration-test, conducting-network-penetration-test, emulating-cloud-attacks-with-stratus-red-team, escaping-containers-to-host, implementing-continuous-security-validation-with-bas, performing-container-escape-detection, performing-gcp-penetration-testing-with-gcpbucketbrute, performing-graphql-security-assessment, performing-hash-cracking-with-hashcat, performing-web-application-penetration-test]
confidence: medium
---

Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools

## Metadata

- **ID:** `performing-kubernetes-penetration-testing`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/performing-kubernetes-penetration-testing/SKILL.md`
- **Score:** 45.0
- **Edges:** 12

## Related Skills

- [[conducting-cloud-penetration-testing]] *(similar)* — This skill outlines methodologies for performing authorized penetration testing against AWS, Azure, and GCP cloud environments. It covers understanding the shared responsibility model for testing scope, leveraging cloud-specific attack tools like Pacu and ScoutSuite, exploiting IAM misconfigurations
- [[conducting-internal-network-penetration-test]] *(similar)* — Execute an internal network penetration test simulating an insider threat or post-breach attacker to identify lateral movement paths, privilege escalation vectors, and sensitive data exposure within the corporate network.
- [[conducting-network-penetration-test]] *(similar)* — Conducts comprehensive network penetration tests against authorized target environments by performing host discovery, port scanning, service enumeration, vulnerability identification, and controlled exploitation to assess the security posture of network infrastructure. The tester follows PTES method
- [[performing-graphql-security-assessment]] *(similar)* — Assessing GraphQL API endpoints for introspection leaks, injection attacks, authorization flaws, and denial-of-service vulnerabilities during authorized security tests.
- [[performing-web-application-penetration-test]] *(similar)* — Performs systematic security testing of web applications following the OWASP Web Security Testing Guide (WSTG) methodology to identify vulnerabilities in authentication, authorization, input validation, session management, and business logic. The tester uses Burp Suite as the primary interception pr
- [[auditing-kubernetes-cluster-rbac]] *(complement)* — Auditing Kubernetes cluster RBAC configurations to identify overly permissive roles, wildcard permissions, dangerous ClusterRoleBindings, service account abuse, and privilege escalation paths using kubectl, rbac-tool, KubiScan, and Kubeaudit.

- [[emulating-cloud-attacks-with-stratus-red-team]] *(similar)* — Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.
- [[escaping-containers-to-host]] *(similar)* — Exploit privileged pods, host mounts, runC CVEs, and exposed Docker sockets to break out of a container and reach the underlying host during authorized container-security assessments.
- [[implementing-continuous-security-validation-with-bas]] *(similar)* — Deploy Breach and Attack Simulation tools to continuously validate security control effectiveness by safely emulating real-world attack techniques across the kill chain.
- [[performing-container-escape-detection]] *(similar)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[performing-gcp-penetration-testing-with-gcpbucketbrute]] *(similar)* — Perform GCP security testing using GCPBucketBrute for storage bucket enumeration, gcloud IAM privilege escalation path analysis, and service account permission auditing
- [[performing-hash-cracking-with-hashcat]] *(similar)* — Hash cracking is an essential skill for penetration testers and security auditors to evaluate password strength. Hashcat is the world's fastest password recovery tool, supporting over 300 hash types w

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
