import { createBrowserClient } from "@supabase/ssr";
import { logAccountFailure } from "./liveLogging.mjs";

let client;
export function browserAuth() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error("Supabase account access is not configured. Check the public Supabase URL and publishable key.");
  if (!client) client = createBrowserClient(url, key, { auth: { flowType: "pkce" } });
  return client.auth;
}

export function authRedirect() {
  return `${window.location.origin}/auth/callback`;
}

export function passwordError(password) {
  const length = Array.from(password).length;
  return length < 8 || length > 20 ? "Use a password with 8 to 20 characters." : "";
}

export function authError(error) {
  if (!error?.code) return error?.message || "Account access failed. Check your connection and retry.";
  switch (error.code) {
    case "invalid_credentials": return "The email or password is incorrect.";
    case "current_password_mismatch": return "The current password is incorrect.";
    case "same_password": return "Choose a password different from your current one.";
    case "email_exists":
    case "email_address_not_authorized": return "This email address cannot be used. Try a different address.";
    case "reauthentication_not_valid": return "The verification code is invalid or expired. Request a new code.";
    case "email_not_confirmed": return "Confirm your email before signing in. You can request another confirmation email.";
    case "weak_password": return "Your password must be 8–20 characters long and include at least one uppercase letter, one lowercase letter, one number, and one special character.";
    case "over_email_send_rate_limit":
    case "over_request_rate_limit": return "Too many attempts. Wait at least a minute before retrying.";
    case "otp_expired": return "This email link expired or was already used. Request a new link.";
    case "mfa_verification_failed":
    case "mfa_challenge_expired": return "The authenticator code is invalid or expired. Enter the current code.";
    default: return "Account access could not be completed. Check your connection and retry, or request a new email link.";
  }
}

export async function authResult(operation) {
  try {
    const result = await operation;
    if (result.error) throw result.error;
    return result.data;
  } catch (error) { logAccountFailure(error); throw error; }
}
