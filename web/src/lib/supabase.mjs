import { createBrowserClient } from "@supabase/ssr";

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
    case "email_not_confirmed": return "Confirm your email before signing in. You can request another confirmation email.";
    case "weak_password": return "Choose a stronger password with 8 to 20 characters that meets the project password requirements.";
    case "over_email_send_rate_limit":
    case "over_request_rate_limit": return "Too many attempts. Wait at least a minute before retrying.";
    case "otp_expired": return "This email link expired or was already used. Request a new link.";
    case "mfa_verification_failed":
    case "mfa_challenge_expired": return "The authenticator code is invalid or expired. Enter the current code.";
    default: return "Account access could not be completed. Check your connection and retry, or request a new email link.";
  }
}

export async function authResult(operation) {
  const result = await operation;
  if (result.error) throw result.error;
  return result.data;
}
