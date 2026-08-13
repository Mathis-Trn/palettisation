import { SimulationWorkspace } from "@/components/workspace/simulation-workspace";

export default async function SimulationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SimulationWorkspace simulationId={id} />;
}
