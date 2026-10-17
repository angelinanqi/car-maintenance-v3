"use client";

import { forwardRef, useRef } from "react";
import {
  Button,
  HStack,
  Input,
  InputGroup,
  Progress,
  Stack,
  Text,
  mergeRefs,
  useControllableState,
} from "@chakra-ui/react";

// Chakra's documented PasswordInput snippet composition. Text keeps the
// visibility action explicit without adding an icon dependency.
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
        <Button
          type="button"
          size="xs"
          variant="outline"
          disabled={props.disabled}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setVisible(!visible);
            input.current?.focus();
          }}
        >
          {visible ? "Hide" : "Show"}
        </Button>
      }
    >
      <Input
        {...props}
        pe="20"
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
        <Progress.Label>Password strength guidance</Progress.Label>
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
