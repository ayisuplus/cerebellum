---
title: emulating-cloud-attacks-with-stratus-red-team
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [conducting-cloud-penetration-testing, deploying-cloud-deception-with-decoy-resources, detecting-compromised-cloud-credentials, detecting-serverless-function-injection, enumerating-cloud-with-cloudfox, hunting-for-living-off-the-cloud-techniques, implementing-cloud-waf-rules, implementing-continuous-security-validation-with-bas, implementing-ddos-mitigation-with-cloudflare, performing-cloud-asset-inventory-with-cartography, performing-container-escape-detection, performing-kubernetes-penetration-testing, performing-purple-team-exercise]
confidence: medium
---

Detonate granular AWS, Azure, GCP, and Kubernetes attack techniques to validate detections with Stratus Red Team.

## Metadata

- **ID:** `emulating-cloud-attacks-with-stratus-red-team`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/emulating-cloud-attacks-with-stratus-red-team/SKILL.md`
- **Score:** 42.0
- **Edges:** 13

## Related Skills

- [[conducting-cloud-penetration-testing]] *(similar)* — This skill outlines methodologies for performing authorized penetration testing against AWS, Azure, and GCP cloud environments. It covers understanding the shared responsibility model for testing scope, leveraging cloud-specific attack tools like Pacu and ScoutSuite, exploiting IAM misconfigurations
- [[enumerating-cloud-with-cloudfox]] *(similar)* — Map AWS and Azure attack paths and find exploitable misconfigurations with CloudFox.
- [[hunting-for-living-off-the-cloud-techniques]] *(similar)* — Hunt for adversary abuse of legitimate cloud services for C2, data staging, and exfiltration including abuse of Azure, AWS, GCP services, and SaaS platforms.
- [[implementing-continuous-security-validation-with-bas]] *(similar)* — Deploy Breach and Attack Simulation tools to continuously validate security control effectiveness by safely emulating real-world attack techniques across the kill chain.
- [[performing-kubernetes-penetration-testing]] *(similar)* — Kubernetes penetration testing systematically evaluates cluster security by simulating attacker techniques against the API server, kubelet, etcd, pods, RBAC, network policies, and secrets. Using tools
- [[deploying-cloud-deception-with-decoy-resources]] *(similar)* — Deploy cloud-native deception across AWS, Azure, and GCP using decoy (honey) resources whose only purpose is to generate a high-fidelity alert the instant an attacker touches them: canary IAM access keys, permission-less decoy users/roles/service principals, honey object-storage buckets, and decoy s
- [[detecting-compromised-cloud-credentials]] *(similar)* — Detecting compromised cloud credentials across AWS, Azure, and GCP by analyzing anomalous API activity, impossible travel patterns, unauthorized resource provisioning, and credential abuse indicators using GuardDuty, Defender for Identity, and SCC Event Threat Detection.

- [[detecting-serverless-function-injection]] *(similar)* — Detects and prevents code injection attacks targeting serverless functions (AWS Lambda, Azure Functions, Google Cloud Functions) through event source poisoning, malicious layer injection, runtime command execution, and IAM privilege escalation via function modification. The analyst combines static a
- [[implementing-cloud-waf-rules]] *(similar)* — This skill covers deploying and tuning Web Application Firewall rules on AWS WAF, Azure WAF, and Cloudflare to protect cloud-hosted applications against OWASP Top 10 attacks. It details configuring managed rule sets, creating custom rules for business logic protection, implementing rate limiting, de
- [[implementing-ddos-mitigation-with-cloudflare]] *(similar)* — Configure Cloudflare DDoS protection with managed rulesets, rate limiting, WAF rules, Bot Management, and origin protection to mitigate volumetric, protocol, and application-layer attacks.
- [[performing-cloud-asset-inventory-with-cartography]] *(similar)* — Perform comprehensive cloud asset inventory and relationship mapping using Cartography to build a Neo4j security graph of infrastructure assets, IAM permissions, and attack paths across AWS, GCP, and Azure.
- [[performing-container-escape-detection]] *(similar)* — Detects container escape attempts by analyzing namespace configurations, privileged container checks, dangerous capability assignments, and host path mounts using the kubernetes Python client. Identifies CVE-2022-0492 style escapes via cgroup abuse. Use when auditing container security posture or in
- [[performing-purple-team-exercise]] *(similar)* — Performs purple team exercises by coordinating red team adversary emulation with blue team detection validation using MITRE ATT&CK-mapped attack scenarios, real-time detection testing, and collaborative gap remediation. Use when SOC teams need to validate detection capabilities, improve analyst skil

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
