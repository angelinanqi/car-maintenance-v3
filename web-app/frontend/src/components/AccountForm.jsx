"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import NextLink from "next/link";
import { Box, Button, Field, Flex, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { registerAccount } from "@/api/accounts.mjs";
import { useSession } from "./SessionProvider";
import Brand from "./Brand";
import { PasswordInput, PasswordStrengthMeter } from "./ui/password-input";

export default function AccountForm({ mode }) {
  const registering = mode === "register";
  const session = useSession();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const passwordInvalid = registering && (password.length < 8 || password.length > 1024);
  const mismatch = registering && confirmPassword !== password;

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    setSubmitted(true);
    setError("");
    setSuccess("");
    if (registering && !displayName.trim()) return;
    if (passwordInvalid || mismatch) return;
    if (!event.currentTarget.reportValidity()) return;
    setLoading(true);
    try {
      const details = { email: email.trim(), password };
      if (registering) {
        await registerAccount({ ...details, display_name: displayName.trim() });
        setSuccess("Account created. Sign in to continue. An administrator must assign dashboard access separately.");
      } else {
        const result = await session.login(details);
        if (result.user.role === "admin") router.replace("/user/home");
        else setSuccess("Signed in. Your account is ready for Roadie. Ask your administrator for access to Roadie Admin.");
      }
      setPassword("");
      setConfirmPassword("");
      setSubmitted(false);
    } catch (cause) {
      setError(cause.message || "Could not connect. Please try again.");
    } finally { setLoading(false); }
  }

  return (
    <Flex minH="100dvh" direction={{ base: "column", lg: "row" }}>
      <Flex w={{ base: "100%", lg: "44%" }} bg="rail" color="white" p={{ base: 6, md: 10, xl: 14 }} direction="column" justify="space-between" gap={12}>
        <Brand inverse />
        <Box display={{ base: "none", lg: "block" }} maxW="450px" py={14}>
          <Heading as="h2" color="white" fontSize={{ lg: "44px", xl: "56px" }} lineHeight="1.08" mb={6}>Better care starts here.</Heading>
          <Text color="#c5cdd6" fontSize="lg">The workspace behind Roadie. Keep vehicle knowledge accurate, maintenance clear, and guidance ready for the road.</Text>
          <Stack mt={12} gap={5}>
            {["Maintain the vehicle catalogue", "Publish reviewed guides and manuals", "Check answers before drivers need them"].map((line) => <Flex gap={3} align="center" key={line}><Box w="7px" h="7px" bg="brand.400" borderRadius="full" /><Text>{line}</Text></Flex>)}
          </Stack>
        </Box>
        <Text color="#abb7c4" fontSize="sm" display={{ base: "none", lg: "block" }}>Built for the people keeping Roadie useful.</Text>
      </Flex>
      <Flex as="main" flex={1} px={{ base: 5, md: 10 }} py={10} align="center" justify="center">
        <Stack w="full" maxW="420px" gap={7}>
          <Box>
            <Heading as="h1" fontSize="32px" lineHeight="1.2">{registering ? "Create an account" : "Welcome back"}</Heading>
            <Text color="muted" mt={3}>{registering ? "One account for Roadie and Roadie Admin." : "Sign in to your Roadie Admin workspace."}</Text>
          </Box>
          <Box as="form" onSubmit={submit} noValidate>
            <Stack gap={5}>
              {registering && <Field.Root required invalid={submitted && !displayName.trim()}>
                <Field.Label htmlFor="account-name">Full name <Field.RequiredIndicator /></Field.Label>
                <Input id="account-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoComplete="name" required maxLength={100} disabled={loading} />
                <Field.ErrorText>Enter your name, up to 100 characters.</Field.ErrorText>
              </Field.Root>}
              <Field.Root required>
                <Field.Label htmlFor="account-email">Email address <Field.RequiredIndicator /></Field.Label>
                <Input id="account-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required disabled={loading} placeholder="you@example.com" />
              </Field.Root>
              <Field.Root required invalid={submitted && passwordInvalid}>
                <Field.Label htmlFor="account-password">Password <Field.RequiredIndicator /></Field.Label>
                <PasswordInput id="account-password" visible={showPassword} onVisibleChange={setShowPassword} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={registering ? "new-password" : "current-password"} required minLength={registering ? 8 : 1} maxLength={1024} disabled={loading} aria-describedby={registering ? "password-requirements" : undefined} />
                {registering && <PasswordStrengthMeter password={password} />}
                {registering && <Field.HelperText id="password-requirements">Use 8–1,024 characters. No special character or number is required.</Field.HelperText>}
                <Field.ErrorText>Use a password between 8 and 1,024 characters.</Field.ErrorText>
              </Field.Root>
              {registering && <Field.Root required invalid={Boolean(confirmPassword || submitted) && mismatch}>
                <Field.Label htmlFor="account-confirm">Confirm password <Field.RequiredIndicator /></Field.Label>
                <PasswordInput id="account-confirm" visible={showPassword} onVisibleChange={setShowPassword} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} autoComplete="new-password" required maxLength={1024} disabled={loading} />
                <Field.ErrorText>Passwords must match.</Field.ErrorText>
              </Field.Root>}
              {error && <Text role="alert">{error}</Text>}
              {success && <Text role="status">{success}</Text>}
              <Button type="submit" colorPalette="brand" w="full" loading={loading} loadingText={registering ? "Creating account" : "Signing in"}>{registering ? "Create account" : "Sign in"}</Button>
            </Stack>
          </Box>
          <Text fontSize="md" color="ink">{registering ? "Already registered?" : "Need an account?"} <NextLink style={{ color: "#795000", fontWeight: 600, textDecoration: "underline" }} href={registering ? "/login" : "/register"}>{registering ? "Sign in" : "Create an account"}</NextLink></Text>
          <Box bg="white" p={4} borderRadius="8px"><Text fontSize="md" color="ink">{registering ? "Registration creates a standard account. Dashboard access is assigned by your administrator." : "This workspace requires administrator access. Drivers can use the Roadie mobile app with the same account."}</Text></Box>
        </Stack>
      </Flex>
    </Flex>
  );
}
