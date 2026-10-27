"use client";

import { useEffect, useState } from "react";
import { request, listAll } from "@/api/client.mjs";
import {
  loadCatalogue,
  loadItems,
  type Vehicle,
  type MaintenanceItem,
  type SourceDocument,
} from "@/api/admin";

export default function useScheduleResources(reloadKey: number) {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [items, setItems] = useState<MaintenanceItem[]>([]);
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [links, setLinks] = useState<
    { vehicle_id: string; document_id: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      loadCatalogue(),
      loadItems(),
      listAll("/documents"),
      request("/knowledge/manage"),
    ])
      .then(([catalogue, items, documents, knowledge]) => {
        if (active) {
          setVehicles(catalogue.vehicles);
          setItems(items);
          setDocuments(documents);
          setLinks(knowledge.document_vehicles);
        }
      })
      .catch((cause) => {
        if (active) setError(cause.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reloadKey]);

  return { vehicles, items, setItems, documents, links, loading, error };
}
