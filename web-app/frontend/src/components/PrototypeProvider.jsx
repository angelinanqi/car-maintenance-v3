"use client";

import { createContext, useContext, useRef, useState } from "react";
import { mockProcessDocument } from "@/lib/prototypeDocuments.mjs";

const PrototypeContext = createContext(null);
// Temporary session store for admin content. Replace these collections/setters
// with persistent CRUD calls when APIs exist. Browser reload restores samples.
// Chat uses its real API separately; demo document status never changes RAG data.
export const guideCategories = [
  "Engine & Fluids",
  "Tires & Brakes",
  "General Maintenance",
];

const initialSteps = [
  {
    id: 101,
    title: "Safely Pull Over & Signal Danger",
    description:
      "Turn on hazard lights immediately. Guide the vehicle onto the hard shoulder or off the main traffic lane as far right/left as safely possible.",
    imageUrl: "",
    completed: false,
  },
  {
    id: 102,
    title: "Evacuate Passengers & Set Warning Triangle",
    description:
      "All occupants should exit from the non-traffic side and stand behind safety barriers. Set your reflective warning triangle 45 meters (150 feet) behind the vehicle.",
    imageUrl: "",
    completed: false,
  },
  {
    id: 103,
    title: "Contact Emergency Roadside Assistance",
    description:
      "Call the highway patrol hotline or your insurance towing service. Provide your exact GPS location, nearest kilometer marker, and vehicle status.",
    imageUrl: "",
    completed: false,
  },
  {
    id: 104,
    title: "Stay Clear of Traffic Until Help Arrives",
    description:
      "Do not stay inside the vehicle if pulled over on a high-speed shoulder. Wait safely behind the barrier facing oncoming traffic.",
    imageUrl: "",
    completed: false,
  },
];
// Only the first sample contains authored steps; other playbooks start empty.
const initialSops = [
  {
    id: 1,
    title: "Highway Engine Breakdown SOP",
    status: "Sample",
    updatedAt: "1 Sep 2026",
  },
  {
    id: 2,
    title: "Flat Tire on Active Roadway",
    status: "Sample",
    updatedAt: "28 Aug 2026",
  },
  {
    id: 3,
    title: "Overheating Engine Protocol",
    status: "Sample",
    updatedAt: "15 Aug 2026",
  },
].map((sop) => ({ ...sop, steps: sop.id === 1 ? initialSteps : [] }));

export function PrototypeProvider({ children }) {
  const processingIds = useRef(new Set());
  const [documents, setDocuments] = useState([
    {
      id: "sample-1",
      name: "Myvi Car Manual",
      tags: ["Manuals"],
      status: "Sample",
      date: "2026-08-15",
      file: null,
    },
    {
      id: "sample-2",
      name: "Perodua Bezza Warranty Booklet",
      tags: ["Manuals"],
      status: "Sample",
      date: "2026-08-20",
      file: null,
    },
    {
      id: "sample-3",
      name: "Emergency SOPs Proton Saga",
      tags: ["Other"],
      status: "Sample",
      date: "2026-08-28",
      file: null,
    },
  ]);
  const [cards, setCards] = useState([
    {
      id: "sample-1",
      title: "How to Check & Top Up Engine Oil",
      category: "Engine & Fluids",
      status: "Draft",
      updatedAt: "1 January 2026",
      content: "<p></p>",
    },
    {
      id: "sample-2",
      title: "Inspecting Tire Pressure and Tread Depth",
      category: "Tires & Brakes",
      status: "Draft",
      updatedAt: "14 February 2026",
      content: "<p></p>",
    },
    {
      id: "sample-3",
      title: "Replacing Your Cabin Air Filter",
      category: "General Maintenance",
      status: "Draft",
      updatedAt: "28 August 2026",
      content: "<p></p>",
    },
    {
      id: "sample-4",
      title: "Signs Your Brake Pads Need Replacement",
      category: "Tires & Brakes",
      status: "Draft",
      updatedAt: "1 September 2026",
      content: "<p></p>",
    },
  ]);

  const [sops, setSops] = useState(initialSops);
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

  // Keep jobs above the pages so navigating Home does not interrupt the demo.
  async function processDocuments(ids) {
    const selected = documents.filter(
      (document) =>
        ids.includes(document.id) && !processingIds.current.has(document.id),
    );
    for (const document of selected) processingIds.current.add(document.id);
    setDocuments((previous) =>
      previous.map((document) =>
        selected.some((item) => item.id === document.id)
          ? { ...document, status: "Processing", error: "" }
          : document,
      ),
    );
    const results = await Promise.all(
      selected.map(async (document) => {
        try {
          const result = await mockProcessDocument(document);
          setDocuments((previous) =>
            previous.map((item) =>
              item.id === document.id ? { ...item, ...result } : item,
            ),
          );
          return true;
        } catch (error) {
          setDocuments((previous) =>
            previous.map((item) =>
              item.id === document.id
                ? { ...item, status: "Failed", error: error.message }
                : item,
            ),
          );
          return false;
        } finally {
          processingIds.current.delete(document.id);
        }
      }),
    );
    return {
      succeeded: results.filter(Boolean).length,
      failed: results.filter((result) => !result).length,
    };
  }

  return (
    <PrototypeContext.Provider
      value={{
        documents,
        setDocuments,
        processDocuments,
        cards,
        setCards,
        sops,
        setSops,
        contacts,
        setContacts,
      }}
    >
      {children}
    </PrototypeContext.Provider>
  );
}

export function usePrototype() {
  return useContext(PrototypeContext);
}
