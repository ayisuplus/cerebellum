---
title: workflow-patterns
created: 2026-07-04
type: concept
tags: [workflow, pattern]
confidence: high
---

# Workflow Patterns

Derived from the skill-graph edge relationships and pipeline workflows.

## Summary

This reference catalogs 340+ complementary skill pairs, 65 cross-domain bridge connections, and 10 reusable workflow patterns from the skill-graph. It serves two purposes:

- **Workflow selection** — find the right skill sequence for a given task type
- **Training data** — structured mappings of `task → workflow → outcome` for fine-tuning

### Document Structure

| Section | Content | Use Case |
|---|---|---|
| [Complementary Skills](#complementary-skills) | 340+ bidirectional pairs (`↔`) of skills that work together | Find what to combine for a task |
| [Bridge Connections](#bridge-connections) | 65 directional pairs (`→`) crossing domain boundaries | Understand cross-domain skill flow |
| [Workflows](#workflows) | 10 pre-assembled full skill sequences | Reuse proven patterns directly |

### Workflow Quick Reference

| Pattern | Best For | Key Differentiator |
|---|---|---|
| `test-q` | Recording Q-table entries during development | Core build loop — no codebase recon |
| `verify-test` | Validating Q-table recordings | Verification step in build pipeline |
| `vf` | Final pre-ship validation | Full pipeline with security scanning |
| `final-smoke` | Quick pre-ship smoke test | Skips recon, has 4-stage breakdown |
| `optimize-dailyglider` | Full-cycle project optimization | Ends-to-end: recon → plan → build → review → ship |
| `wf-optimize-dailyglider` | Bilingual (CN/EN) project optimization | Same as above with bilingual spec |
| `add-reasonix-tui-agent-to` | Adding a new agent to Orca | Multi-agent integration pattern |
| `build-a-saas-website-with` | Full-stack SaaS build | Adds design-mobile-apps + security |
| `afac-doc-parsing` | Large document parsing | Academic-paper skill for research docs |
| `hello-world-test` | Prototypes and experiments | Browser devtools + prompt leak testing |

### Training Data Format

Each workflow entry can be used directly as training data:

```yaml
task: "<pipeline description>"
workflow:
  - skill-1  # Brief description of what it does
  - skill-2
  - ...
outcome: "<expected result>"
```

The `Bridge Connections` section adds cross-domain awareness, showing how skills transfer between domains (e.g., `sec-incident` → `sec-pentest`).

## Complementary Skills

These skills are designed to work together — one feeds into or enhances the other.

- [[PaperSpine-paper-spine]] ↔ [[paper-spine-build]]
- [[academic-paper]] ↔ [[academic-pipeline]]
- [[academic-paper]] ↔ [[deep-research]]
- [[accessibility]] ↔ [[web-design-guidelines]]
- [[aliyun-cli]] ↔ [[deploy-to-vercel]]
- [[analyzing-api-gateway-access-logs]] ↔ [[analyzing-web-server-logs-for-intrusion]]
- [[analyzing-azure-activity-logs-for-threats]] ↔ [[detecting-azure-lateral-movement]]
- [[analyzing-bootkit-and-rootkit-samples]] ↔ [[performing-firmware-malware-analysis]]
- [[analyzing-cloud-storage-access-patterns]] ↔ [[detecting-aws-cloudtrail-anomalies]]
- [[analyzing-cloud-storage-access-patterns]] ↔ [[detecting-s3-data-exfiltration-attempts]]
- [[analyzing-command-and-control-communication]] ↔ [[analyzing-network-traffic-of-malware]]
- [[analyzing-disk-image-with-autopsy]] ↔ [[performing-endpoint-forensics-investigation]]
- [[analyzing-disk-image-with-autopsy]] ↔ [[performing-file-carving-with-foremost]]
- [[analyzing-golang-malware-with-ghidra]] ↔ [[reverse-engineering-malware-with-ghidra]]
- [[analyzing-golang-malware-with-ghidra]] ↔ [[reverse-engineering-rust-malware]]
- [[analyzing-heap-spray-exploitation]] ↔ [[analyzing-memory-dumps-with-volatility]]
- [[analyzing-indicators-of-compromise]] ↔ [[analyzing-threat-intelligence-feeds]]
- [[analyzing-indicators-of-compromise]] ↔ [[automating-ioc-enrichment]]
- [[analyzing-indicators-of-compromise]] ↔ [[collecting-indicators-of-compromise]]
- [[analyzing-indicators-of-compromise]] ↔ [[correlating-threat-campaigns]]
- [[analyzing-indicators-of-compromise]] ↔ [[performing-malware-ioc-extraction]]
- [[analyzing-linux-audit-logs-for-intrusion]] ↔ [[analyzing-linux-system-artifacts]]
- [[analyzing-linux-audit-logs-for-intrusion]] ↔ [[analyzing-persistence-mechanisms-in-linux]]
- [[analyzing-linux-system-artifacts]] ↔ [[analyzing-persistence-mechanisms-in-linux]]
- [[analyzing-macro-malware-in-office-documents]] ↔ [[analyzing-pdf-malware-with-pdfid]]
- [[analyzing-malware-behavior-with-cuckoo-sandbox]] ↔ [[analyzing-malware-sandbox-evasion-techniques]]
- [[analyzing-malware-behavior-with-cuckoo-sandbox]] ↔ [[analyzing-network-traffic-of-malware]]
- [[analyzing-malware-behavior-with-cuckoo-sandbox]] ↔ [[performing-dynamic-analysis-with-any-run]]
- [[analyzing-malware-behavior-with-cuckoo-sandbox]] ↔ [[performing-malware-ioc-extraction]]
- [[analyzing-malware-persistence-with-autoruns]] ↔ [[performing-malware-persistence-investigation]]
- [[analyzing-memory-dumps-with-volatility]] ↔ [[extracting-memory-artifacts-with-rekall]]
- [[analyzing-network-covert-channels-in-malware]] ↔ [[hunting-for-data-exfiltration-indicators]]
- [[analyzing-network-flow-data-with-netflow]] ↔ [[implementing-network-traffic-baselining]]
- [[analyzing-network-packets-with-scapy]] ↔ [[detecting-arp-poisoning-in-network-traffic]]
- [[analyzing-network-traffic-of-malware]] ↔ [[analyzing-ransomware-network-indicators]]
- [[analyzing-powershell-empire-artifacts]] ↔ [[analyzing-powershell-script-block-logging]]
- [[analyzing-powershell-script-block-logging]] ↔ [[analyzing-windows-prefetch-with-python]]
- [[analyzing-security-logs-with-splunk]] ↔ [[triaging-security-alerts-in-splunk]]
- [[analyzing-threat-intelligence-feeds]] ↔ [[automating-ioc-enrichment]]
- [[analyzing-threat-intelligence-feeds]] ↔ [[building-threat-intelligence-feed-integration]]
- [[analyzing-threat-intelligence-feeds]] ↔ [[correlating-threat-campaigns]]
- [[analyzing-threat-intelligence-feeds]] ↔ [[processing-stix-taxii-feeds]]
- [[analyzing-threat-landscape-with-misp]] ↔ [[collecting-threat-intelligence-with-misp]]
- [[analyzing-uefi-bootkit-persistence]] ↔ [[detecting-secure-boot-bypass]]
- [[analyzing-web-server-logs-for-intrusion]] ↔ [[detecting-sql-injection-via-waf-logs]]
- [[analyzing-windows-amcache-artifacts]] ↔ [[analyzing-windows-lnk-files-for-artifacts]]
- [[android-architecture-clean]] ↔ [[android-testing-unit]]
- [[attacking-entra-id-with-roadtools]] ↔ [[auditing-entra-id-with-aadinternals]]
- [[auditing-aws-s3-bucket-permissions]] ↔ [[auditing-terraform-infrastructure-for-security]]
- [[auditing-aws-s3-bucket-permissions]] ↔ [[remediating-s3-bucket-misconfiguration]]
- [[auditing-entra-id-with-aadinternals]] ↔ [[detecting-azure-service-principal-abuse]]
- [[auditing-kubernetes-cluster-rbac]] ↔ [[performing-kubernetes-penetration-testing]]
- [[automating-ioc-enrichment]] ↔ [[building-ioc-defanging-and-sharing-pipeline]]
- [[automating-ioc-enrichment]] ↔ [[building-ioc-enrichment-pipeline-with-opencti]]
- [[automating-ioc-enrichment]] ↔ [[building-threat-intelligence-feed-integration]]
- [[automating-ioc-enrichment]] ↔ [[implementing-soar-automation-with-phantom]]
- [[benchmarking-kubernetes-with-kube-bench]] ↔ [[hardening-linux-endpoint-with-cis-benchmark]]
- [[building-automated-malware-submission-pipeline]] ↔ [[building-ioc-defanging-and-sharing-pipeline]]
- [[building-c2-infrastructure-with-sliver-framework]] ↔ [[building-c2-redirector-infrastructure]]
- [[building-c2-infrastructure-with-sliver-framework]] ↔ [[building-red-team-c2-infrastructure-with-havoc]]
- [[building-detection-rule-with-splunk-spl]] ↔ [[building-detection-rules-with-sigma]]
- [[building-detection-rule-with-splunk-spl]] ↔ [[implementing-siem-use-cases-for-detection]]
- [[building-detection-rules-with-sigma]] ↔ [[implementing-siem-use-cases-for-detection]]
- [[building-devsecops-pipeline-with-gitlab-ci]] ↔ [[implementing-devsecops-security-scanning]]
- [[building-devsecops-pipeline-with-gitlab-ci]] ↔ [[implementing-secrets-scanning-in-ci-cd]]
- [[building-devsecops-pipeline-with-gitlab-ci]] ↔ [[implementing-semgrep-for-custom-sast-rules]]
- [[building-incident-response-playbook]] ↔ [[building-soc-playbook-for-ransomware]]
- [[building-incident-response-playbook]] ↔ [[implementing-ot-incident-response-playbook]]
- [[building-ioc-defanging-and-sharing-pipeline]] ↔ [[building-ioc-enrichment-pipeline-with-opencti]]
- [[building-ioc-defanging-and-sharing-pipeline]] ↔ [[building-threat-intelligence-feed-integration]]
- [[building-ioc-enrichment-pipeline-with-opencti]] ↔ [[building-threat-intelligence-feed-integration]]
- [[building-malware-incident-communication-template]] ↔ [[building-soc-escalation-matrix]]
- [[building-native-ui]] ↔ [[react-native-dev]]
- [[building-threat-intelligence-enrichment-in-splunk]] ↔ [[building-threat-intelligence-feed-integration]]
- [[building-threat-intelligence-feed-integration]] ↔ [[building-threat-intelligence-platform]]
- [[building-threat-intelligence-feed-integration]] ↔ [[implementing-stix-taxii-feed-integration]]
- [[building-threat-intelligence-feed-integration]] ↔ [[processing-stix-taxii-feeds]]
- [[building-threat-intelligence-platform]] ↔ [[collecting-threat-intelligence-with-misp]]
- [[building-threat-intelligence-platform]] ↔ [[evaluating-threat-intelligence-platforms]]
- [[clerk]] ↔ [[clerk-setup]]
- [[clerk-custom-ui]] ↔ [[clerk-swift]]
- [[clerk-custom-ui]] ↔ [[clerk-testing]]
- [[clerk-nextjs-patterns]] ↔ [[clerk-vue-patterns]]
- [[code-review-and-quality]] ↔ [[requesting-code-review]]
- [[coercing-authentication-with-coercer-petitpotam]] ↔ [[relaying-ntlm-for-adcs-esc8]]
- [[collecting-indicators-of-compromise]] ↔ [[collecting-threat-intelligence-with-misp]]
- [[collecting-open-source-intelligence]] ↔ [[monitoring-darkweb-sources]]
- [[collecting-open-source-intelligence]] ↔ [[performing-open-source-intelligence-gathering]]
- [[conducting-cloud-incident-response]] ↔ [[conducting-malware-incident-response]]
- [[conducting-cloud-incident-response]] ↔ [[performing-cloud-forensics-investigation]]
- [[conducting-cloud-incident-response]] ↔ [[performing-cloud-incident-containment-procedures]]
- [[conducting-domain-persistence-with-dcsync]] ↔ [[performing-active-directory-compromise-investigation]]
- [[conducting-domain-persistence-with-dcsync]] ↔ [[performing-active-directory-forest-trust-attack]]
- [[conducting-external-reconnaissance-with-osint]] ↔ [[performing-open-source-intelligence-gathering]]
- [[conducting-full-scope-red-team-engagement]] ↔ [[executing-red-team-exercise]]
- [[conducting-internal-network-penetration-test]] ↔ [[conducting-network-penetration-test]]
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] ↔ [[executing-active-directory-attack-simulation]]
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] ↔ [[exploiting-active-directory-with-bloodhound]]
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] ↔ [[mapping-attack-paths-with-bloodhound-ce]]
- [[conducting-internal-reconnaissance-with-bloodhound-ce]] ↔ [[performing-active-directory-vulnerability-assessment]]
- [[conducting-malware-incident-response]] ↔ [[conducting-phishing-incident-response]]
- [[conducting-mobile-app-penetration-test]] ↔ [[conducting-network-penetration-test]]
- [[conducting-mobile-app-penetration-test]] ↔ [[performing-web-application-penetration-test]]
- [[conducting-network-penetration-test]] ↔ [[conducting-wireless-network-penetration-test]]
- [[conducting-phishing-incident-response]] ↔ [[investigating-phishing-email-incident]]
- [[conducting-spearphishing-simulation-campaign]] ↔ [[executing-phishing-simulation-campaign]]
- [[configuring-aws-verified-access-for-ztna]] ↔ [[deploying-cloudflare-access-for-zero-trust]]
- [[configuring-host-based-intrusion-detection]] ↔ [[implementing-file-integrity-monitoring-with-aide]]
- [[configuring-hsm-for-key-storage]] ↔ [[performing-hardware-security-module-integration]]
- [[configuring-identity-aware-proxy-with-google-iap]] ↔ [[implementing-zero-trust-with-beyondcorp]]
- [[configuring-suricata-for-network-monitoring]] ↔ [[detecting-network-anomalies-with-zeek]]
- [[configuring-suricata-for-network-monitoring]] ↔ [[detecting-network-scanning-with-ids-signatures]]
- [[configuring-windows-defender-advanced-settings]] ↔ [[implementing-anti-ransomware-group-policy]]
- [[csharp-async]] ↔ [[csharp-xunit]]
- [[csharp-docs]] ↔ [[dotnet-best-practices]]
- [[csharp-docs]] ↔ [[java-docs]]
- [[detecting-ai-model-prompt-injection-attacks]] ↔ [[detecting-indirect-prompt-injection]]
- [[detecting-anomalies-in-industrial-control-systems]] ↔ [[detecting-dnp3-protocol-anomalies]]
- [[detecting-anomalies-in-industrial-control-systems]] ↔ [[detecting-modbus-protocol-anomalies]]
- [[detecting-anomalies-in-industrial-control-systems]] ↔ [[detecting-stuxnet-style-attacks]]
- [[detecting-anomalous-authentication-patterns]] ↔ [[detecting-aws-cloudtrail-anomalies]]
- [[detecting-anomalous-authentication-patterns]] ↔ [[detecting-service-account-abuse]]
- [[detecting-anomalous-authentication-patterns]] ↔ [[hunting-credential-stuffing-attacks]]
- [[detecting-anomalous-authentication-patterns]] ↔ [[performing-user-behavior-analytics]]
- [[detecting-attacks-on-historian-servers]] ↔ [[detecting-attacks-on-scada-systems]]
- [[detecting-aws-cloudtrail-anomalies]] ↔ [[detecting-aws-iam-privilege-escalation]]
- [[detecting-aws-cloudtrail-anomalies]] ↔ [[detecting-s3-data-exfiltration-attempts]]
- [[detecting-aws-cloudtrail-anomalies]] ↔ [[detecting-service-account-abuse]]
- [[detecting-aws-cloudtrail-anomalies]] ↔ [[implementing-cloud-trail-log-analysis]]
- [[detecting-aws-credential-exposure-with-trufflehog]] ↔ [[implementing-secrets-scanning-in-ci-cd]]
- [[detecting-azure-lateral-movement]] ↔ [[detecting-email-account-compromise]]
- [[detecting-azure-lateral-movement]] ↔ [[detecting-entra-offensive-tools-in-graph-logs]]
- [[detecting-azure-lateral-movement]] ↔ [[detecting-service-account-abuse]]
- [[detecting-azure-lateral-movement]] ↔ [[detecting-suspicious-oauth-application-consent]]
- [[detecting-azure-service-principal-abuse]] ↔ [[detecting-compromised-cloud-credentials]]
- [[detecting-azure-service-principal-abuse]] ↔ [[detecting-oauth-token-theft]]
- [[detecting-azure-service-principal-abuse]] ↔ [[detecting-privilege-escalation-attempts]]
- [[detecting-beaconing-patterns-with-zeek]] ↔ [[hunting-for-command-and-control-beaconing]]
- [[detecting-business-email-compromise]] ↔ [[detecting-business-email-compromise-with-ai]]
- [[detecting-cloud-threats-with-guardduty]] ↔ [[detecting-cryptomining-in-cloud]]
- [[detecting-cloud-threats-with-guardduty]] ↔ [[performing-cloud-native-threat-hunting-with-aws-detective]]
- [[detecting-command-and-control-over-dns]] ↔ [[hunting-for-command-and-control-beaconing]]
- [[detecting-credential-dumping-techniques]] ↔ [[detecting-pass-the-hash-attacks]]
- [[detecting-dnp3-protocol-anomalies]] ↔ [[detecting-modbus-command-injection-attacks]]
- [[detecting-dnp3-protocol-anomalies]] ↔ [[monitoring-scada-modbus-traffic-anomalies]]
- [[detecting-email-account-compromise]] ↔ [[detecting-service-account-abuse]]
- [[detecting-email-account-compromise]] ↔ [[detecting-suspicious-oauth-application-consent]]
- [[detecting-fileless-malware-techniques]] ↔ [[detecting-process-injection-techniques]]
- [[detecting-golden-ticket-forgery]] ↔ [[detecting-kerberoasting-attacks]]
- [[detecting-indirect-prompt-injection]] ↔ [[testing-prompt-injection-in-rag-pipelines]]
- [[detecting-insider-data-exfiltration-via-dlp]] ↔ [[investigating-insider-threat-indicators]]
- [[detecting-insider-threat-behaviors]] ↔ [[detecting-insider-threat-with-ueba]]
- [[detecting-kerberoasting-attacks]] ↔ [[detecting-pass-the-hash-attacks]]
- [[detecting-kerberoasting-attacks]] ↔ [[detecting-service-account-abuse]]
- [[detecting-lateral-movement-with-zeek]] ↔ [[detecting-network-anomalies-with-zeek]]
- [[detecting-living-off-the-land-attacks]] ↔ [[detecting-mimikatz-execution-patterns]]
- [[detecting-malicious-scheduled-tasks-with-sysmon]] ↔ [[detecting-wmi-persistence]]
- [[detecting-mimikatz-execution-patterns]] ↔ [[detecting-pass-the-hash-attacks]]
- [[detecting-modbus-command-injection-attacks]] ↔ [[detecting-modbus-protocol-anomalies]]
- [[detecting-modbus-command-injection-attacks]] ↔ [[monitoring-scada-modbus-traffic-anomalies]]
- [[detecting-modbus-protocol-anomalies]] ↔ [[monitoring-scada-modbus-traffic-anomalies]]
- [[detecting-network-anomalies-with-zeek]] ↔ [[detecting-ransomware-precursors-in-network]]
- [[detecting-network-anomalies-with-zeek]] ↔ [[implementing-network-traffic-analysis-with-arkime]]
- [[detecting-network-scanning-with-ids-signatures]] ↔ [[detecting-port-scanning-with-fail2ban]]
- [[detecting-pass-the-hash-attacks]] ↔ [[detecting-rdp-brute-force-attacks]]
- [[detecting-pass-the-hash-attacks]] ↔ [[hunting-for-ntlm-relay-attacks]]
- [[detecting-privilege-escalation-attempts]] ↔ [[detecting-t1548-abuse-elevation-control-mechanism]]
- [[detecting-privilege-escalation-attempts]] ↔ [[performing-privilege-escalation-on-linux]]
- [[detecting-privilege-escalation-in-kubernetes-pods]] ↔ [[performing-cloud-native-forensics-with-falco]]
- [[detecting-process-injection-techniques]] ↔ [[detecting-rootkit-activity]]
- [[detecting-rdp-brute-force-attacks]] ↔ [[hunting-for-ntlm-relay-attacks]]
- [[detecting-s3-data-exfiltration-attempts]] ↔ [[implementing-cloud-trail-log-analysis]]
- [[detecting-supply-chain-attacks-in-ci-cd]] ↔ [[securing-github-actions-workflows]]
- [[detecting-wmi-persistence]] ↔ [[hunting-for-registry-run-key-persistence]]
- [[elevenlabs-music]] ↔ [[elevenlabs-tts]]
- [[elon-musk-perspective]] ↔ [[feynman-perspective]]
- [[elon-musk-perspective]] ↔ [[munger-perspective]]
- [[escaping-containers-to-host]] ↔ [[performing-container-escape-detection]]
- [[executing-active-directory-attack-simulation]] ↔ [[exploiting-active-directory-with-bloodhound]]
- [[executing-active-directory-attack-simulation]] ↔ [[performing-active-directory-compromise-investigation]]
- [[executing-active-directory-attack-simulation]] ↔ [[performing-active-directory-vulnerability-assessment]]
- [[executing-red-team-exercise]] ↔ [[performing-purple-team-exercise]]
- [[exploiting-active-directory-with-bloodhound]] ↔ [[mapping-attack-paths-with-bloodhound-ce]]
- [[exploiting-active-directory-with-bloodhound]] ↔ [[performing-active-directory-vulnerability-assessment]]
- [[exploiting-adcs-with-certipy]] ↔ [[exploiting-constrained-delegation-abuse]]
- [[exploiting-adcs-with-certipy]] ↔ [[relaying-ntlm-for-adcs-esc8]]
- [[exploiting-api-injection-vulnerabilities]] ↔ [[exploiting-idor-vulnerabilities]]
- [[exploiting-api-injection-vulnerabilities]] ↔ [[exploiting-mass-assignment-in-rest-apis]]
- [[exploiting-api-injection-vulnerabilities]] ↔ [[testing-for-host-header-injection]]
- [[exploiting-api-injection-vulnerabilities]] ↔ [[testing-for-xml-injection-vulnerabilities]]
- [[exploiting-api-injection-vulnerabilities]] ↔ [[testing-for-xss-vulnerabilities]]
- [[exploiting-constrained-delegation-abuse]] ↔ [[exploiting-nopac-cve-2021-42278-42287]]
- [[exploiting-constrained-delegation-abuse]] ↔ [[performing-active-directory-forest-trust-attack]]
- [[exploiting-deeplink-vulnerabilities]] ↔ [[exploiting-insecure-data-storage-in-mobile]]
- [[exploiting-deeplink-vulnerabilities]] ↔ [[testing-android-intents-for-vulnerabilities]]
- [[exploiting-idor-vulnerabilities]] ↔ [[exploiting-insecure-deserialization]]
- [[exploiting-idor-vulnerabilities]] ↔ [[exploiting-mass-assignment-in-rest-apis]]
- [[exploiting-idor-vulnerabilities]] ↔ [[exploiting-oauth-misconfiguration]]
- [[exploiting-insecure-deserialization]] ↔ [[exploiting-template-injection-vulnerabilities]]
- [[exploiting-jwt-algorithm-confusion-attack]] ↔ [[performing-jwt-none-algorithm-attack]]
- [[exploiting-jwt-algorithm-confusion-attack]] ↔ [[testing-jwt-token-security]]
- [[exploiting-ms17-010-eternalblue-vulnerability]] ↔ [[exploiting-smb-vulnerabilities-with-metasploit]]
- [[exploiting-nopac-cve-2021-42278-42287]] ↔ [[exploiting-zerologon-vulnerability-cve-2020-1472]]
- [[exploiting-nosql-injection-vulnerabilities]] ↔ [[exploiting-sql-injection-with-sqlmap]]
- [[exploiting-oauth-misconfiguration]] ↔ [[testing-cors-misconfiguration]]
- [[exploiting-oauth-misconfiguration]] ↔ [[testing-for-open-redirect-vulnerabilities]]
- [[exploiting-oauth-misconfiguration]] ↔ [[testing-oauth2-implementation-flaws]]
- [[exploiting-smb-vulnerabilities-with-metasploit]] ↔ [[exploiting-sql-injection-with-sqlmap]]
- [[exploiting-smb-vulnerabilities-with-metasploit]] ↔ [[exploiting-vulnerabilities-with-metasploit-framework]]
- [[exploiting-sql-injection-with-sqlmap]] ↔ [[performing-second-order-sql-injection]]
- [[extracting-windows-event-logs-artifacts]] ↔ [[hunting-evtx-with-chainsaw]]
- [[feynman-perspective]] ↔ [[munger-perspective]]
- [[fleet-hunting-with-velociraptor]] ↔ [[implementing-velociraptor-for-ir-collection]]
- [[flutter-dev]] ↔ [[flutter-expert]]
- [[golang-patterns]] ↔ [[python-patterns]]
- [[gsap-core]] ↔ [[gsap-plugins]]
- [[hardening-docker-containers-for-production]] ↔ [[hardening-docker-daemon-configuration]]
- [[hardening-docker-containers-for-production]] ↔ [[hardening-linux-endpoint-with-cis-benchmark]]
- [[hardening-docker-containers-for-production]] ↔ [[performing-container-image-hardening]]
- [[hunting-for-cobalt-strike-beacons]] ↔ [[hunting-for-command-and-control-beaconing]]
- [[hunting-for-command-and-control-beaconing]] ↔ [[hunting-for-unusual-network-connections]]
- [[hunting-for-dns-based-persistence]] ↔ [[performing-dns-enumeration-and-zone-transfer]]
- [[hunting-for-registry-run-key-persistence]] ↔ [[hunting-for-startup-folder-persistence]]
- [[hunting-for-registry-run-key-persistence]] ↔ [[hunting-for-unusual-service-installations]]
- [[implementing-alert-fatigue-reduction]] ↔ [[performing-false-positive-reduction-in-siem]]
- [[implementing-anti-ransomware-group-policy]] ↔ [[implementing-application-whitelisting-with-applocker]]
- [[implementing-api-security-testing-with-42crunch]] ↔ [[testing-api-security-with-owasp-top-10]]
- [[implementing-aws-iam-permission-boundaries]] ↔ [[securing-aws-lambda-execution-roles]]
- [[implementing-cisa-zero-trust-maturity-model]] ↔ [[implementing-identity-verification-for-zero-trust]]
- [[implementing-cloud-dlp-for-data-protection]] ↔ [[implementing-data-loss-prevention-with-microsoft-purview]]
- [[implementing-cloud-trail-log-analysis]] ↔ [[implementing-security-monitoring-with-datadog]]
- [[implementing-cloud-trail-log-analysis]] ↔ [[performing-cloud-log-forensics-with-athena]]
- [[implementing-cloud-waf-rules]] ↔ [[implementing-ddos-mitigation-with-cloudflare]]
- [[implementing-conditional-access-policies-azure-ad]] ↔ [[implementing-zero-trust-for-saas-applications]]
- [[implementing-conduit-security-for-ot-remote-access]] ↔ [[securing-remote-access-to-ot-environment]]
- [[implementing-devsecops-security-scanning]] ↔ [[implementing-github-advanced-security-for-code-scanning]]
- [[implementing-devsecops-security-scanning]] ↔ [[implementing-secret-scanning-with-gitleaks]]
- [[implementing-devsecops-security-scanning]] ↔ [[implementing-secrets-scanning-in-ci-cd]]
- [[implementing-devsecops-security-scanning]] ↔ [[implementing-semgrep-for-custom-sast-rules]]
- [[implementing-devsecops-security-scanning]] ↔ [[performing-sca-dependency-scanning-with-snyk]]
- [[implementing-devsecops-security-scanning]] ↔ [[scanning-docker-images-with-trivy]]
- [[implementing-epss-score-for-vulnerability-prioritization]] ↔ [[performing-cve-prioritization-with-kev-catalog]]
- [[implementing-gdpr-data-subject-access-request]] ↔ [[performing-privacy-impact-assessment]]
- [[implementing-github-advanced-security-for-code-scanning]] ↔ [[implementing-semgrep-for-custom-sast-rules]]
- [[implementing-google-workspace-phishing-protection]] ↔ [[implementing-proofpoint-email-security-gateway]]
- [[implementing-identity-verification-for-zero-trust]] ↔ [[implementing-zero-trust-for-saas-applications]]
- [[implementing-immutable-backup-with-restic]] ↔ [[implementing-ransomware-backup-strategy]]
- [[implementing-infrastructure-as-code-security-scanning]] ↔ [[implementing-secret-scanning-with-gitleaks]]
- [[implementing-log-forwarding-with-fluentd]] ↔ [[implementing-syslog-centralization-with-rsyslog]]
- [[implementing-privileged-access-workstation]] ↔ [[implementing-zero-standing-privilege-with-cyberark]]
- [[implementing-saml-sso-with-okta]] ↔ [[implementing-scim-provisioning-with-okta]]
- [[implementing-secret-scanning-with-gitleaks]] ↔ [[implementing-secrets-scanning-in-ci-cd]]
- [[implementing-secrets-scanning-in-ci-cd]] ↔ [[implementing-semgrep-for-custom-sast-rules]]
- [[implementing-security-information-sharing-with-stix2]] ↔ [[implementing-stix-taxii-feed-integration]]
- [[implementing-siem-use-case-tuning]] ↔ [[implementing-siem-use-cases-for-detection]]
- [[implementing-siem-use-case-tuning]] ↔ [[performing-false-positive-reduction-in-siem]]
- [[implementing-siem-use-cases-for-detection]] ↔ [[mapping-mitre-attack-techniques]]
- [[implementing-siem-use-cases-for-detection]] ↔ [[performing-threat-hunting-with-elastic-siem]]
- [[implementing-soar-automation-with-phantom]] ↔ [[implementing-soar-playbook-for-phishing]]
- [[implementing-soar-automation-with-phantom]] ↔ [[implementing-soar-playbook-with-palo-alto-xsoar]]
- [[implementing-soar-playbook-for-phishing]] ↔ [[implementing-soar-playbook-with-palo-alto-xsoar]]
- [[implementing-stix-taxii-feed-integration]] ↔ [[processing-stix-taxii-feeds]]
- [[intercepting-mobile-traffic-with-burpsuite]] ↔ [[performing-mobile-app-certificate-pinning-bypass]]
- [[kotlin-tooling-agp9-migration]] ↔ [[kotlin-tooling-cocoapods-spm-migration]]
- [[machine-learning]] ↔ [[scikit-learn]]
- [[minimax-music-gen]] ↔ [[minimax-music-playlist]]
- [[nature-academic-search]] ↔ [[nature-citation]]
- [[nature-paper2ppt]] ↔ [[nature-reader]]
- [[nature-polishing]] ↔ [[nature-writing]]
- [[nature-response]] ↔ [[nature-reviewer]]
- [[obsidian-markdown]] ↔ [[obsidian-vault]]
- [[pandas-data-analysis]] ↔ [[pandas-pro]]
- [[paper-spine-build]] ↔ [[paper-spine-latex]]
- [[paper-spine-build]] ↔ [[paper-spine-research]]
- [[paper-spine-build]] ↔ [[paper-spine-rewrite]]
- [[paper-spine-research]] ↔ [[paper-spine-rewrite]]
- [[performing-access-review-and-certification]] ↔ [[performing-privileged-account-access-review]]
- [[performing-active-directory-compromise-investigation]] ↔ [[performing-active-directory-forest-trust-attack]]
- [[performing-active-directory-compromise-investigation]] ↔ [[performing-active-directory-vulnerability-assessment]]
- [[performing-active-directory-forest-trust-attack]] ↔ [[performing-active-directory-vulnerability-assessment]]
- [[performing-adversary-in-the-middle-phishing-detection]] ↔ [[performing-initial-access-with-evilginx3]]
- [[performing-agentless-vulnerability-scanning]] ↔ [[performing-authenticated-scan-with-openvas]]
- [[performing-alert-triage-with-elastic-siem]] ↔ [[performing-false-positive-reduction-in-siem]]
- [[performing-alert-triage-with-elastic-siem]] ↔ [[performing-threat-hunting-with-elastic-siem]]
- [[performing-alert-triage-with-elastic-siem]] ↔ [[triaging-security-alerts-in-splunk]]
- [[performing-android-app-static-analysis-with-mobsf]] ↔ [[performing-ios-app-security-assessment]]
- [[performing-arp-spoofing-attack-simulation]] ↔ [[performing-bandwidth-throttling-attack-simulation]]
- [[performing-arp-spoofing-attack-simulation]] ↔ [[performing-ssl-stripping-attack]]
- [[performing-arp-spoofing-attack-simulation]] ↔ [[performing-vlan-hopping-attack]]
- [[performing-bluetooth-security-assessment]] ↔ [[performing-iot-security-assessment]]
- [[performing-clickjacking-attack-test]] ↔ [[performing-csrf-attack-simulation]]
- [[performing-cloud-forensics-investigation]] ↔ [[performing-cloud-storage-forensic-acquisition]]
- [[performing-content-security-policy-bypass]] ↔ [[performing-web-application-firewall-bypass]]
- [[performing-content-security-policy-bypass]] ↔ [[testing-cors-misconfiguration]]
- [[performing-csrf-attack-simulation]] ↔ [[performing-web-cache-poisoning-attack]]
- [[performing-csrf-attack-simulation]] ↔ [[testing-cors-misconfiguration]]
- [[performing-csrf-attack-simulation]] ↔ [[testing-for-xss-vulnerabilities]]
- [[performing-dns-enumeration-and-zone-transfer]] ↔ [[performing-subdomain-enumeration-with-subfinder]]
- [[performing-file-carving-with-foremost]] ↔ [[recovering-deleted-files-with-photorec]]
- [[performing-graphql-depth-limit-attack]] ↔ [[performing-graphql-security-assessment]]
- [[performing-http-parameter-pollution-attack]] ↔ [[performing-web-application-firewall-bypass]]
- [[performing-malware-hash-enrichment-with-virustotal]] ↔ [[performing-malware-ioc-extraction]]
- [[performing-malware-hash-enrichment-with-virustotal]] ↔ [[performing-malware-triage-with-yara]]
- [[performing-malware-triage-with-yara]] ↔ [[performing-threat-hunting-with-yara-rules]]
- [[performing-malware-triage-with-yara]] ↔ [[performing-yara-rule-development-for-detection]]
- [[performing-oil-gas-cybersecurity-assessment]] ↔ [[performing-ot-network-security-assessment]]
- [[performing-oil-gas-cybersecurity-assessment]] ↔ [[performing-power-grid-cybersecurity-assessment]]
- [[performing-ot-vulnerability-assessment-with-claroty]] ↔ [[performing-ot-vulnerability-scanning-safely]]
- [[performing-ransomware-tabletop-exercise]] ↔ [[performing-soc-tabletop-exercise]]
- [[performing-soap-web-service-security-testing]] ↔ [[testing-for-xml-injection-vulnerabilities]]
- [[performing-threat-hunting-with-yara-rules]] ↔ [[performing-yara-rule-development-for-detection]]
- [[performing-web-application-penetration-test]] ↔ [[testing-for-xss-vulnerabilities-with-burpsuite]]
- [[performing-web-cache-deception-attack]] ↔ [[performing-web-cache-poisoning-attack]]
- [[performing-web-cache-poisoning-attack]] ↔ [[testing-for-host-header-injection]]
- [[pptx]] ↔ [[xlsx]]
- [[prisma-cli]] ↔ [[prisma-client-api]]
- [[python-patterns]] ↔ [[python-testing-patterns]]
- [[rails-code-review]] ↔ [[rails-security-review]]
- [[rails-code-review]] ↔ [[ruby-on-rails-best-practices]]
- [[receiving-code-review]] ↔ [[requesting-code-review]]
- [[reference-core]] ↔ [[reference-signal-forms]]
- [[reverse-engineering-dotnet-malware-with-dnspy]] ↔ [[reverse-engineering-malware-with-ghidra]]
- [[reverse-engineering-malware-with-ghidra]] ↔ [[reverse-engineering-ransomware-encryption-routine]]
- [[reverse-engineering-malware-with-ghidra]] ↔ [[reverse-engineering-rust-malware]]
- [[securing-aws-iam-permissions]] ↔ [[securing-serverless-functions]]
- [[tailwind-css-patterns]] ↔ [[tailwind-design-system]]
- [[testing-api-for-broken-object-level-authorization]] ↔ [[testing-api-for-mass-assignment-vulnerability]]
- [[testing-cors-misconfiguration]] ↔ [[testing-for-open-redirect-vulnerabilities]]
- [[testing-for-email-header-injection]] ↔ [[testing-for-host-header-injection]]
- [[testing-for-email-header-injection]] ↔ [[testing-for-xss-vulnerabilities]]
- [[testing-for-host-header-injection]] ↔ [[testing-for-open-redirect-vulnerabilities]]
- [[testing-for-host-header-injection]] ↔ [[testing-for-xml-injection-vulnerabilities]]
- [[testing-for-host-header-injection]] ↔ [[testing-for-xss-vulnerabilities]]
- [[testing-for-open-redirect-vulnerabilities]] ↔ [[testing-for-xss-vulnerabilities]]
- [[testing-for-open-redirect-vulnerabilities]] ↔ [[testing-for-xss-vulnerabilities-with-burpsuite]]
- [[testing-for-open-redirect-vulnerabilities]] ↔ [[testing-oauth2-implementation-flaws]]
- [[testing-for-xml-injection-vulnerabilities]] ↔ [[testing-for-xss-vulnerabilities]]
- [[testing-for-xss-vulnerabilities]] ↔ [[testing-for-xss-vulnerabilities-with-burpsuite]]
- [[testing-jwt-token-security]] ↔ [[testing-oauth2-implementation-flaws]]
- [[threejs-geometry]] ↔ [[threejs-shaders]]
- [[ui-ux-pro-max-skill-design-system]] ↔ [[ui-ux-pro-max-skill-slides]]

## Bridge Connections

These skills bridge between different domains or attack phases.

- [[analyzing-android-malware-with-apktool]] → [[performing-dynamic-analysis-of-android-app]] *(bridge-sec-incident-coding)*
- [[analyzing-apt-group-with-mitre-navigator]] → [[analyzing-threat-actor-ttps-with-mitre-attack]] *(bridge-sec-incident-sec-pentest)*
- [[analyzing-command-and-control-communication]] → [[analyzing-network-covert-channels-in-malware]] *(bridge-sec-incident-sec-pentest)*
- [[analyzing-network-traffic-of-malware]] → [[analyzing-network-covert-channels-in-malware]] *(bridge-sec-incident-sec-pentest)*
- [[analyzing-ransomware-network-indicators]] → [[analyzing-network-flow-data-with-netflow]] *(bridge-sec-incident-sec-monitoring)*
- [[analyzing-slack-space-and-file-system-artifacts]] → [[analyzing-mft-for-deleted-file-recovery]] *(bridge-creative-sec-incident)*
- [[analyzing-windows-registry-for-artifacts]] → [[analyzing-usb-device-connection-history]] *(bridge-creative-sec-monitoring)*
- [[analyzing-windows-registry-for-artifacts]] → [[analyzing-windows-amcache-artifacts]] *(bridge-creative-sec-incident)*
- [[analyzing-windows-registry-for-artifacts]] → [[analyzing-windows-lnk-files-for-artifacts]] *(bridge-creative-sec-incident)*
- [[analyzing-windows-registry-for-artifacts]] → [[analyzing-windows-shellbag-artifacts]] *(bridge-creative-sec-monitoring)*
- [[android-coroutines-flow]] → [[android-kotlin-core]] *(bridge-meta-data)*
- [[auditing-azure-active-directory-configuration]] → [[auditing-entra-id-with-aadinternals]] *(bridge-sec-audit-sec-pentest)*
- [[auditing-azure-active-directory-configuration]] → [[detecting-azure-lateral-movement]] *(bridge-sec-audit-sec-monitoring)*
- [[auditing-foundry-smart-contract-security]] → [[analyzing-ethereum-smart-contract-vulnerabilities]] *(bridge-sec-audit-sec-monitoring)*
- [[building-incident-timeline-with-timesketch]] → [[building-super-timelines-with-plaso]] *(bridge-sec-incident-sec-monitoring)*
- [[building-ioc-enrichment-pipeline-with-opencti]] → [[modeling-threats-with-opencti]] *(bridge-sec-incident-data)*
- [[building-patch-tuesday-response-process]] → [[implementing-patch-management-workflow]] *(bridge-sec-incident-devops)*
- [[building-threat-actor-profile-from-osint]] → [[analyzing-threat-actor-ttps-with-mitre-attack]] *(bridge-devops-sec-pentest)*
- [[building-threat-actor-profile-from-osint]] → [[collecting-open-source-intelligence]] *(bridge-devops-sec-pentest)*
- [[building-vulnerability-aging-and-sla-tracking]] → [[building-vulnerability-exception-tracking-system]] *(bridge-devops-meta)*
- [[clerk]] → [[clerk-expo-patterns]] *(bridge-creative-sec-compliance)*
- [[clerk-setup]] → [[clerk-testing]] *(bridge-creative-coding)*
- [[collecting-open-source-intelligence]] → [[performing-osint-with-spiderfoot]] *(bridge-sec-pentest-research)*
- [[configuring-microsegmentation-for-zero-trust]] → [[implementing-microsegmentation-with-guardicore]] *(bridge-devops-data)*
- [[deploying-cloudflare-access-for-zero-trust]] → [[deploying-tailscale-for-zero-trust-vpn]] *(bridge-devops-sec-compliance)*
- [[deploying-cloudflare-access-for-zero-trust]] → [[implementing-zero-trust-with-beyondcorp]] *(bridge-devops-meta)*
- [[detecting-anomalies-in-industrial-control-systems]] → [[detecting-attacks-on-scada-systems]] *(bridge-sec-monitoring-sec-pentest)*
- [[detecting-aws-cloudtrail-anomalies]] → [[detecting-compromised-cloud-credentials]] *(bridge-sec-monitoring-sec-pentest)*
- [[detecting-aws-guardduty-findings-automation]] → [[detecting-cloud-threats-with-guardduty]] *(bridge-sec-incident-sec-monitoring)*
- [[detecting-azure-lateral-movement]] → [[detecting-azure-service-principal-abuse]] *(bridge-sec-monitoring-sec-pentest)*
- [[executing-red-team-engagement-planning]] → [[conducting-full-scope-red-team-engagement]] *(bridge-meta-sec-pentest)*
- [[expo-deployment]] → [[expo-dev-client]] *(bridge-devops-coding)*
- [[implementing-api-security-testing-with-42crunch]] → [[implementing-api-security-posture-management]] *(bridge-sec-audit-devops)*
- [[implementing-aws-iam-permission-boundaries]] → [[securing-aws-iam-permissions]] *(bridge-devops-sec-compliance)*
- [[implementing-aws-security-hub]] → [[detecting-cloud-threats-with-guardduty]] *(bridge-sec-compliance-sec-monitoring)*
- [[implementing-delinea-secret-server-for-pam]] → [[implementing-hashicorp-vault-dynamic-secrets]] *(bridge-devops-data)*
- [[implementing-device-posture-assessment-in-zero-trust]] → [[implementing-conditional-access-policies-azure-ad]] *(bridge-sec-audit-sec-compliance)*
- [[implementing-device-posture-assessment-in-zero-trust]] → [[implementing-zero-trust-with-beyondcorp]] *(bridge-sec-audit-meta)*
- [[implementing-gcp-binary-authorization]] → [[implementing-gcp-organization-policy-constraints]] *(bridge-devops-sec-compliance)*
- [[implementing-gcp-binary-authorization]] → [[implementing-zero-trust-with-beyondcorp]] *(bridge-devops-meta)*
- [[implementing-google-workspace-sso-configuration]] → [[implementing-google-workspace-admin-security]] *(bridge-creative-sec-compliance)*
- [[implementing-just-in-time-access-provisioning]] → [[implementing-zero-standing-privilege-with-cyberark]] *(bridge-creative-sec-compliance)*
- [[implementing-pam-for-database-access]] → [[implementing-delinea-secret-server-for-pam]] *(bridge-sec-audit-devops)*
- [[implementing-patch-management-workflow]] → [[implementing-patch-management-for-ot-systems]] *(bridge-devops-coding)*
- [[implementing-rbac-hardening-for-kubernetes]] → [[auditing-kubernetes-cluster-rbac]] *(bridge-sec-audit-sec-pentest)*
- [[implementing-secrets-management-with-vault]] → [[implementing-hashicorp-vault-dynamic-secrets]] *(bridge-devops-data)*
- [[implementing-zero-trust-in-cloud]] → [[implementing-zero-trust-with-beyondcorp]] *(bridge-sec-audit-meta)*
- [[implementing-zero-trust-with-beyondcorp]] → [[implementing-zero-trust-for-saas-applications]] *(bridge-meta-sec-compliance)*
- [[performing-android-app-static-analysis-with-mobsf]] → [[analyzing-android-malware-with-apktool]] *(bridge-sec-audit-sec-incident)*
- [[performing-android-app-static-analysis-with-mobsf]] → [[performing-dynamic-analysis-of-android-app]] *(bridge-sec-audit-coding)*
- [[performing-authenticated-scan-with-openvas]] → [[implementing-vulnerability-management-with-greenbone]] *(bridge-sec-audit-devops)*
- [[performing-aws-privilege-escalation-assessment]] → [[detecting-aws-iam-privilege-escalation]] *(bridge-sec-audit-sec-monitoring)*
- [[performing-bluetooth-security-assessment]] → [[detecting-bluetooth-low-energy-attacks]] *(bridge-sec-audit-sec-pentest)*
- [[performing-directory-traversal-testing]] → [[testing-for-broken-access-control]] *(bridge-coding-sec-compliance)*
- [[performing-docker-bench-security-assessment]] → [[benchmarking-kubernetes-with-kube-bench]] *(bridge-sec-audit-sec-compliance)*
- [[performing-docker-bench-security-assessment]] → [[hardening-docker-containers-for-production]] *(bridge-sec-audit-sec-compliance)*
- [[performing-ios-app-security-assessment]] → [[performing-dynamic-analysis-of-android-app]] *(bridge-sec-audit-coding)*
- [[scanning-kubernetes-manifests-with-kubesec]] → [[auditing-kubernetes-cluster-rbac]] *(bridge-devops-sec-pentest)*
- [[spec-driven-development]] → [[test-driven-development]] *(bridge-creative-sec-monitoring)*
- [[terraform-module-library]] → [[refactor-module]] *(bridge-devops-coding)*
- [[testing-api-for-broken-object-level-authorization]] → [[conducting-api-security-testing]] *(bridge-coding-sec-monitoring)*
- [[testing-api-for-broken-object-level-authorization]] → [[detecting-broken-object-property-level-authorization]] *(bridge-coding-sec-pentest)*
- [[testing-api-for-broken-object-level-authorization]] → [[testing-for-broken-access-control]] *(bridge-coding-sec-compliance)*
- [[wp-block-themes]] → [[wp-block-development]] *(bridge-creative-data)*
- [[wrangler]] → [[cloudflare]] *(bridge-meta-coding)*
- [[xlsx]] → [[minimax-xlsx]] *(bridge-creative-data)*

## Workflows

### add-reasonix-tui-agent-to

_pipeline:Add Reasonix TUI agent to Orca multi-agent orchestrator and fix bugs_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…

### afac-doc-parsing

_build:AFAC赛题二：多模态金融文档解析。输入超大金融文档截图（面条图1508×50170），输出高保真Markdown。唯一VLM：FinixDoc-VL API。本地模型<10M参数。全量运行≤3小时。核心模块：智能切片、并行API调用、Markdown拼接去重、表格HTML还原、阅读流顺序恢复。_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[academic-paper]] — 12-agent academic paper writing pipeline. 11 modes (full/pla…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…

### build-a-saas-website-with

_build:build a SaaS website with user auth, payment integration, and admin dashboard_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[design-mobile-apps]] — Use when the user wants to design a mobile app, create scree…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…

### final-smoke

_build:final smoke test_

**Pipeline:**

- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…

### hello-world-test

_build:hello world test_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[browser-testing-with-devtools]] — Tests in real browsers via Chrome DevTools MCP. Use when bui…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[testing-for-system-prompt-leakage]] — Extract and defend system prompts plus embedded secrets and …
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…

### optimize-dailyglider

_pipeline:optimize Tauri dailyglider project_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…

### test-q

_build:test Q-table recording_

**Pipeline:**

- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…

### verify-test

_build:verify Q-table_

**Pipeline:**

- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…

### vf

_build:verify final_

**Pipeline:**

- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…

### wf-optimize-dailyglider

_pipeline:优化 Tauri dailyglider 项目：前端性能、Rust后端、构建配置、UI/UX_

**Pipeline:**

- [[codebase-recon]] — Analyze codebases and render architecture diagrams. Auto-rou…
- [[codebase-inject]] — Inject codebase context before planning. Tool selection: <10…
- [[brainstorming]] — You MUST use this before any creative work - creating featur…
- [[idea-refine]] — Refines raw ideas into sharp, actionable concepts through st…
- [[spec-driven-development]] — Creates specs before coding. Use when starting a new project…
- [[planning-and-task-breakdown]] — Breaks work into ordered tasks. Use when you have a spec or …
- [[incremental-implementation]] — Delivers changes incrementally. Use when implementing any fe…
- [[orchestration]] — Use Orca orchestration for structured multi-agent coordinati…
- [[orca-cli]] — Use the public orca CLI to operate Orca-managed worktrees, f…
- [[dispatching-parallel-agents]] — Use when facing 2+ independent tasks that can be worked on w…
- [[omp-in-orca]] — Run oh-my-pi (omp) as a launchable agent inside Orca ADE. Co…
- [[test-driven-development]] — Drives development with tests. Use when implementing any log…
- [[code-simplification]] — Simplifies code for clarity. Use when refactoring code for c…
- [[code-review-and-quality]] — Conducts multi-axis code review. Use before merging any chan…
- [[doubt-driven-development]] — Subjects every non-trivial decision to a fresh-context adver…
- [[receiving-code-review]] — Use when receiving code review feedback, before implementing…
- [[security-and-hardening]] — Hardens code against vulnerabilities. Use when handling user…
- [[performing-threat-modeling-with-owasp-threat-dragon]] — Use OWASP Threat Dragon to create data flow diagrams, identi…
- [[building-vulnerability-scanning-workflow]] — Builds a structured vulnerability scanning workflow using to…
- [[git-workflow-and-versioning]] — Structures git workflow practices. Use when making any code …
- [[documentation-and-adrs]] — Records decisions and documentation. Use when making archite…
- [[shipping-and-launch]] — Prepares production launches. Use when preparing to deploy t…
