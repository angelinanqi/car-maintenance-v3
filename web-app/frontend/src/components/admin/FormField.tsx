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
  hint,
  error,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
  error?: string;
}) {
  const id = useId();
  const elements = Children.toArray(children);
  const control = elements[0];
  const required =
    isValidElement<{ required?: boolean }>(control) &&
    Boolean(control.props.required);
  const disabled =
    isValidElement<{ disabled?: boolean }>(control) &&
    Boolean(control.props.disabled);
  const labelledControl = isValidElement<{
    id?: string;
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }>(control)
    ? cloneElement(control, {
        id,
        "aria-describedby":
          [
            control.props["aria-describedby"],
            hint ? `${id}-hint` : "",
            error ? `${id}-error` : "",
          ]
            .filter(Boolean)
            .join(" ") || undefined,
        "aria-invalid": error ? true : undefined,
      })
    : control;
  return (
    <Field.Root minW={0} required={required} disabled={disabled || undefined} invalid={Boolean(error)}>
      <Field.Label htmlFor={id}>
        {label}
        {required && <Field.RequiredIndicator />}
      </Field.Label>
      {labelledControl}
      {elements.slice(1)}
      {hint && <Field.HelperText id={`${id}-hint`}>{hint}</Field.HelperText>}
      {error && <Field.ErrorText id={`${id}-error`}>{error}</Field.ErrorText>}
    </Field.Root>
  );
}
