// Reusable templates for the Topic form: natural-language description prompts and
// weighted-keyword presets. These are inserted into the form and remain editable.

export type PromptTemplate = { label: string; value: string };
export type KeywordTemplate = { label: string; value: string };

/** 10 ready-to-use 描述提示词 covering the customs/trade-intelligence domains. */
export const DESCRIPTION_PROMPT_TEMPLATES: PromptTemplate[] = [
  {
    label: "贸易政策监控",
    value:
      "监控全球主要经济体的贸易政策变化、关税调整、贸易协定（FTA/RCEP/CPTPP）进展与生效情况，重点关注影响中国进出口的措施、配额、原产地规则与许可证制度。",
  },
  {
    label: "关税与税则变动",
    value:
      "跟踪各国海关税则（HS编码）调整、加征/取消关税、反倾销与反补贴税、保障措施立案与裁决，识别对重点商品税率的实际影响。",
  },
  {
    label: "走私与执法情报",
    value:
      "收集全球海关缉私、跨境走私案件、查获通报与执法行动信息，关注走私手法、重点口岸、涉案商品（毒品、野生动植物、烟草、贵金属）与国际合作打击动态。",
  },
  {
    label: "大宗商品价格",
    value:
      "追踪原油、天然气、金属（铜/铝/铁矿）、农产品（粮食/食糖/油脂）与贵金属的国际现货与期货价格走势、价格指数与供需基本面变化。",
  },
  {
    label: "出口管制与制裁",
    value:
      "监控各国出口管制清单、实体清单、经济制裁与禁运措施更新，关注双用途物项、敏感技术与受限主体变化对供应链合规的影响。",
  },
  {
    label: "供应链与物流",
    value:
      "关注全球供应链中断、港口拥堵、海运/空运运价、集装箱周转与关键节点风险，评估对跨境贸易时效与成本的影响。",
  },
  {
    label: "贸易救济调查",
    value:
      "跟踪反倾销、反补贴、保障措施的立案、初裁、终裁与复审进展，整理涉案国别、产品范围、税率水平与企业应对动态。",
  },
  {
    label: "海关合规与通关",
    value:
      "收集各国海关通关流程、AEO认证、原产地证明、申报规范与稽查重点变化，识别合规风险与便利化政策机会。",
  },
  {
    label: "知识产权与边境保护",
    value:
      "监控海关知识产权保护、假冒侵权商品查获、边境扣押与维权案例，关注重点品类与高风险来源地。",
  },
  {
    label: "行业市场动态",
    value:
      "综合采集目标行业的市场规模、产能、贸易流向、主要企业与政策驱动因素，形成可用于决策的情报摘要。",
  },
];

/** Weighted-keyword presets (each line: keyword:weight, 0.1~1.0). */
export const KEYWORD_WEIGHT_TEMPLATES: KeywordTemplate[] = [
  {
    label: "贸易政策",
    value: "关税:1.0\n贸易协定:0.9\n出口管制:0.8\n原产地规则:0.7\n配额:0.6",
  },
  {
    label: "走私缉私",
    value: "走私:1.0\n缉私:0.9\n查获:0.8\n跨境:0.7\n口岸:0.6",
  },
  {
    label: "大宗商品",
    value: "原油:1.0\n铜价:0.9\n铁矿石:0.8\n粮食:0.7\n黄金:0.6",
  },
  {
    label: "贸易救济",
    value: "反倾销:1.0\n反补贴:0.9\n保障措施:0.8\n裁决:0.7\n复审:0.6",
  },
  {
    label: "供应链",
    value: "供应链:1.0\n海运运价:0.9\n港口拥堵:0.8\n集装箱:0.7\n物流:0.6",
  },
];
