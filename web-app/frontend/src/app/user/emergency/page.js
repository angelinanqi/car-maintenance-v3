"use client";

import { useState } from "react";
import { usePrototype } from "@/components/PrototypeProvider";
import { toaster } from "@/components/ui/toaster";
import {
  Grid,
  Box,
  Heading,
  Text,
  Stack,
  Card,
  Badge,
  Button,
  Input,
  Textarea,
  HStack,
  Field,
  Flex,
  Checkbox,
  Progress,
  Tabs,
} from "@chakra-ui/react";

import AdminLayout from "../../../components/layouts/AdminLayout";

export default function SOPManagerPage() {
  const [mode, setMode] = useState("edit");

  const { sops, setSops, contacts, setContacts } = usePrototype();
  const [selectedSopId, setSelectedSopId] = useState(1);
  const selectedSop = sops.find((s) => s.id === selectedSopId);

  const steps = selectedSop.steps;
  const setSteps = (update) => {
    setSops((previous) => previous.map((sop) => sop.id === selectedSopId
      ? { ...sop, steps: typeof update === "function" ? update(sop.steps) : update }
      : sop));
  };

  const handleToggleStepComplete = (id) => {
    setSteps((prev) =>
      prev.map((step) =>
        step.id === id ? { ...step, completed: !step.completed } : step,
      ),
    );
  };

  const completedCount = steps.filter((s) => s.completed).length;
  const progressPercent =
    steps.length > 0 ? (completedCount / steps.length) * 100 : 0;

  const handleStepChange = (id, field, value) => {
    setSteps((prev) =>
      prev.map((step) => (step.id === id ? { ...step, [field]: value } : step)),
    );
  };

  const handleAddStep = () => {
    const newStep = {
      id: crypto.randomUUID(),
      title: "",
      description: "",
      imageUrl: "",
      completed: false,
    };
    setSteps((previous) => [...previous, newStep]);
  };

  // Contact Edit Handlers
  const handleToggleEditContact = (id) => {
    const contact = contacts.find((item) => item.id === id);
    if (contact.isEditing && (!contact.name.trim() || !contact.phone.trim())) {
      toaster.create({ title: "Enter a contact name and phone number", type: "error" });
      return;
    }
    if (contact.isEditing) toaster.create({ title: "Contact saved locally", type: "success" });
    setContacts((prev) =>
      prev.map((c) => (c.id === id ? { ...c, isEditing: !c.isEditing } : c)),
    );
  };

  const handleContactChange = (id, field, value) => {
    setContacts((prev) =>
      prev.map((c) => (c.id === id ? { ...c, [field]: value } : c)),
    );
  };

  const handleAddContact = () => {
    setContacts([
      ...contacts,
      {
        id: crypto.randomUUID(),
        name: "New Emergency Contact",
        phone: "",
        isEditing: true,
      },
    ]);
  };

  return (
    <AdminLayout
      title="Roadside Emergency SOPs"
      description="Sample playbooks and contacts for UI demonstration; not verified emergency guidance."
    >
      <Stack gap={6}>
        {/* TOP MAIN TABS */}
        <Tabs.Root defaultValue="steps" variant="line">
          <Tabs.List mb={6} overflowX="auto">
            <Tabs.Trigger value="steps">
              Roadside Playbooks & Steps
            </Tabs.Trigger>
            <Tabs.Trigger value="contacts">
              Emergency Contacts ({contacts.length})
            </Tabs.Trigger>
          </Tabs.List>

          {/* TAB 1: Playbooks & Steps Split Interface */}
          <Tabs.Content value="steps">
            <Grid
              templateColumns={{ base: "1fr", lg: "minmax(0, 3fr) minmax(0, 7fr)" }}
              gap={6}
              alignContent="start"
            >
              {/* LEFT PANEL */}
              <Stack gap={4}>
                <Flex justify="space-between" align="center">
                  <Heading size="md">Playbooks</Heading>

                </Flex>

                <Stack gap={3}>
                  {sops.map((sop) => {
                    const isSelected = sop.id === selectedSopId;
                    return (
                      <Card.Root
                        key={sop.id}
                        variant="outline"
                        cursor="pointer"
                        borderColor={
                          isSelected
                            ? mode === "incident"
                              ? "red.500"
                              : "blue.500"
                            : "gray.200"
                        }
                        bg={
                          isSelected
                            ? mode === "incident"
                              ? "red.50/40"
                              : "blue.50/30"
                            : "white"
                        }
                        role="button"
                        tabIndex={0}
                        aria-pressed={isSelected}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedSopId(sop.id);
                          }
                        }}
                        onClick={() => setSelectedSopId(sop.id)}
                      >
                        <Card.Body p={4}>
                          <Stack gap={2}>
                            <Flex justify="space-between" align="start" gap={2}>
                              <Text
                                fontWeight="bold"
                                fontSize="sm"
                                lineHeight="short"
                              >
                                {sop.title}
                              </Text>
                              <Badge
                                colorPalette="gray"
                                variant="subtle"
                                size="xs"
                              >
                                {sop.status}
                              </Badge>
                            </Flex>
                            <Text fontSize="xs" color="gray.500">
                              {sop.steps.length} steps
                            </Text>
                          </Stack>
                        </Card.Body>
                      </Card.Root>
                    );
                  })}
                </Stack>
              </Stack>

              {/* RIGHT PANEL */}
              <Stack gap={6}>
                <Flex
                  justify="space-between"
                  align="center"
                  bg={mode === "incident" ? "red.500" : "white"}
                  color={mode === "incident" ? "white" : "black"}
                  p={4}
                  borderRadius="md"
                  border="1px solid"
                  borderColor={mode === "incident" ? "red.600" : "gray.200"}
                  wrap="wrap"
                  gap={4}
                  transition="all 0.2s"
                >
                  <Box>
                    <HStack gap={2}>
                      <Heading size="md">{selectedSop?.title}</Heading>
                      {mode === "incident" && (
                        <Badge colorPalette="red" variant="solid" size="sm">
                          CHECKLIST PREVIEW
                        </Badge>
                      )}
                    </HStack>
                    <Text
                      fontSize="xs"
                      color={mode === "incident" ? "red.100" : "gray.500"}
                      mt={1}
                    >
                      Last updated on {selectedSop?.updatedAt}
                    </Text>
                  </Box>

                  <HStack gap={2}>
                    {mode === "edit" ? (
                      <Button
                        size="sm"
                        colorPalette="red"
                        onClick={() => setMode("incident")}
                      >
                        Preview Checklist
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        color="white"
                        borderColor="white"
                        onClick={() => setMode("edit")}
                      >
                        Back to Editing
                      </Button>
                    )}
                  </HStack>
                </Flex>

                {mode === "incident" && (
                  <Card.Root variant="outline" bg="white" borderColor="red.200">
                    <Card.Body p={4}>
                      <Stack gap={2}>
                        <Flex justify="space-between" align="center">
                          <Text fontSize="sm" fontWeight="bold">
                            Safety Execution Progress: {completedCount} /{" "}
                            {steps.length} Steps Completed
                          </Text>
                          <Text fontSize="sm" fontWeight="bold" color="red.600">
                            {Math.round(progressPercent)}%
                          </Text>
                        </Flex>
                        <Progress.Root
                          value={progressPercent}
                          colorPalette="red"
                          size="md"
                        >
                          <Progress.Track>
                            <Progress.Range />
                          </Progress.Track>
                        </Progress.Root>
                      </Stack>
                    </Card.Body>
                  </Card.Root>
                )}

                <Stack gap={4}>
                  {steps.length === 0 && <Text color="gray.600" p={4}>No steps yet. Add steps in editing mode.</Text>}
                  {steps.map((step, index) => {
                    if (mode === "incident") {
                      return (
                        <Card.Root
                          key={step.id}
                          variant="outline"
                          bg={step.completed ? "green.50/40" : "white"}
                          borderColor={
                            step.completed ? "green.300" : "gray.200"
                          }
                        >
                          <Card.Body p={4}>
                            <Flex align="start" gap={3}>
                              <Checkbox.Root
                                checked={step.completed}
                                onCheckedChange={() =>
                                  handleToggleStepComplete(step.id)
                                }
                                size="lg"
                                colorPalette="green"
                                mt={1}
                              >
                                <Checkbox.HiddenInput aria-label={"Complete step " + (index + 1)} />
                                <Checkbox.Control />
                              </Checkbox.Root>

                              <Stack gap={2} flex={1}>
                                <HStack justify="space-between">
                                  <Text
                                    fontWeight="bold"
                                    fontSize="md"
                                    textDecoration={
                                      step.completed ? "line-through" : "none"
                                    }
                                    color={
                                      step.completed ? "gray.500" : "black"
                                    }
                                  >
                                    Step {index + 1}: {step.title || "Untitled step"}
                                  </Text>
                                  {step.completed && (
                                    <Badge colorPalette="green" variant="solid">
                                      DONE
                                    </Badge>
                                  )}
                                </HStack>

                                <Text
                                  fontSize="sm"
                                  color="gray.700"
                                  whiteSpace="pre-wrap"
                                >
                                  {step.description}
                                </Text>

                                {step.imageUrl && (
                                  <Box mt={2}>
                                    <img
                                      src={step.imageUrl}
                                      alt={`Step ${index + 1}`}
                                      style={{
                                        maxWidth: "100%",
                                        borderRadius: "6px",
                                      }}
                                    />
                                  </Box>
                                )}
                              </Stack>
                            </Flex>
                          </Card.Body>
                        </Card.Root>
                      );
                    }

                    return (
                      <Card.Root key={step.id} variant="outline" bg="white">
                        <Card.Body p={5}>
                          <Stack gap={4}>
                            <Flex align="center" gap={3}>
                              <Badge
                                colorPalette="blue"
                                variant="solid"
                                borderRadius="full"
                                px={3}
                                py={1}
                              >
                                Step {index + 1}
                              </Badge>
                              <Input
                                size="sm"
                                fontWeight="semibold"
                                aria-label={"Step " + (index + 1) + " title"}
                                placeholder="Step title"
                                value={step.title}
                                onChange={(e) =>
                                  handleStepChange(
                                    step.id,
                                    "title",
                                    e.target.value,
                                  )
                                }
                              />
                            </Flex>

                            <Field.Root>
                              <Textarea
                                size="sm"
                                rows={3}
                                aria-label={"Step " + (index + 1) + " description"}
                                value={step.description}
                                onChange={(e) =>
                                  handleStepChange(
                                    step.id,
                                    "description",
                                    e.target.value,
                                  )
                                }
                              />
                            </Field.Root>
                          </Stack>
                        </Card.Body>
                      </Card.Root>
                    );
                  })}

                  {mode === "edit" && (
                    <Button
                      variant="outline"
                      border="2px dashed"
                      borderColor="gray.300"
                      onClick={handleAddStep}
                      w="100%"
                    >
                      + Add Step {steps.length + 1}
                    </Button>
                  )}
                </Stack>
              </Stack>
            </Grid>
          </Tabs.Content>

          {/* TAB 2: Emergency Contacts List */}
          <Tabs.Content value="contacts">
            <Stack gap={4} maxW="800px">
              {/* Header Row */}
              <Flex justify="space-between" align="center" mb={2} wrap="wrap" gap={3}>
                <Box>
                  <Heading size="md">Emergency & Towing Contacts</Heading>
                  <Text fontSize="sm" color="gray.500">
                    Sample contact details. Replace these with your own verified contacts.
                  </Text>
                </Box>
                <Button
                  size="sm"
                  colorPalette="blue"
                  onClick={handleAddContact}
                >
                  + Add Contact
                </Button>
              </Flex>

              {/* Contact Cards List */}
              {contacts.map((contact) => (
                <Card.Root key={contact.id} variant="outline" bg="white">
                  <Card.Body p={4}>
                    <Flex justify="space-between" align="center" gap={4} wrap="wrap">
                      {/* Left Info: Name & Phone */}
                      {contact.isEditing ? (
                        <Stack direction={{ base: "column", md: "row" }} gap={4} flex={1}>
                          <Field.Root>
                            <Input
                              size="sm"
                              aria-label="Contact name"
                              placeholder="Service / Contact Name"
                              value={contact.name}
                              onChange={(e) =>
                                handleContactChange(
                                  contact.id,
                                  "name",
                                  e.target.value,
                                )
                              }
                            />
                          </Field.Root>

                          <Field.Root>
                            <Input
                              size="sm"
                              aria-label="Contact phone number"
                              placeholder="Phone / Hotline Number"
                              value={contact.phone}
                              onChange={(e) =>
                                handleContactChange(
                                  contact.id,
                                  "phone",
                                  e.target.value,
                                )
                              }
                            />
                          </Field.Root>
                        </Stack>
                      ) : (
                        <Box flex={1}>
                          <Text fontWeight="bold" fontSize="md">
                            {contact.name}
                          </Text>
                          <Text fontSize="sm" color="gray.600" mt={0.5}>
                            {contact.phone}
                          </Text>
                        </Box>
                      )}

                      {/* Right Action: Edit / Save Toggle */}
                      <Button
                        size="sm"
                        variant={contact.isEditing ? "solid" : "outline"}
                        colorPalette={contact.isEditing ? "blue" : "gray"}
                        onClick={() => handleToggleEditContact(contact.id)}
                      >
                        {contact.isEditing ? "Save" : "Edit"}
                      </Button>
                    </Flex>
                  </Card.Body>
                </Card.Root>
              ))}
            </Stack>
          </Tabs.Content>
        </Tabs.Root>
      </Stack>
    </AdminLayout>
  );
}
