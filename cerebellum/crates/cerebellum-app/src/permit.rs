use anyhow::{Context, Result, bail};
use base64::{Engine as _, engine::general_purpose::URL_SAFE_NO_PAD};
use cerebellum_core::{ActionPermit, canonical_json_hash};
use chrono::Utc;
/// Hard ceiling enforced at verification time, independent of the minting
/// site's clamp: a permit valid longer than this is rejected no matter who
/// signed it. Matches the api.rs authorize clamp of 1..=300 seconds.
const MAX_PERMIT_LIFETIME_SECONDS: i64 = 300;

/// Tolerated clock skew when checking `issued_at` against the verifier's
/// clock. Expiry itself stays strict.
const ISSUED_AT_SKEW_SECONDS: i64 = 30;
use hmac::{Hmac, Mac};
use serde_json::Value;
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

#[derive(Clone)]
pub struct PermitSigner {
    secret: Vec<u8>,
}

impl PermitSigner {
    pub fn new(secret: Vec<u8>) -> Result<Self> {
        if secret.len() < 32 {
            bail!("permit signing secret must be at least 32 bytes");
        }
        Ok(Self { secret })
    }

    pub fn sign(&self, permit: &ActionPermit) -> Result<String> {
        let payload = serde_json::to_vec(permit)?;
        let mut mac =
            HmacSha256::new_from_slice(&self.secret).expect("HMAC accepts arbitrary key sizes");
        mac.update(&payload);
        let signature = mac.finalize().into_bytes();
        Ok(format!(
            "{}.{}",
            URL_SAFE_NO_PAD.encode(payload),
            URL_SAFE_NO_PAD.encode(signature)
        ))
    }

    pub fn verify(&self, token: &str, action: &Value) -> Result<ActionPermit> {
        let (payload, signature) = token
            .split_once('.')
            .context("invalid permit token format")?;
        let payload = URL_SAFE_NO_PAD
            .decode(payload)
            .context("invalid permit payload")?;
        let signature = URL_SAFE_NO_PAD
            .decode(signature)
            .context("invalid permit signature")?;
        let mut mac =
            HmacSha256::new_from_slice(&self.secret).expect("HMAC accepts arbitrary key sizes");
        mac.update(&payload);
        mac.verify_slice(&signature)
            .map_err(|_| anyhow::anyhow!("invalid permit signature"))?;
        let permit: ActionPermit = serde_json::from_slice(&payload)?;
        let now = Utc::now();
        if permit.issued_at > now + chrono::Duration::seconds(ISSUED_AT_SKEW_SECONDS) {
            bail!("permit was issued in the future");
        }
        let lifetime = permit.expires_at - permit.issued_at;
        if lifetime <= chrono::Duration::zero() {
            bail!("permit has a non-positive lifetime");
        }
        if lifetime > chrono::Duration::seconds(MAX_PERMIT_LIFETIME_SECONDS) {
            bail!("permit lifetime exceeds the {MAX_PERMIT_LIFETIME_SECONDS} second ceiling");
        }
        if permit.expires_at <= now {
            bail!("permit has expired");
        }
        if permit.action_hash != canonical_json_hash(action) {
            bail!("permit does not match this action");
        }
        Ok(permit)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;
    use uuid::Uuid;

    #[test]
    fn permit_is_bound_to_action() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let permit = ActionPermit {
            permit_id: Uuid::new_v4(),
            run_id: Uuid::new_v4(),
            workflow_id: "bugfix".into(),
            workflow_version: "1.0.0".into(),
            action_hash: canonical_json_hash(&action),
            issued_at: Utc::now(),
            expires_at: Utc::now() + Duration::minutes(1),
        };
        let token = signer.sign(&permit).unwrap();
        assert!(signer.verify(&token, &action).is_ok());
        assert!(
            signer
                .verify(
                    &token,
                    &serde_json::json!({"tool":"shell","command":"git push"})
                )
                .is_err()
        );
    }
    fn mint(signer: &PermitSigner, issued: Duration, lifetime: Duration) -> String {
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let permit = ActionPermit {
            permit_id: Uuid::new_v4(),
            run_id: Uuid::new_v4(),
            workflow_id: "bugfix".into(),
            workflow_version: "1.0.0".into(),
            action_hash: canonical_json_hash(&action),
            issued_at: Utc::now() + issued,
            expires_at: Utc::now() + issued + lifetime,
        };
        signer.sign(&permit).unwrap()
    }

    #[test]
    fn verify_rejects_overlong_lifetime() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let token = mint(&signer, Duration::zero(), Duration::minutes(10));
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let error = signer.verify(&token, &action).unwrap_err();
        assert!(error.to_string().contains("lifetime"), "{error}");
    }

    #[test]
    fn verify_rejects_tampered_payload_byte() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let token = mint(&signer, Duration::zero(), Duration::seconds(60));
        let (payload, signature) = token.split_once('.').unwrap();
        let mut decoded = URL_SAFE_NO_PAD.decode(payload).unwrap();
        decoded[0] ^= 0x01;
        let forged = format!("{}.{}", URL_SAFE_NO_PAD.encode(decoded), signature);
        let error = signer.verify(&forged, &action).unwrap_err();
        assert!(error.to_string().contains("signature"), "{error}");
    }

    #[test]
    fn verify_rejects_tampered_signature_byte() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let token = mint(&signer, Duration::zero(), Duration::seconds(60));
        let (payload, signature) = token.split_once('.').unwrap();
        let mut decoded = URL_SAFE_NO_PAD.decode(signature).unwrap();
        let last = decoded.len() - 1;
        decoded[last] ^= 0x01;
        let forged = format!("{}.{}", payload, URL_SAFE_NO_PAD.encode(decoded));
        let error = signer.verify(&forged, &action).unwrap_err();
        assert!(error.to_string().contains("signature"), "{error}");
    }

    #[test]
    fn verify_rejects_wrong_key() {
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let token = mint(
            &PermitSigner::new(vec![42; 32]).unwrap(),
            Duration::zero(),
            Duration::seconds(60),
        );
        let other = PermitSigner::new(vec![43; 32]).unwrap();
        let error = other.verify(&token, &action).unwrap_err();
        assert!(error.to_string().contains("signature"), "{error}");
    }

    #[test]
    fn verify_rejects_malformed_tokens() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        // No dot separator.
        assert!(signer.verify("abcdef", &action).is_err());
        // Bad base64 on both segments.
        assert!(signer.verify("!!!.@@@", &action).is_err());
        // Empty signature segment.
        assert!(signer.verify("abc.", &action).is_err());
    }

    #[test]
    fn verify_rejects_future_issued_at() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let token = mint(&signer, Duration::minutes(5), Duration::seconds(60));
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let error = signer.verify(&token, &action).unwrap_err();
        assert!(error.to_string().contains("future"), "{error}");
    }

    #[test]
    fn verify_rejects_non_positive_lifetime_and_expired() {
        let signer = PermitSigner::new(vec![42; 32]).unwrap();
        let action = serde_json::json!({"tool":"shell","command":"cargo test"});
        let inverted = mint(&signer, Duration::seconds(30), Duration::seconds(-30));
        assert!(signer.verify(&inverted, &action).is_err());
        let expired = mint(&signer, Duration::seconds(-120), Duration::seconds(30));
        assert!(signer.verify(&expired, &action).is_err());
    }
}
