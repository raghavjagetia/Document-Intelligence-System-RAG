import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export const qk = {
  stats: ["statistics"] as const,
  analytics: ["analytics"] as const,
  system: ["system-status"] as const,
  documentsRoot: ["documents"] as const,
  documents: (domain?: string, search?: string) => ["documents", domain ?? "", search ?? ""] as const,
  document: (id: string) => ["document", id] as const,
  versions: (id: string) => ["versions", id] as const,
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  suggestions: (domain: string) => ["suggestions", domain] as const,
  evalResults: ["eval-results"] as const,
  evalStatus: ["eval-status"] as const,
  admin: ["admin-overview"] as const,
};

export const useStatistics = () => useQuery({ queryKey: qk.stats, queryFn: api.statistics });
export const useAnalytics = () => useQuery({ queryKey: qk.analytics, queryFn: api.analytics });
export const useAdminOverview = (enabled = true) =>
  useQuery({ queryKey: qk.admin, queryFn: api.adminOverview, enabled });
export const useSystemStatus = () => useQuery({ queryKey: qk.system, queryFn: api.systemStatus, staleTime: 60_000 });
export const useDocuments = (domain?: string, search?: string) =>
  useQuery({ queryKey: qk.documents(domain, search), queryFn: () => api.documents({ domain, search }) });
export const useConversations = () => useQuery({ queryKey: qk.conversations, queryFn: api.conversations });
