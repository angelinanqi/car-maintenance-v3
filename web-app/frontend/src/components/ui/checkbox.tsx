"use client";

import {
  Checkbox as ChakraCheckbox,
  type CheckboxRootProps,
} from "@chakra-ui/react";

// Closed Chakra composition shared by catalogue and content forms.
export function Checkbox({ children, ...props }: CheckboxRootProps) {
  return (
    <ChakraCheckbox.Root {...props}>
      <ChakraCheckbox.HiddenInput />
      <ChakraCheckbox.Control>
        <ChakraCheckbox.Indicator />
      </ChakraCheckbox.Control>
      <ChakraCheckbox.Label>{children}</ChakraCheckbox.Label>
    </ChakraCheckbox.Root>
  );
}
