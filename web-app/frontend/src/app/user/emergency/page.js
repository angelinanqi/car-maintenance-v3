"use client";

import { useState } from "react";
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

  // Roadside Emergency SOP List State
  const [sops, setSops] = useState([
    {
      id: 1,
      title: "Highway Engine Breakdown SOP",
      stepsCount: 4,
      status: "Active",
      updatedAt: "1 Sep 2026",
    },
    {
      id: 2,
      title: "Flat Tire on Active Roadway",
      stepsCount: 3,
      status: "Active",
      updatedAt: "28 Aug 2026",
    },
    {
      id: 3,
      title: "Overheating Engine Protocol",
      stepsCount: 3,
      status: "Active",
      updatedAt: "15 Aug 2026",
    },
  ]);

  const [selectedSopId, setSelectedSopId] = useState(1);

  // Roadside Emergency Steps State
  const [steps, setSteps] = useState([
    {
      id: 101,
      stepNumber: 1,
      title: "Safely Pull Over & Signal Danger",
      description:
        "Turn on hazard lights immediately. Guide the vehicle onto the hard shoulder or off the main traffic lane as far right/left as safely possible.",
      imageUrl: "",
      completed: false,
    },
    {
      id: 102,
      stepNumber: 2,
      title: "Evacuate Passengers & Set Warning Triangle",
      description:
        "All occupants should exit from the non-traffic side and stand behind safety barriers. Set your reflective warning triangle 45 meters (150 feet) behind the vehicle.",
      imageUrl: "",
      completed: false,
    },
    {
      id: 103,
      stepNumber: 3,
      title: "Contact Emergency Roadside Assistance",
      description:
        "Call the highway patrol hotline or your insurance towing service. Provide your exact GPS location, nearest kilometer marker, and vehicle status.",
      imageUrl: "",
      completed: false,
    },
    {
      id: 104,
      stepNumber: 4,
      title: "Stay Clear of Traffic Until Help Arrives",
      description:
        "Do not stay inside the vehicle if pulled over on a high-speed shoulder. Wait safely behind the barrier facing oncoming traffic.",
      imageUrl: "",
      completed: false,
    },
  ]);

  // Roadside Emergency Contacts (Towing, Highway Patrol, Insurance)
  const [contacts, setContacts] = useState([
    {
      id: 1,
      name: "Highway Patrol Hotline (PLUS)",
      phone: "1-800-88-0000",
      isEditing: false,
    },
    {
      id: 2,
      name: "24/7 Towing & Recovery Service",
      phone: "+60 12-345 6789",
      isEditing: false,
    },
    {
      id: 3,
      name: "Insurance Roadside Dispatch",
      phone: "1-300-88-9999",
      isEditing: false,
    },
  ]);

  const selectedSop = sops.find((s) => s.id === selectedSopId);

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
      id: Date.now(),
      stepNumber: steps.length + 1,
      title: `Step ${steps.length + 1}: `,
      description: "",
      imageUrl: "",
      completed: false,
    };
    setSteps([...steps, newStep]);
  };

  // Contact Edit Handlers
  const handleToggleEditContact = (id) => {
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
        id: Date.now(),
        name: "New Emergency Contact",
        phone: "+60 10-000 0000",
        isEditing: true,
      },
    ]);
  };

  return (
    <AdminLayout
      title="Roadside Emergency SOPs"
      description="Breakdown Safety Runbooks & Emergency Dispatch Contacts"
    >
      <Stack gap={6}>
        {/* TOP MAIN TABS */}
        <Tabs.Root defaultValue="steps" variant="line">
          <Tabs.List mb={6}>
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
              templateColumns={{ base: "1fr", lg: "30% 70%" }}
              gap={6}
              alignContent="start"
            >
              {/* LEFT PANEL */}
              <Stack gap={4}>
                <Flex justify="space-between" align="center">
                  <Heading size="md">Playbooks</Heading>
                  {mode === "edit" && (
                    <Button size="xs" colorPalette="blue">
                      + New SOP
                    </Button>
                  )}
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
                                colorPalette={
                                  sop.status === "Active" ? "green" : "gray"
                                }
                                variant="subtle"
                                size="xs"
                              >
                                {sop.status}
                              </Badge>
                            </Flex>
                            <Text fontSize="xs" color="gray.500">
                              {sop.stepsCount} Sequential Steps
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
                  transition="all 0.2s"
                >
                  <Box>
                    <HStack gap={2}>
                      <Heading size="md">{selectedSop?.title}</Heading>
                      {mode === "incident" && (
                        <Badge colorPalette="red" variant="solid" size="sm">
                          LIVE BREAKDOWN MODE
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
                        🚨 Run Emergency Mode
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        colorPalette="whiteAlpha"
                        onClick={() => setMode("edit")}
                      >
                        Exit Emergency Mode
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
                                <Checkbox.HiddenInput />
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
                                    Step {index + 1}: {step.title}
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
                      variant="dashed"
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
              <Flex justify="space-between" align="center" mb={2}>
                <Box>
                  <Heading size="md">Emergency & Towing Contacts</Heading>
                  <Text fontSize="sm" color="gray.500">
                    24/7 Roadside assistance & highway patrol directory
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
                    <Flex justify="space-between" align="center" gap={4}>
                      {/* Left Info: Name & Phone */}
                      {contact.isEditing ? (
                        <HStack gap={4} flex={1}>
                          <Field.Root>
                            <Input
                              size="sm"
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
                        </HStack>
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
