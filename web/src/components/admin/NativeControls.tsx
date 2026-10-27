"use client";

import { NativeSelect, type NativeSelectFieldProps } from "@chakra-ui/react";

type AdminSelectProps = NativeSelectFieldProps & {
  disabled?: boolean;
  required?: boolean;
};

export function AdminSelect({
  children,
  disabled,
  required,
  ...props
}: AdminSelectProps) {
  return (
    <NativeSelect.Root disabled={disabled} width="full">
      {/* Required validation comes from the enclosing Chakra Field.Root. */}
      <NativeSelect.Field
        {...props}
        aria-required={required || props["aria-required"]}
        minH="44px"
        bg="white"
        borderColor="#7b8794"
      >
        {children}
      </NativeSelect.Field>
      <NativeSelect.Indicator />
    </NativeSelect.Root>
  );
}
