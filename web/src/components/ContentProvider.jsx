"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import * as documentsApi from "@/api/documents.mjs";
import * as guidesApi from "@/api/guides.mjs";
import * as categoriesApi from "@/api/categories.mjs";
import * as emergencyApi from "@/api/emergency.mjs";
import { request, listAll } from "@/api/client.mjs";
import { CONTENT_POLL_MS, DOCUMENT_BATCH_LIMIT } from "@/lib/config.mjs";

const ContentContext = createContext(null);
const empty = {
  documents: [],
  cards: [],
  categories: [],
  sops: [],
  contacts: [],
  dashboard: null,
  configuration: null,
  knowledge: null,
  scheduleDrafts: [],
  reviewQuestions: [],
};
const date = (value) => new Date(value).toLocaleDateString("en-GB");

export function ContentProvider({ children }) {
  const [data, setData] = useState(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const resourceVersions = useRef({});
  const resourceErrors = useRef({});
  const refresh = useCallback(
    async ({ documentsOnly = false, resources = null } = {}) => {
      const version = ++generation.current;
      const fetchers = {
        documents: documentsApi.listDocuments,
        dashboard: () => request("/dashboard"),
        configuration: () => request("/config"),
        knowledge: () => request("/knowledge/manage"),
        scheduleDrafts: () => listAll("/admin/schedule-drafts"),
        reviewQuestions: () =>
          listAll("/admin/review-questions", { status: "open" }),
        cards: guidesApi.listGuides,
        categories: categoriesApi.listCategories,
        sops: emergencyApi.listPlaybooks,
        contacts: emergencyApi.listContacts,
      };
      const wanted = documentsOnly
        ? [
            "documents",
            "dashboard",
            "configuration",
            "knowledge",
            "reviewQuestions",
          ]
        : resources;
      const entries = Object.entries(fetchers).filter(
        ([name]) => !wanted || wanted.includes(name),
      );
      entries.forEach(([name]) => {
        resourceVersions.current[name] = version;
      });
      const results = await Promise.allSettled(
        entries.map(([, fetch]) => fetch()),
      );
      if (!entries.some(([name]) => resourceVersions.current[name] === version))
        return "";
      const updates = {};
      results.forEach((result, index) => {
        const name = entries[index][0];
        if (resourceVersions.current[name] !== version) return;
        if (result.status === "fulfilled") {
          updates[name] = result.value;
          delete resourceErrors.current[name];
        } else resourceErrors.current[name] = result.reason.message;
      });
      setData((previous) => {
        const next = { ...previous, ...updates };
        if (updates.documents)
          next.documents = next.documents.map((item) => ({
            ...item,
            date: date(item.created_at),
          }));
        if (updates.cards || updates.categories)
          next.cards = next.cards.map((item) => ({
            ...item,
            category:
              next.categories.find((cat) => cat.id === item.category_id)
                ?.name || "Uncategorized",
            updatedAt: date(item.updated_at),
          }));
        if (updates.sops)
          next.sops = next.sops.map((item) => ({
            ...item,
            updatedAt: date(item.updated_at),
          }));
        return next;
      });
      const message = Object.entries(resourceErrors.current)
        .map(([name, detail]) => `${name}: ${detail}`)
        .join("; ");
      setError(message);
      setLoading(false);
      return message;
    },
    [],
  );

  useEffect(() => {
    let mounted = true;
    Promise.resolve().then(() => {
      if (mounted) refresh();
    });
    return () => {
      mounted = false;
      resourceVersions.current = {};
    };
  }, [refresh]);
  const processing = data.documents.some((item) =>
    ["processing", "awaiting_index"].includes(item.status),
  );
  useEffect(() => {
    if (!processing) return;
    let stopped = false;
    let timer;
    async function poll() {
      await refresh({ documentsOnly: true });
      if (!stopped) timer = setTimeout(poll, CONTENT_POLL_MS);
    }
    timer = setTimeout(poll, CONTENT_POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [processing, refresh]);

  async function mutate(action, resources) {
    const result = await action();
    const warning = await refresh({
      resources: [...resources, "dashboard", "configuration", "knowledge"],
    });
    if (warning)
      setError(
        `Saved successfully, but some data could not be refreshed. ${warning}`,
      );
    return result;
  }

  async function saveDocument(editItem, { files, ...metadata }) {
    let saved;
    try {
      if (editItem) {
        saved = await documentsApi.editDocument(editItem.id, metadata);
        if (files[0]) await documentsApi.replaceDocument(editItem.id, files[0]);
      } else {
        const uploadedFiles = [];
        try {
          for (const file of files) {
            saved = await documentsApi.uploadDocument(file, {
              ...metadata,
              name: files.length === 1 ? metadata.name : file.name,
            });
            uploadedFiles.push(file);
          }
        } catch (error) {
          error.uploadedFiles = uploadedFiles;
          throw error;
        }
      }
    } finally {
      // Reflect partial successes too; failed files remain visible as an error in the dialog.
      await refresh({ documentsOnly: true });
    }
    return saved;
  }

  async function processDocuments(ids, force = false) {
    const results = [];
    try {
      for (let start = 0; start < ids.length; start += DOCUMENT_BATCH_LIMIT) {
        results.push(
          ...(await documentsApi.processDocuments(
            ids.slice(start, start + DOCUMENT_BATCH_LIMIT),
            force,
          )),
        );
      }
      return results;
    } finally {
      await refresh({ documentsOnly: true });
    }
  }

  return (
    <ContentContext.Provider
      value={{
        ...data,
        loading,
        error,
        refresh,
        saveDocument,
        processDocuments,
        deleteDocument: (id) =>
          mutate(() => documentsApi.deleteDocument(id), ["documents"]),
        saveGuide: (id, body) =>
          mutate(() => guidesApi.saveGuide(id, body), ["cards"]),
        deleteGuide: (id) => mutate(() => guidesApi.deleteGuide(id), ["cards"]),
        publishGuide: (id) =>
          mutate(() => guidesApi.publishGuide(id), ["cards"]),
        saveCategory: (id, body) =>
          mutate(
            () => categoriesApi.saveCategory(id, body),
            ["categories", "cards"],
          ),
        deleteCategory: (id) =>
          mutate(
            () => categoriesApi.deleteCategory(id),
            ["categories", "cards"],
          ),
        savePlaybook: (id, body) =>
          mutate(() => emergencyApi.savePlaybook(id, body), ["sops"]),
        publishPlaybook: (id) =>
          mutate(() => emergencyApi.publishPlaybook(id), ["sops"]),
        deletePlaybook: (id) =>
          mutate(() => emergencyApi.deletePlaybook(id), ["sops"]),
        saveContact: (id, body) =>
          mutate(() => emergencyApi.saveContact(id, body), ["contacts"]),
        deleteContact: (id) =>
          mutate(() => emergencyApi.deleteContact(id), ["contacts"]),
      }}
    >
      {children}
    </ContentContext.Provider>
  );
}

export const useContent = () => useContext(ContentContext);
