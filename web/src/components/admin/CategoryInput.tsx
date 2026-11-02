"use client";

import {
  Combobox,
  createListCollection,
  useFieldContext,
  type InputProps,
} from "@chakra-ui/react";

type Props = Pick<
  InputProps,
  "id" | "aria-describedby" | "aria-invalid" | "placeholder" | "disabled" | "maxLength"
> & {
  value: string;
  options: string[];
  onChange: (value: string) => void;
};

export default function CategoryInput({
  value,
  options,
  onChange,
  disabled,
  id,
  ...props
}: Props) {
  const field = useFieldContext();
  const collection = createListCollection({
    items: options.filter((option) =>
      option.toLowerCase().includes(value.toLowerCase()),
    ),
  });
  return (
    <Combobox.Root
      collection={collection}
      allowCustomValue
      disabled={disabled ?? field?.disabled}
      ids={{ input: id ?? field?.ids.control, label: field?.ids.label }}
      inputValue={value}
      onInputValueChange={({ inputValue }) => onChange(inputValue)}
      positioning={{ strategy: "fixed", hideWhenDetached: true }}
    >
      <Combobox.Control>
        <Combobox.Input {...props} bg="white" minH="44px" />
        <Combobox.IndicatorGroup>
          <Combobox.Trigger />
        </Combobox.IndicatorGroup>
      </Combobox.Control>
      <Combobox.Positioner>
        <Combobox.Content>
          <Combobox.Empty>Type a new category name.</Combobox.Empty>
          {collection.items.map((option) => (
            <Combobox.Item key={option} item={option}>
              <Combobox.ItemText>{option}</Combobox.ItemText>
              <Combobox.ItemIndicator />
            </Combobox.Item>
          ))}
        </Combobox.Content>
      </Combobox.Positioner>
    </Combobox.Root>
  );
}
