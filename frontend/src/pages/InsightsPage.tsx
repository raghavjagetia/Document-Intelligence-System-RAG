import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Briefcase, FileDiff, FileSearch, ScrollText, Sparkles, Tags, Upload } from "lucide-react";
import { useDocuments } from "../hooks/queries";
import { cn } from "../lib/utils";
import { Button, Card, EmptyState, ErrorState, PageHeader, Tabs } from "../components/ui";
import { DocCombobox } from "../components/DocCombobox";
import { CompareTab } from "../components/insights/CompareTab";
import { DocumentHero } from "../components/insights/DocumentHero";
import { EntitiesTab } from "../components/insights/EntitiesTab";
import { ExtractTab } from "../components/insights/ExtractTab";
import { SummaryTab } from "../components/insights/SummaryTab";

type Tab = "summary" | "entities" | "extract" | "compare";
const TABS: Tab[] = ["summary", "entities", "extract", "compare"];

// ---------------------------------------------------------------- Page
export default function InsightsPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const docs = useDocuments();
  const list = docs.data?.documents ?? [];
  const docId = params.get("doc");
  const tabParam = params.get("tab") as Tab | null;
  const tab: Tab = tabParam && TABS.includes(tabParam) ? tabParam : "summary";

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };

  const compareA = params.get("a") ?? docId;
  const compareB = params.get("b");

  return (
    <div>
      <PageHeader
        icon={<Sparkles />}
        title="Insights"
        description="Understand any document at a glance: a summary, the people, places and key facts it mentions, and what changed between versions."
      />

      <div className={cn("mb-5 grid gap-4 lg:items-end", tab !== "compare" && "lg:grid-cols-[minmax(0,420px)_1fr]")}>
        {tab !== "compare" && <DocCombobox documents={list} value={docId} onChange={(id) => update({ doc: id })} loading={docs.isLoading} label="Document" />}
        <Tabs
          value={tab}
          onChange={(t) => update({ tab: t })}
          items={[
            { value: "summary", label: "Summary", icon: <ScrollText /> },
            { value: "entities", label: "People & places", icon: <Tags /> },
            { value: "extract", label: "Key fields", icon: <Briefcase /> },
            { value: "compare", label: "Compare", icon: <FileDiff /> },
          ]}
        />
      </div>

      {docs.isError && (
        <Card>
          <ErrorState error={docs.error} onRetry={() => docs.refetch()} />
        </Card>
      )}
      {docs.data && list.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Upload />}
            title="No documents to analyze"
            description="Upload a document first, then come back for summaries and entity extraction."
            action={
              <Button variant="gradient" leftIcon={<Upload className="h-4 w-4" />} onClick={() => navigate("/documents?upload=1")}>
                Upload documents
              </Button>
            }
          />
        </Card>
      ) : tab === "compare" ? (
        <CompareTab a={compareA} b={compareB} setA={(v) => update({ a: v })} setB={(v) => update({ b: v })} />
      ) : !docId ? (
        <Card>
          <EmptyState icon={<FileSearch />} title="Select a document" description="Choose a document above to generate insights." />
        </Card>
      ) : (
        <>
          <DocumentHero docId={docId} />
          <motion.div key={`${tab}-${docId}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            {tab === "summary" && <SummaryTab docId={docId} />}
            {tab === "entities" && <EntitiesTab docId={docId} />}
            {tab === "extract" && <ExtractTab docId={docId} />}
          </motion.div>
        </>
      )}
    </div>
  );
}
