import { useState } from "react";
import { BookOpen, FileText } from "lucide-react";

// Preset keyword templates mapped by domain
const KEYWORD_TEMPLATES: Record<string, { label: string; keywords: string[]; description: string }> = {
  "trade-policy": {
    label: "贸易政策",
    keywords: ["tariff", "trade policy", "import restriction", "trade agreement", "FTA", "WTO", "sanction", "export control"],
    description: "关注关税调整、贸易协定、进出口限制和制裁政策。",
  },
  "tech-regulations": {
    label: "技术法规",
    keywords: ["TBT", "technical regulation", "standard", "certification", "conformity assessment", "CE marking", "RoHS", "REACH", "product safety"],
    description: "追踪技术性贸易壁垒(TBT)、产品认证和合规标准变化。",
  },
  "customs-compliance": {
    label: "海关合规",
    keywords: ["customs", "tariff classification", "HS code", "rules of origin", "valuation", "AEO", "customs clearance", "trade facilitation"],
    description: "聚焦海关程序、归类裁定、原产地规则和贸易便利化措施。",
  },
  "food-safety": {
    label: "食品安全",
    keywords: ["food safety", "SPS", "MRL", "pesticide", "contaminant", "food additive", "labeling", "traceability", "import alert"],
    description: "关注SPS措施、农残限量、食品添加剂和进口预警。",
  },
  "digital-trade": {
    label: "数字贸易",
    keywords: ["digital trade", "data localization", "cross-border data", "privacy", "GDPR", "AI regulation", "cybersecurity", "e-commerce"],
    description: "追踪数字贸易规则、数据本地化和网络安全合规要求。",
  },
  "supply-chain": {
    label: "供应链合规",
    keywords: ["supply chain", "forced labor", "conflict minerals", "CSR", "ESG", "due diligence", "traceability", "human rights"],
    description: "关注供应链尽职调查、强迫劳动和ESG合规要求。",
  },
};

const DESC_TEMPLATES: Record<string, string> = {
  "trade-policy": "请分析最近{window_days}天内全球主要经济体发布的贸易政策措施，重点关注关税调整、进口限制、贸易协定更新和制裁措施的变化趋势。按影响程度排序，并标注涉及的关键商品类别。",
  "tech-regulations": "请分析最近{window_days}天内主要国家/地区发布的技术法规和标准更新，重点关注产品认证要求变化、新标准的生效日期以及对中国出口企业的影响评估。",
  "customs-compliance": "请分析最近{window_days}天内海关程序和贸易便利化措施的重大变化，包括归类裁定、原产地规则更新和AEO互认进展。",
  "food-safety": "请分析最近{window_days}天内全球食品安全预警和SPS通报，重点关注农残限量修订、食品添加剂新规和进口禁令信息。",
  "digital-trade": "请分析最近{window_days}天内数字贸易和数据治理相关法规变化，包括数据本地化要求、AI监管新规和跨境数据传输机制更新。",
  "supply-chain": "请分析最近{window_days}天内供应链合规相关法规和标准变化，包括尽职调查要求、强迫劳动立法和冲突矿产报告义务。",
};

interface Props {
  onSelectKeywords: (keywords: string[]) => void;
  onSelectDescription: (description: string) => void;
  onClose: () => void;
}

export function KeywordTemplatePicker({ onSelectKeywords, onSelectDescription, onClose }: Props) {
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  const handleApply = () => {
    if (!selectedDomain) return;
    const template = KEYWORD_TEMPLATES[selectedDomain];
    const desc = DESC_TEMPLATES[selectedDomain];
    if (template) onSelectKeywords(template.keywords);
    if (desc) onSelectDescription(desc);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 520, maxWidth: "95vw" }}>
        <h3><BookOpen size={16} style={{ verticalAlign: "middle", marginRight: 6 }} />选择关键词模板</h3>
        <p className="text-muted small" style={{ marginBottom: 16 }}>
          选择一个预置的领域模板，自动填充关键词和描述提示词。
        </p>

        <div className="template-grid">
          {Object.entries(KEYWORD_TEMPLATES).map(([key, tmpl]) => (
            <button
              key={key}
              type="button"
              className={`template-card ${selectedDomain === key ? "template-card--active" : ""}`}
              onClick={() => setSelectedDomain(key)}
            >
              <div className="template-card-header">
                <FileText size={16} />
                <strong>{tmpl.label}</strong>
              </div>
              <p className="text-muted small">{tmpl.description}</p>
              <div className="template-chip-preview">
                {tmpl.keywords.slice(0, 4).map((kw) => (
                  <span key={kw} className="chip chip--blue">{kw}</span>
                ))}
                {tmpl.keywords.length > 4 && <span className="chip">+{tmpl.keywords.length - 4}</span>}
              </div>
            </button>
          ))}
        </div>

        <div className="modal-actions" style={{ marginTop: 16 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" disabled={!selectedDomain} onClick={handleApply}>
            应用模板
          </button>
        </div>
      </div>
    </div>
  );
}
