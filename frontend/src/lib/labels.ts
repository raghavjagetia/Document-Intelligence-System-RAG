/**
 * Plain-English descriptions of HOW something was produced. The backend reports technical method
 * strings (e.g. "abstractive (llm:groq/qwen/qwen3.8-27b)"); the UI shows these readable versions and
 * keeps the technical string available as a tooltip.
 */

/** "groq/qwen/qwen3.8-27b" -> "qwen3.8-27b" */
function modelName(label: string): string {
  const parts = label.split("/");
  return parts[parts.length - 1] || label;
}

/** How an insight (summary, entities, key fields) was produced */
export function friendlyMethod(method: string): string {
  const m = method.toLowerCase();
  const llm = method.match(/llm:([^\s)]+)/i);
  if (m.startsWith("abstractive") && llm) return `Written by AI · ${modelName(llm[1])}`;
  if (m.startsWith("extractive")) return "Picked from the document";
  if (m.includes("spacy") || m.includes("ner")) return "Found automatically in the text";
  if (m.includes("rule-based") && llm) return "Read from the text · checked by AI";
  if (m.includes("rule-based") || m.includes("regex")) return "Read from the text";
  return method;
}

/** How a chat answer was produced */
export function friendlyGeneration(mode: string): string {
  if (mode.startsWith("llm:")) return `Written by AI · ${modelName(mode.slice(4))}`;
  if (mode.startsWith("extractive")) return "Quoted from your documents";
  if (mode === "abstained") return "Not in your documents";
  return mode;
}
