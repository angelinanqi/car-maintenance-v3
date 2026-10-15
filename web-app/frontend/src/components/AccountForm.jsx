"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import NextLink from "next/link";
import { Box, Button, Card, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { registerAccount } from "@/api/accounts.mjs";
import { useSession } from "./SessionProvider";

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

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!email.trim() || !event.currentTarget.checkValidity()) {
      setError("Enter a valid email address.");
      return;
    }
    if (registering && !displayName.trim()) {
      setError("Enter your name.");
      return;
    }
    if (registering && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (registering && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const details = { email: email.trim(), password };
      if (registering) {
        await registerAccount({ ...details, display_name: displayName.trim() });
        setSuccess("Account created. You can now sign in. Administrative access is assigned separately.");
      } else {
        const result = await session.login(details);
        if (result.user.role === "admin") router.replace("/user/home");
        else setSuccess("Signed in. This account can be used in the mobile app; administrator access is required for this dashboard.");
      }
      setPassword("");
      setConfirmPassword("");
    } catch (cause) {
      setError(cause.message || "The request failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box minH="100vh" bg="gray.50" color="gray.900" px={4} py={{ base: 8, md: 12 }} display="flex" alignItems="center" justifyContent="center">
      <Stack w="full" maxW="440px" gap={6}>
        <Box textAlign="center">
          <Text color="blue.700" fontWeight="bold" letterSpacing="wide" mb={2}>CAR APP</Text>
          <Heading as="h1" size="xl">{registering ? "Create your account" : "Welcome back"}</Heading>
          <Text color="gray.600" mt={2}>{registering ? "Save your details to get started." : "Sign in to your account."}</Text>
        </Box>
        <Card.Root variant="outline" bg="white" shadow="sm" borderRadius="xl">
          <Card.Body p={{ base: 5, md: 8 }}>
            <form onSubmit={submit}>
              <Stack gap={4}>
                {registering && <Box as="label" display="block" fontWeight="medium" fontSize="sm">Name<Input mt={2} value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" required maxLength={100} disabled={loading} /></Box>}
                <Box as="label" display="block" fontWeight="medium" fontSize="sm">Email address<Input mt={2} type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required disabled={loading} /></Box>
                <Box as="label" display="block" fontWeight="medium" fontSize="sm">
                  Password
                  <Box mt={2} display="flex" gap={2}>
                    <Input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={registering ? "new-password" : "current-password"} required minLength={registering ? 8 : 1} disabled={loading} />
                    <Button type="button" variant="outline" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} disabled={loading}>{showPassword ? "Hide" : "Show"}</Button>
                  </Box>
                </Box>
                {registering && <Box as="label" display="block" fontWeight="medium" fontSize="sm">Confirm password<Input mt={2} type={showPassword ? "text" : "password"} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" required disabled={loading} /></Box>}
                {error && <Text role="alert" color="red.600" fontSize="sm">{error}</Text>}
                {success && <Text role="status" color="green.700" fontSize="sm">{success}</Text>}
                <Button type="submit" colorPalette="blue" w="full" disabled={loading} aria-busy={loading}>{loading ? "Please wait..." : registering ? "Create account" : "Sign in"}</Button>
              </Stack>
            </form>
          </Card.Body>
        </Card.Root>
        <Text textAlign="center" fontSize="sm" color="gray.600">{registering ? "Already have an account?" : "New here?"} <NextLink href={registering ? "/login" : "/register"}>{registering ? "Go to login" : "Create an account"}</NextLink></Text>
        <Text textAlign="center" fontSize="sm"><NextLink href="/user/home">Continue to dashboard</NextLink></Text>
      </Stack>
    </Box>
  );
}
