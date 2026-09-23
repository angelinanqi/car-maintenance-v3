"use client";

import { useState } from "react";
import { usePrototype } from "@/components/PrototypeProvider";
import { toaster } from "@/components/ui/toaster";
import EmergencyContact from "@/components/EmergencyContact";
import DeleteConfirmModal from "@/components/modals/DeleteConfirmModal";
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
  const [completedIds, setCompletedIds] = useState([]);
  const [newContact, setNewContact] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);

  const { sops, setSops, contacts, setContacts } = usePrototype();
  const [selectedSopId, setSelectedSopId] = useState(1);
  const selectedSop = sops.find((s) => s.id === selectedSopId);

  const steps = selectedSop.steps.map((step) => ({
    ...step,
    completed: completedIds.includes(step.id),
  }));
  const setSteps = (update) => {
    setSops((previous) =>
      previous.map((sop) =>
        sop.id === selectedSopId
          ? {
              ...sop,
              status: "Edited locally",
              updatedAt: new Date().toLocaleDateString("en-GB"),
              steps: typeof update === "function" ? update(sop.steps) : update,
            }
          : sop,
      ),
    );
  };

  const handleToggleStepComplete = (id) => {
    setCompletedIds((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : [...previous, id],
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

  const handleAddContact = () => {
    setNewContact({ id: crypto.randomUUID(), name: "", phone: "" });
  };

  function moveStep(index, direction) {
    setSteps((previous) => {
      const next = [...previous];
      const target = index + direction;
      if (target < 0 || target >= next.length) return previous;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function previewChecklist() {
    if (
      !steps.length ||
      steps.some(
        (step) =>
          !step.title.trim() ||
          !step.description.trim() ||
          (step.imageUrl && !/^https?:\/\//i.test(step.imageUrl)),
      )
    ) {
      toaster.create({
        title:
          "Add a title and description for every step; images need an http(s) URL",
        type: "error",
      });
      return;
    }
    setMode("incident");
  }

  return (
    <AdminLayout
      title="Roadside Emergency SOPs"
      description="Sample playbooks and contacts for UI demonstration; not verified emergency guidance."
    >
      <Stack gap={6}>
        <Text fontSize="sm" color="gray.600">
          Instruction edits are saved immediately in this tab. Checklist
          progress is a separate preview and resets when you leave this page.
        </Text>
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
              templateColumns={{
                base: "1fr",
                lg: "minmax(0, 3fr) minmax(0, 7fr)",
              }}
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
                            setMode("edit");
                          }
                        }}
                        onClick={() => {
                          setSelectedSopId(sop.id);
                          setMode("edit");
                        }}
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
                        onClick={previewChecklist}
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
                    {mode === "incident" && (
                      <Button
                        size="sm"
                        onClick={() =>
                          setCompletedIds((previous) =>
                            previous.filter(
                              (id) => !steps.some((step) => step.id === id),
                            ),
                          )
                        }
                      >
                        Reset checklist
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
                  {steps.length === 0 && (
                    <Text color="gray.600" p={4}>
                      No steps yet. Add steps in editing mode.
                    </Text>
                  )}
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
                                <Checkbox.HiddenInput
                                  aria-label={"Complete step " + (index + 1)}
                                />
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
                                    Step {index + 1}:{" "}
                                    {step.title || "Untitled step"}
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

                                {/^https?:\/\//i.test(step.imageUrl) && (
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
                                aria-label={
                                  "Step " + (index + 1) + " description"
                                }
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
                            <Field.Root>
                              <Field.Label>Image URL (optional)</Field.Label>
                              <Input
                                aria-label={`Step ${index + 1} image URL`}
                                placeholder="https://..."
                                value={step.imageUrl}
                                onChange={(event) =>
                                  handleStepChange(
                                    step.id,
                                    "imageUrl",
                                    event.target.value,
                                  )
                                }
                              />
                            </Field.Root>
                            <HStack>
                              <Button
                                size="xs"
                                variant="outline"
                                disabled={index === 0}
                                onClick={() => moveStep(index, -1)}
                              >
                                Move up
                              </Button>
                              <Button
                                size="xs"
                                variant="outline"
                                disabled={index === steps.length - 1}
                                onClick={() => moveStep(index, 1)}
                              >
                                Move down
                              </Button>
                              <Button
                                size="xs"
                                variant="outline"
                                colorPalette="red"
                                onClick={() =>
                                  setDeleteItem({
                                    type: "step",
                                    id: step.id,
                                    name: step.title || `Step ${index + 1}`,
                                    sopId: selectedSopId,
                                  })
                                }
                              >
                                Remove step
                              </Button>
                            </HStack>
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
              <Flex
                justify="space-between"
                align="center"
                mb={2}
                wrap="wrap"
                gap={3}
              >
                <Box>
                  <Heading size="md">Emergency & Towing Contacts</Heading>
                  <Text fontSize="sm" color="gray.500">
                    Sample contact details. Replace these with your own verified
                    contacts.
                  </Text>
                </Box>
                <Button
                  size="sm"
                  colorPalette="blue"
                  onClick={handleAddContact}
                  disabled={Boolean(newContact)}
                >
                  + Add Contact
                </Button>
              </Flex>

              {/* Contact Cards List */}
              {contacts.length === 0 && !newContact && (
                <Text>No contacts yet. Add a verified contact.</Text>
              )}
              {contacts.map((contact) => (
                <EmergencyContact
                  key={contact.id}
                  contact={contact}
                  onSave={(saved) => {
                    setContacts((previous) =>
                      previous.map((item) =>
                        item.id === saved.id ? saved : item,
                      ),
                    );
                    toaster.create({
                      title: "Contact saved locally",
                      type: "success",
                    });
                  }}
                  onDelete={() =>
                    setDeleteItem({
                      type: "contact",
                      id: contact.id,
                      name: contact.name,
                    })
                  }
                />
              ))}
              {newContact && (
                <EmergencyContact
                  key={newContact.id}
                  contact={newContact}
                  isNew
                  onCancel={() => setNewContact(null)}
                  onSave={(saved) => {
                    setContacts((previous) => [...previous, saved]);
                    setNewContact(null);
                    toaster.create({
                      title: "Contact added locally",
                      type: "success",
                    });
                  }}
                />
              )}
            </Stack>
          </Tabs.Content>
        </Tabs.Root>
      </Stack>
      <DeleteConfirmModal
        isOpen={Boolean(deleteItem)}
        itemName={deleteItem?.name}
        onClose={() => setDeleteItem(null)}
        onConfirm={() => {
          if (deleteItem.type === "contact")
            setContacts((previous) =>
              previous.filter((contact) => contact.id !== deleteItem.id),
            );
          else {
            setSops((previous) =>
              previous.map((sop) =>
                sop.id === deleteItem.sopId
                  ? {
                      ...sop,
                      status: "Edited locally",
                      updatedAt: new Date().toLocaleDateString("en-GB"),
                      steps: sop.steps.filter(
                        (step) => step.id !== deleteItem.id,
                      ),
                    }
                  : sop,
              ),
            );
            setCompletedIds((previous) =>
              previous.filter((id) => id !== deleteItem.id),
            );
          }
          setDeleteItem(null);
          toaster.create({ title: "Removed locally", type: "success" });
        }}
      />
    </AdminLayout>
  );
}
