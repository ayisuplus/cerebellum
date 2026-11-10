---
title: implementing-devsecops-security-scanning
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [building-devsecops-pipeline-with-gitlab-ci, conducting-api-security-testing, detecting-aws-credential-exposure-with-trufflehog, implementing-github-advanced-security-for-code-scanning, implementing-infrastructure-as-code-security-scanning, implementing-secret-scanning-with-gitleaks, implementing-secrets-scanning-in-ci-cd, implementing-semgrep-for-custom-sast-rules, implementing-sigstore-for-software-signing, implementing-vulnerability-sla-breach-alerting, performing-sca-dependency-scanning-with-snyk, performing-web-application-vulnerability-triage, scanning-docker-images-with-trivy]
confidence: medium
---

Integrates Static Application Security Testing (SAST), Dynamic Application Security Testing (DAST), and Software Composition Analysis (SCA) into CI/CD pipelines using open-source tools. Covers Semgrep for SAST, Trivy for SCA and container scanning, OWASP ZAP for DAST, and Gitleaks for secrets detect

## Metadata

- **ID:** `implementing-devsecops-security-scanning`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/implementing-devsecops-security-scanning/SKILL.md`
- **Score:** 57.0
- **Edges:** 13

## Related Skills

- [[implementing-github-advanced-security-for-code-scanning]] *(complement)* — Configure GitHub Advanced Security with CodeQL to perform automated static analysis and vulnerability detection across repositories at enterprise scale.
- [[implementing-secret-scanning-with-gitleaks]] *(complement)* — This skill covers implementing Gitleaks for detecting and preventing hardcoded secrets in git repositories. It addresses configuring pre-commit hooks, CI/CD pipeline integration, custom rule authoring for organization-specific secrets, baseline management for existing repositories, and remediation w
- [[implementing-secrets-scanning-in-ci-cd]] *(complement)* — Integrate gitleaks and trufflehog into CI/CD pipelines to detect leaked secrets before deployment
- [[implementing-semgrep-for-custom-sast-rules]] *(complement)* — Write custom Semgrep SAST rules in YAML to detect application-specific vulnerabilities, enforce coding standards, and integrate into CI/CD pipelines.
- [[scanning-docker-images-with-trivy]] *(complement)* — Trivy is a comprehensive open-source vulnerability scanner by Aqua Security that detects vulnerabilities in OS packages, language-specific dependencies, misconfigurations, secrets, and license violati
- [[building-devsecops-pipeline-with-gitlab-ci]] *(complement)* — Design and implement a comprehensive DevSecOps pipeline in GitLab CI/CD integrating SAST, DAST, container scanning, dependency scanning, and secret detection.
- [[performing-sca-dependency-scanning-with-snyk]] *(complement)* — This skill covers implementing Software Composition Analysis (SCA) using Snyk to detect vulnerable open-source dependencies in CI/CD pipelines. It addresses scanning package manifests and lockfiles, automated fix pull request generation, license compliance checking, continuous monitoring of deployed
- [[conducting-api-security-testing]] *(similar)* — Conducts security testing of REST, GraphQL, and gRPC APIs to identify vulnerabilities in authentication, authorization, rate limiting, input validation, and business logic. The tester uses the OWASP API Security Top 10 as the testing framework, combining Burp Suite interception with Postman collecti
- [[detecting-aws-credential-exposure-with-trufflehog]] *(similar)* — Detecting exposed AWS credentials in source code repositories, CI/CD pipelines, and configuration files using TruffleHog, git-secrets, and AWS-native detection mechanisms to prevent credential theft and unauthorized account access.

- [[implementing-infrastructure-as-code-security-scanning]] *(similar)* — This skill covers implementing automated security scanning for Infrastructure as Code (IaC) templates using tools like Checkov, tfsec, and KICS. It addresses detecting misconfigurations in Terraform, CloudFormation, Kubernetes manifests, and Helm charts before deployment, establishing policy-based g
- [[implementing-sigstore-for-software-signing]] *(similar)* — Implements Sigstore-based software signing and verification using Cosign keyless signing, Rekor transparency log verification, and Fulcio certificate authority integration to establish cryptographic provenance for container images, binaries, and software artifacts. The practitioner configures OIDC-b
- [[implementing-vulnerability-sla-breach-alerting]] *(similar)* — Build automated alerting for vulnerability remediation SLA breaches with severity-based timelines, escalation workflows, and compliance reporting dashboards.
- [[performing-web-application-vulnerability-triage]] *(similar)* — Triage web application vulnerability findings from DAST/SAST scanners using OWASP risk rating methodology to separate true positives from false positives and prioritize remediation.

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
