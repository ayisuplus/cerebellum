---
title: analyzing-active-directory-acl-abuse
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [anthropic-cybersecurity-skills]
category: Anthropic-Cybersecurity-Skills
related: [auditing-kubernetes-cluster-rbac, configuring-ldap-security-hardening, detecting-azure-service-principal-abuse, executing-active-directory-attack-simulation, exploiting-active-directory-with-bloodhound, exploiting-constrained-delegation-abuse, hunting-for-dcsync-attacks, hunting-for-t1098-account-manipulation, mapping-attack-paths-with-bloodhound-ce, performing-active-directory-compromise-investigation, performing-active-directory-forest-trust-attack, performing-active-directory-vulnerability-assessment]
confidence: low
---

Detect dangerous ACL misconfigurations in Active Directory using ldap3 to identify GenericAll, WriteDACL, and WriteOwner abuse paths

## Metadata

- **ID:** `analyzing-active-directory-acl-abuse`
- **Source:** `Anthropic-Cybersecurity-Skills/skills/analyzing-active-directory-acl-abuse/SKILL.md`
- **Score:** 38.0
- **Edges:** 12

## Related Skills

- [[executing-active-directory-attack-simulation]] *(similar)* — Executes authorized attack simulations against Active Directory environments to identify misconfigurations, weak credentials, dangerous privilege paths, and exploitable trust relationships that could lead to domain compromise. The tester uses BloodHound for attack path analysis, Mimikatz for credent
- [[exploiting-active-directory-with-bloodhound]] *(similar)* — BloodHound is a graph-based Active Directory reconnaissance tool that uses graph theory to reveal hidden and unintended relationships within AD environments. Red teams use BloodHound to identify attac
- [[exploiting-constrained-delegation-abuse]] *(similar)* — Exploit Kerberos Constrained Delegation misconfigurations in Active Directory to impersonate privileged users via S4U2self and S4U2proxy extensions for lateral movement and privilege escalation.
- [[performing-active-directory-compromise-investigation]] *(similar)* — Investigate Active Directory compromise by analyzing authentication logs, replication metadata, Group Policy changes, and Kerberos ticket anomalies to identify attacker persistence and lateral movement paths.
- [[performing-active-directory-vulnerability-assessment]] *(similar)* — Assess Active Directory security posture using PingCastle, BloodHound, and Purple Knight to identify misconfigurations, privilege escalation paths, and attack vectors.
- [[auditing-kubernetes-cluster-rbac]] *(similar)* — Auditing Kubernetes cluster RBAC configurations to identify overly permissive roles, wildcard permissions, dangerous ClusterRoleBindings, service account abuse, and privilege escalation paths using kubectl, rbac-tool, KubiScan, and Kubeaudit.

- [[configuring-ldap-security-hardening]] *(similar)* — Harden LDAP directory services against common attacks including credential harvesting, LDAP injection, anonymous binding, and channel binding bypass. Covers LDAPS enforcement, channel binding, LDAP si
- [[detecting-azure-service-principal-abuse]] *(similar)* — Detect and investigate Azure service principal abuse including privilege escalation, credential compromise, admin consent bypass, and unauthorized enumeration in Microsoft Entra ID environments.
- [[hunting-for-dcsync-attacks]] *(similar)* — Detect DCSync attacks by analyzing Windows Event ID 4662 for unauthorized DS-Replication-Get-Changes requests from non-domain-controller accounts.
- [[hunting-for-t1098-account-manipulation]] *(similar)* — Hunt for MITRE ATT&CK T1098 account manipulation including shadow admin creation, SID history injection, group membership changes, and credential modifications using Windows Security Event Logs.
- [[mapping-attack-paths-with-bloodhound-ce]] *(similar)* — Collect Active Directory data with SharpHound and Entra ID data with AzureHound, ingest into BloodHound Community Edition, and analyze on-prem, cloud, and hybrid attack paths with built-in queries and custom Cypher.
- [[performing-active-directory-forest-trust-attack]] *(similar)* — Enumerate and audit Active Directory forest trust relationships using impacket for SID filtering analysis, trust key extraction, cross-forest SID history abuse detection, and inter-realm Kerberos ticket assessment.

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
