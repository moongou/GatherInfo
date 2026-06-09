import type { ReactNode } from "react";

interface Props {
  content: string;
}

/**
 * Simple Markdown renderer for report content.
 * Supports: ##/### headers, **bold**, numbered lists, bullet points, code blocks.
 */
export function RenderMarkdown({ content }: Props): ReactNode {
  const lines = content.split("\n");
  const elements: ReactNode[] = [];
  let inCode = false;
  let codeBlock: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCode) {
        elements.push(<pre key={i} className="md-code-block"><code>{codeBlock.join("\n")}</code></pre>);
        codeBlock = [];
        inCode = false;
      } else {
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeBlock.push(line);
      continue;
    }

    if (line.startsWith("## ")) {
      elements.push(<h4 key={i} style={{ margin: "16px 0 8px", fontSize: "1rem", fontWeight: 700, color: "var(--accent)" }}>{line.slice(3)}</h4>);
    } else if (line.startsWith("### ")) {
      elements.push(<h5 key={i} style={{ margin: "12px 0 6px", fontSize: "0.9rem", fontWeight: 600 }}>{line.slice(4)}</h5>);
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(<p key={i} style={{ fontWeight: 600, margin: "8px 0 4px" }}>{line.replace(/\*\*/g, "")}</p>);
    } else if (line.match(/^\d\.\s/)) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12 }}>{line}</p>);
    } else if (line.startsWith("- ")) {
      elements.push(<p key={i} style={{ margin: "2px 0", paddingLeft: 12, color: "var(--ink-muted)" }}>{line}</p>);
    } else if (line.trim() === "") {
      elements.push(<div key={i} style={{ height: 4 }} />);
    } else {
      const rendered = line
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\[参见条目(\d+)\]/g, '<span style="color:var(--accent);font-size:0.8em">[参见条目$1]</span>');
      elements.push(<p key={i} style={{ margin: "4px 0" }} dangerouslySetInnerHTML={{ __html: rendered }} />);
    }
  }

  return <>{elements}</>;
}
