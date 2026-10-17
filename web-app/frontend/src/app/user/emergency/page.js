"use client";

import { useState } from "react";
import { useContent } from "@/components/ContentProvider";
import { toaster } from "@/components/ui/toaster";
import EmergencyContact from "@/components/EmergencyContact";
import DeleteConfirmModal from "@/components/modals/DeleteConfirmModal";
import useUnsavedChanges from "@/components/admin/useUnsavedChanges";
import CategoryInput from "@/components/admin/CategoryInput";
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
  Image,
  Fieldset,
} from "@chakra-ui/react";

import AdminLayout from "../../../components/layouts/AdminLayout";

export default function SOPManagerPage() {
  const [mode, setMode] = useState("edit");
  const [completedIds, setCompletedIds] = useState([]);
  const [newContact, setNewContact] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);

  const {
    sops,
    contacts,
    savePlaybook,
    publishPlaybook,
    deletePlaybook,
    saveContact,
    deleteContact,
  } = useContent();
  const [draft, setDraft] = useState(null);
  useUnsavedChanges(Boolean(draft));
  const [saving, setSaving] = useState(false);
  const [selectedSopId, setSelectedSopId] = useState(null);
  const [query, setQuery] = useState("");
  const selectedSop =
    draft || sops.find((s) => s.id === selectedSopId) || sops[0];

  const steps = (selectedSop?.steps || []).map((step) => ({
    ...step,
    completed: completedIds.includes(step.id),
  }));
  const setSteps = (update) => {
    if (!selectedSop) return;
    setDraft((previous) => {
      const current = previous || selectedSop;
      return {
        ...current,
        steps: typeof update === "function" ? update(current.steps) : update,
      };
    });
  };
  function editPlaybook(field, value) {
    setDraft((previous) => ({ ...(previous || selectedSop), [field]: value }));
  }

  function selectPlaybook(sop) {
    if (saving) return;
    if (draft && !window.confirm("Discard unsaved playbook changes?")) return;
    setDraft(null);
    setSelectedSopId(sop.id);
    setMode("edit");
  }

  async function persistPlaybook(unpublish = false) {
    if (!selectedSop || saving) return;
    if (!selectedSop.title.trim()) {
      toaster.create({
        title: "Enter a playbook title before saving.",
        type: "error",
      });
      return;
    }
    if (
      !Number.isInteger(selectedSop.display_order ?? 0) ||
      (selectedSop.display_order ?? 0) < 0
    ) {
      toaster.create({
        title: "Display order must be a non-negative whole number.",
        type: "error",
      });
      return;
    }
    if (
      selectedSop.scenario_key &&
      !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(selectedSop.scenario_key.trim())
    ) {
      toaster.create({
        title:
          "Use lowercase words separated by hyphens for the scenario key, for example minor-accident.",
        type: "error",
      });
      return;
    }
    if (
      selectedSop.steps.some(
        (step) =>
          !step.title.trim() ||
          !step.description.trim() ||
          (step.imageUrl && !/^https?:\/\//i.test(step.imageUrl)),
      )
    ) {
      toaster.create({
        title:
          "Each step needs a title and description. Image links must start with http:// or https://.",
        type: "error",
      });
      return;
    }
    setSaving(true);
    try {
      const saved = await savePlaybook(selectedSop.id, {
        title: selectedSop.title,
        display_order: selectedSop.display_order || 0,
        scenario_key: selectedSop.scenario_key?.trim() || null,
        source: selectedSop.source || "",
        category: selectedSop.category || "",
        description: selectedSop.description || "",
        safety_warnings: selectedSop.safety_warnings || "",
        ...(unpublish === true ? { status: "draft" } : {}),
        steps: selectedSop.steps.map(
          ({ id, title, description, imageUrl }) => ({
            id,
            title,
            description,
            imageUrl,
          }),
        ),
      });
      setSelectedSopId(saved.id);
      setDraft(null);
      toaster.create({ title: "Playbook saved", type: "success" });
    } catch (error) {
      toaster.create({ title: error.message, type: "error" });
    } finally {
      setSaving(false);
    }
  }

  async function reviewAndPublish() {
    if (!selectedSop?.id || draft) return;
    if (
      !window.confirm(
        "Confirm that these instructions and their source have been reviewed and are ready for public use?",
      )
    )
      return;
    setSaving(true);
    try {
      await publishPlaybook(selectedSop.id);
      toaster.create({ title: "Reviewed playbook published", type: "success" });
    } catch (error) {
      toaster.create({ title: error.message, type: "error" });
    } finally {
      setSaving(false);
    }
  }

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
      title="Emergency & contacts"
      description="Manage published playbooks, ordered steps, and shared contacts."
    >
      <Fieldset.Root disabled={saving}>
        <Stack gap={6}>
          <Text fontSize="sm" color="gray.600">
            Save edits, then review and publish. Mobile downloads update in
            Offline guides; withdrawals take effect after the next online
            refresh. Checklist progress is a preview.
          </Text>
          {/* TOP MAIN TABS */}
          <Tabs.Root defaultValue="steps" variant="line">
            <Tabs.List mb={6} overflowX="auto">
              <Tabs.Trigger value="steps">Playbooks & steps</Tabs.Trigger>
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
                    <Heading as="h2" size="md">
                      Playbooks
                    </Heading>
                    <Button
                      size="sm"
                      disabled={saving}
                      onClick={() => {
                        if (
                          draft &&
                          !window.confirm("Discard unsaved changes?")
                        )
                          return;
                        setDraft({ title: "", steps: [] });
                        setMode("edit");
                      }}
                    >
                      New playbook
                    </Button>
                  </Flex>
                  <Box as="label">
                    Search playbooks
                    <Input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Title or category"
                    />
                  </Box>

                  <Stack gap={3}>
                    {sops
                      .filter((sop) =>
                        `${sop.title} ${sop.category || ""}`
                          .toLowerCase()
                          .includes(query.toLowerCase()),
                      )
                      .map((sop) => {
                        const isSelected = sop.id === selectedSop?.id;
                        return (
                          <Card.Root
                            key={sop.id}
                            variant="outline"
                            cursor="pointer"
                            borderColor={
                              isSelected
                                ? mode === "incident"
                                  ? "red.500"
                                  : "brand.600"
                                : "gray.200"
                            }
                            bg={
                              isSelected
                                ? mode === "incident"
                                  ? "red.50/40"
                                  : "brand.50"
                                : "white"
                            }
                            role="button"
                            tabIndex={0}
                            aria-pressed={isSelected}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                selectPlaybook(sop);
                              }
                            }}
                            onClick={() => {
                              selectPlaybook(sop);
                            }}
                          >
                            <Card.Body p={4}>
                              <Stack gap={2}>
                                <Flex
                                  justify="space-between"
                                  align="start"
                                  gap={2}
                                >
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
                                <Text fontSize="sm" color="muted">
                                  {sop.steps.length} steps
                                </Text>
                              </Stack>
                            </Card.Body>
                          </Card.Root>
                        );
                      })}
                    {!sops.some((sop) =>
                      `${sop.title} ${sop.category || ""}`
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                    ) && (
                      <Text color="muted">
                        {sops.length
                          ? "No playbooks match your search."
                          : "No playbooks yet. Create one to add reviewed guidance for Roadie."}
                      </Text>
                    )}
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
                      <HStack gap={2} wrap="wrap">
                        {mode === "edit" && selectedSop ? (
                          <Input
                            aria-label="Playbook title"
                            placeholder="Playbook title"
                            value={selectedSop.title}
                            onChange={(event) =>
                              editPlaybook("title", event.target.value)
                            }
                          />
                        ) : (
                          <Heading size="md">
                            {selectedSop?.title || "Create a playbook to begin"}
                          </Heading>
                        )}
                        {mode === "incident" && (
                          <Badge colorPalette="red" variant="solid" size="sm">
                            CHECKLIST PREVIEW
                          </Badge>
                        )}
                      </HStack>
                      <Text
                        fontSize="sm"
                        color={mode === "incident" ? "red.100" : "gray.500"}
                        mt={1}
                      >
                        Last updated on {selectedSop?.updatedAt}
                      </Text>
                    </Box>

                    <HStack gap={2} wrap="wrap">
                      {mode === "edit" && selectedSop && (
                        <>
                          <Button
                            size="sm"
                            loading={saving}
                            onClick={() => persistPlaybook()}
                          >
                            Save Playbook
                          </Button>
                          {selectedSop.id &&
                            selectedSop.status !== "published" && (
                              <Button
                                size="sm"
                                disabled={saving || Boolean(draft)}
                                onClick={reviewAndPublish}
                              >
                                Review and publish
                              </Button>
                            )}
                          {selectedSop.status === "published" && (
                            <Button
                              size="sm"
                              disabled={saving}
                              onClick={() => persistPlaybook(true)}
                            >
                              Unpublish
                            </Button>
                          )}
                          {selectedSop.id && (
                            <Button
                              size="sm"
                              colorPalette="red"
                              variant="outline"
                              onClick={() =>
                                setDeleteItem({
                                  type: "playbook",
                                  id: selectedSop.id,
                                  name: selectedSop.title,
                                })
                              }
                            >
                              Remove playbook
                            </Button>
                          )}
                        </>
                      )}
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

                  {mode === "edit" && selectedSop && (
                    <Stack gap={3}>
                      <Field.Root>
                        <Field.Label>Display order</Field.Label>
                        <Input
                          type="number"
                          min={0}
                          step={1}
                          value={selectedSop.display_order || 0}
                          onChange={(event) =>
                            editPlaybook(
                              "display_order",
                              Number(event.target.value),
                            )
                          }
                        />
                        <Field.HelperText>
                          Lower numbers appear first in the mobile guide
                          catalogue.
                        </Field.HelperText>
                      </Field.Root>
                      <Field.Root>
                        <Field.Label>Emergency category</Field.Label>
                        <CategoryInput
                          options={[
                            ...new Set(
                              sops.map((sop) => sop.category).filter(Boolean),
                            ),
                          ]}
                          value={selectedSop.category || ""}
                          onChange={(category) =>
                            editPlaybook("category", category)
                          }
                        />
                      </Field.Root>
                      <Field.Root>
                        <Field.Label>Situation description</Field.Label>
                        <Textarea
                          value={selectedSop.description || ""}
                          onChange={(event) =>
                            editPlaybook("description", event.target.value)
                          }
                        />
                      </Field.Root>
                      <Field.Root>
                        <Field.Label>Safety warnings</Field.Label>
                        <Textarea
                          value={selectedSop.safety_warnings || ""}
                          onChange={(event) =>
                            editPlaybook("safety_warnings", event.target.value)
                          }
                        />
                      </Field.Root>
                      <Field.Root>
                        <Field.Label>Scenario key</Field.Label>
                        <Input
                          placeholder="minor-accident"
                          value={selectedSop.scenario_key || ""}
                          onChange={(event) =>
                            editPlaybook("scenario_key", event.target.value)
                          }
                        />
                        <Field.HelperText>
                          Use breakdown for general car trouble or
                          minor-accident for the accident route. Other unique
                          keys appear under car trouble. Matching keys replace
                          the bundled scenario after download.
                        </Field.HelperText>
                      </Field.Root>
                      <Field.Root>
                        <Field.Label>Source / review reference</Field.Label>
                        <Textarea
                          value={selectedSop.source || ""}
                          onChange={(event) =>
                            editPlaybook("source", event.target.value)
                          }
                        />
                      </Field.Root>
                      <Text fontSize="sm">
                        {selectedSop.reviewed_at
                          ? `Reviewed ${new Date(selectedSop.reviewed_at).toLocaleString()}`
                          : "Review required before publication."}{" "}
                        Editing published instructions returns them to draft
                        when saved.
                      </Text>
                    </Stack>
                  )}
                  {mode !== "edit" && selectedSop && (
                    <Stack gap={2}>
                      <Text fontWeight="semibold">{selectedSop.category}</Text>
                      <Text>{selectedSop.description}</Text>
                      {selectedSop.safety_warnings && (
                        <Box bg="orange.50" p={3}>
                          <Text fontWeight="semibold">Safety warnings</Text>
                          <Text whiteSpace="pre-wrap">
                            {selectedSop.safety_warnings}
                          </Text>
                        </Box>
                      )}
                    </Stack>
                  )}
                  {mode === "incident" && (
                    <Card.Root
                      variant="outline"
                      bg="white"
                      borderColor="red.200"
                    >
                      <Card.Body p={4}>
                        <Stack gap={2}>
                          <Flex justify="space-between" align="center">
                            <Text fontSize="sm" fontWeight="bold">
                              Safety Execution Progress: {completedCount} /{" "}
                              {steps.length} Steps Completed
                            </Text>
                            <Text
                              fontSize="sm"
                              fontWeight="bold"
                              color="red.600"
                            >
                              {Math.round(progressPercent)}%
                            </Text>
                          </Flex>
                          <Progress.Root
                            value={progressPercent}
                            colorPalette="red"
                            size="md"
                          >
                            <Progress.Label srOnly>
                              Checklist preview progress
                            </Progress.Label>
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
                                  <Checkbox.Control>
                                    <Checkbox.Indicator />
                                  </Checkbox.Control>
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
                                      <Badge
                                        colorPalette="green"
                                        variant="solid"
                                      >
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
                                      <Image
                                        src={step.imageUrl}
                                        alt={step.title || `Step ${index + 1}`}
                                        loading="lazy"
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
                                  colorPalette="brand"
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
                        disabled={!selectedSop}
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
                    <Text fontSize="sm" color="muted">
                      Manage shared emergency and roadside contacts.
                    </Text>
                  </Box>
                  <Button
                    size="sm"
                    colorPalette="brand"
                    onClick={handleAddContact}
                    disabled={Boolean(newContact)}
                  >
                    + Add Contact
                  </Button>
                </Flex>

                {/* Contact Cards List */}
                {contacts.length === 0 && !newContact && (
                  <Text>No contacts yet. Add a shared contact.</Text>
                )}
                {contacts.map((contact) => (
                  <EmergencyContact
                    key={contact.id}
                    contact={contact}
                    onSave={async (saved) => {
                      await saveContact(saved.id, {
                        name: saved.name,
                        phone: saved.phone,
                        description: saved.description,
                        display_order: saved.display_order,
                      });
                      toaster.create({
                        title: "Contact saved",
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
                    onSave={async (saved) => {
                      await saveContact(null, {
                        name: saved.name,
                        phone: saved.phone,
                        description: saved.description,
                        display_order: saved.display_order,
                      });
                      setNewContact(null);
                      toaster.create({
                        title: "Contact added",
                        type: "success",
                      });
                    }}
                  />
                )}
              </Stack>
            </Tabs.Content>
          </Tabs.Root>
        </Stack>
      </Fieldset.Root>
      <DeleteConfirmModal
        isOpen={Boolean(deleteItem)}
        itemName={deleteItem?.name}
        onClose={() => setDeleteItem(null)}
        onConfirm={async () => {
          try {
            if (deleteItem.type === "playbook") {
              await deletePlaybook(deleteItem.id);
              setDraft(null);
              setSelectedSopId(null);
            } else if (deleteItem.type === "step") {
              setSteps((previous) =>
                previous.filter((step) => step.id !== deleteItem.id),
              );
            } else {
              await deleteContact(deleteItem.id);
            }
            setDeleteItem(null);
            toaster.create({
              title:
                deleteItem.type === "step"
                  ? "Step removed from draft; save the playbook to persist"
                  : "Record removed",
              type: "success",
            });
          } catch (error) {
            toaster.create({ title: error.message, type: "error" });
          }
        }}
      />
    </AdminLayout>
  );
}
