import type { ComponentType, CSSProperties } from "react";
import type { EChartsOption } from "echarts";
import { BarChart, GraphChart, LineChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  TransformComponent
} from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import EChartsCoreModule from "echarts-for-react/lib/core.js";

echarts.use([
  BarChart,
  GraphChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  TransformComponent,
  CanvasRenderer
]);

type Props = {
  option: EChartsOption;
  style?: CSSProperties;
};

type EChartsCoreProps = Props & {
  echarts: typeof echarts;
  notMerge?: boolean;
  lazyUpdate?: boolean;
};

const coreCandidate = EChartsCoreModule as unknown as
  | ComponentType<EChartsCoreProps>
  | { default: ComponentType<EChartsCoreProps> };
const ReactEChartsCore = "default" in coreCandidate ? coreCandidate.default : coreCandidate;

export function EChart({ option, style }: Props) {
  return <ReactEChartsCore echarts={echarts} option={option} notMerge lazyUpdate style={style} />;
}
