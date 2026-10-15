import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  type ReactNode,
} from "react";
import { Field } from "@chakra-ui/react";

export default function FormField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const id = useId();
  const elements = Children.toArray(children);
  const control = elements[0];
  const labelledControl = isValidElement<{ id?: string }>(control)
    ? cloneElement(control, { id })
    : control;
  return (
    <Field.Root>
      <Field.Label htmlFor={id}>{label}</Field.Label>
      {labelledControl}
      {elements.slice(1)}
    </Field.Root>
  );
}
