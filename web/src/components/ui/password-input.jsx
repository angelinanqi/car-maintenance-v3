"use client";

import { forwardRef, useRef } from "react";
import {
  IconButton,
  HStack,
  Input,
  InputGroup,
  Progress,
  Stack,
  Text,
  mergeRefs,
  useControllableState,
} from "@chakra-ui/react";

// Shared visibility toggle for all password fields.
export const PasswordInput = forwardRef(function PasswordInput(
  {
    visible: controlledVisible,
    defaultVisible = false,
    onVisibleChange,
    ...props
  },
  ref,
) {
  const input = useRef(null);
  const [visible, setVisible] = useControllableState({
    value: controlledVisible,
    defaultValue: defaultVisible,
    onChange: onVisibleChange,
  });
  return (
    <InputGroup
      width="full"
      endElement={
        <IconButton
          type="button"
          size="xs"
          variant="plain"
          bg="transparent"
          border="none"
          boxShadow="none"
          color={visible ? "brand.700" : "muted"}
          w="40px"
          h="40px"
          p={0}
          _hover={{ bg: "transparent", color: "ink" }}
          _active={{ bg: "transparent", color: "brand.700" }}
          disabled={props.disabled}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setVisible(!visible);
            input.current?.focus();
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
            {visible ? <>
              <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
              <circle cx="12" cy="12" r="3" />
            </> : <>
              <path d="m3 3 18 18M10.6 5.1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-3.1 4.1M6.3 6.3A21 21 0 0 0 2 12s3.5 7 10 7a12 12 0 0 0 5.7-1.7M9.9 9.9a3 3 0 0 0 4.2 4.2" />
            </>}
          </svg>
        </IconButton>
      }
    >
      <Input
        {...props}
        pe="12"
        ref={mergeRefs(ref, input)}
        type={visible ? "text" : "password"}
      />
    </InputGroup>
  );
});

export function PasswordStrengthMeter({ password }) {
  // Length guidance is advisory; the backend's existing password policy applies.
  const value =
    password.length === 0
      ? 0
      : password.length < 8
        ? 1
        : password.length < 12
          ? 2
          : password.length < 16
            ? 3
            : 4;
  const label = [
    "Enter a password",
    "Too short",
    "Fair length",
    "Good length",
    "Long password",
  ][value];
  return (
    <Stack width="full" gap={1}>
      <Progress.Root
        value={value}
        max={4}
        size="xs"
        colorPalette={value < 2 ? "red" : value < 4 ? "orange" : "green"}
      >
        <Progress.Label>Password strength</Progress.Label>
        <Progress.Track>
          <Progress.Range />
        </Progress.Track>
      </Progress.Root>
      <HStack justify="space-between" fontSize="xs">
        <Text>{label}</Text>
        <Text>Longer, unique passwords are stronger.</Text>
      </HStack>
    </Stack>
  );
}
