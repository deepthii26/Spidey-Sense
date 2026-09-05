import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { Group, Mesh } from "three";

import type { ActivityRecord, DashboardPayload } from "../types";

type WorldMode = "all" | "active" | "conflicts";

interface WorldNode {
  id: string;
  language: string;
  position: [number, number, number];
  height: number;
  color: string;
  activity?: ActivityRecord;
  blocked: boolean;
  dirty: boolean;
}

function supportsWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

function nodeColor(
  activity: ActivityRecord | undefined,
  blocked: boolean,
  dirty: boolean,
): string {
  if (blocked) return "#ef4444";
  if (activity?.status === "working") return "#2563eb";
  if (activity?.status === "done") return "#10b981";
  if (activity?.status === "pending") return "#f59e0b";
  if (dirty) return "#a855f7";
  return "#334155";
}

function buildWorld(data: DashboardPayload, mode: WorldMode) {
  const activityByFile = new Map<string, ActivityRecord>();
  for (const activity of Object.values(data.activity.teammates)) {
    for (const file of activity.files) activityByFile.set(file, activity);
  }
  const blockedFiles = new Set(
    data.blockers.flatMap((blocker) => [blocker.blocked_file, blocker.blocking_file]),
  );
  const dirtyFiles = new Set(data.live.git.dirty_files.map((file) => file.path));
  const degree = new Map<string, number>();
  for (const edge of data.graph.edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }
  const prioritized = [...data.graph.nodes].sort((left, right) => {
    const score = (id: string) =>
      (blockedFiles.has(id) ? 1000 : 0) +
      (activityByFile.has(id) ? 500 : 0) +
      (dirtyFiles.has(id) ? 250 : 0) +
      (degree.get(id) ?? 0);
    return score(right.id) - score(left.id) || left.id.localeCompare(right.id);
  });
  const filtered = prioritized.filter((node) => {
    if (mode === "conflicts") return blockedFiles.has(node.id);
    if (mode === "active") return activityByFile.has(node.id) || dirtyFiles.has(node.id);
    return true;
  });
  const visible = filtered.slice(0, 72);
  const nodes: WorldNode[] = visible.map((node, index) => {
    const lane = Math.floor(index / 16);
    const angle = (index % 16) * ((Math.PI * 2) / Math.min(16, visible.length));
    const radius = 4.3 + lane * 2.7;
    const activity = activityByFile.get(node.id);
    const blocked = blockedFiles.has(node.id);
    const dirty = dirtyFiles.has(node.id);
    const height = 0.9 + Math.min(degree.get(node.id) ?? 0, 9) * 0.22 + (activity ? 0.8 : 0);
    return {
      id: node.id,
      language: node.language,
      position: [Math.cos(angle) * radius, height / 2, Math.sin(angle) * radius],
      height,
      color: nodeColor(activity, blocked, dirty),
      activity,
      blocked,
      dirty,
    };
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = data.graph.edges
    .map((edge) => ({ source: byId.get(edge.source), target: byId.get(edge.target) }))
    .filter((edge): edge is { source: WorldNode; target: WorldNode } => Boolean(edge.source && edge.target))
    .slice(0, 160);
  return { nodes, edges };
}

function AgentBeacon({ node, animate }: { node: WorldNode; animate: boolean }) {
  const group = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (animate && group.current) {
      group.current.position.y = node.height + 0.55 + Math.sin(clock.elapsedTime * 2.4) * 0.12;
      group.current.rotation.y += 0.015;
    }
  });
  return (
    <group ref={group} position={[node.position[0], node.height + 0.55, node.position[2]]}>
      <mesh>
        <sphereGeometry args={[0.22, 16, 16]} />
        <meshStandardMaterial color="#ffffff" emissive={node.color} emissiveIntensity={1.8} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.42, 0.035, 8, 24]} />
        <meshBasicMaterial color={node.color} transparent opacity={0.8} />
      </mesh>
      <Html center distanceFactor={12} position={[0, 0.55, 0]}>
        <span className="pointer-events-none whitespace-nowrap rounded-full border border-white/20 bg-slate-950/90 px-2 py-1 text-[10px] font-bold text-white shadow-lg">
          {node.activity?.teammate}
        </span>
      </Html>
    </group>
  );
}

function CityScene({
  data,
  mode,
  spin,
  selected,
  onSelect,
  reducedMotion,
}: {
  data: DashboardPayload;
  mode: WorldMode;
  spin: boolean;
  selected: string | null;
  onSelect: (id: string | null) => void;
  reducedMotion: boolean;
}) {
  const world = useMemo(() => buildWorld(data, mode), [data, mode]);
  return (
    <>
      <color attach="background" args={["#020617"]} />
      <fog attach="fog" args={["#020617", 12, 31]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[8, 14, 6]} intensity={2.2} color="#dbeafe" />
      <pointLight position={[-8, 5, -7]} intensity={35} distance={18} color="#7c3aed" />
      <gridHelper args={[36, 36, "#1e3a8a", "#172033"]} position={[0, 0, 0]} />
      {world.edges.map(({ source, target }, index) => (
        <Line
          key={`${source.id}-${target.id}-${index}`}
          points={[
            [source.position[0], 0.12, source.position[2]],
            [target.position[0], 0.12, target.position[2]],
          ]}
          color={source.blocked || target.blocked ? "#ef4444" : "#2563eb"}
          lineWidth={source.blocked || target.blocked ? 1.8 : 0.65}
          transparent
          opacity={source.blocked || target.blocked ? 0.85 : 0.3}
        />
      ))}
      {world.nodes.map((node) => (
        <group key={node.id} position={node.position}>
          <mesh
            scale={selected === node.id ? 1.18 : 1}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(node.id);
            }}
            onPointerEnter={(event) => {
              event.stopPropagation();
              document.body.style.cursor = "pointer";
            }}
            onPointerLeave={() => {
              document.body.style.cursor = "default";
            }}
          >
            <boxGeometry args={[0.72, node.height, 0.72]} />
            <meshStandardMaterial
              color={node.color}
              emissive={node.color}
              emissiveIntensity={node.activity || node.dirty ? 0.55 : 0.12}
              roughness={0.38}
              metalness={0.45}
            />
          </mesh>
          <mesh position={[0, node.height / 2 + 0.05, 0]}>
            <boxGeometry args={[0.8, 0.06, 0.8]} />
            <meshBasicMaterial color={node.color} />
          </mesh>
        </group>
      ))}
      {world.nodes
        .filter((node) => node.activity?.status === "working")
        .map((node) => (
          <AgentBeacon key={`agent-${node.id}`} node={node} animate={!reducedMotion} />
        ))}
      <OrbitControls
        makeDefault
        autoRotate={spin && !reducedMotion}
        autoRotateSpeed={0.35}
        enableZoom={false}
        minPolarAngle={0.65}
        maxPolarAngle={1.32}
        target={[0, 0.8, 0]}
      />
    </>
  );
}

function WorldFallback({ data }: { data: DashboardPayload }) {
  return (
    <div className="grid min-h-96 place-items-center bg-slate-950 p-8 text-center text-white">
      <div>
        <p className="font-semibold">3D view unavailable</p>
        <p className="mt-2 text-sm text-slate-400">
          The live accessible dashboard remains available below with {data.graph.stats.nodes} files
          and {data.graph.stats.edges} dependency edges.
        </p>
      </div>
    </div>
  );
}

export function DependencyWorld({ data }: { data: DashboardPayload }) {
  const [mode, setMode] = useState<WorldMode>("all");
  const [spin, setSpin] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [webGL, setWebGL] = useState<boolean | null>(null);
  const [mobile, setMobile] = useState(false);
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    setWebGL(supportsWebGL());
    const query = window.matchMedia("(max-width: 640px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  const selectedActivity = selected
    ? Object.values(data.activity.teammates).find((activity) => activity.files.includes(selected))
    : undefined;
  const selectedDirty = selected
    ? data.live.git.dirty_files.find((file) => file.path === selected)
    : undefined;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-xl" aria-labelledby="world-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 text-white">
        <div>
          <p className="text-[11px] font-bold uppercase text-blue-400">Dependency city</p>
          <h2 id="world-heading" className="text-lg font-bold text-balance">Live repository world</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="3D graph filters">
          {(["all", "active", "conflicts"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setMode(value);
                setSelected(null);
              }}
              className={`min-h-9 rounded-lg border px-3 text-xs font-semibold capitalize outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                mode === value
                  ? "border-blue-500 bg-blue-600 text-white"
                  : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500"
              }`}
            >
              {value}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setSpin((value) => !value)}
            className="min-h-9 rounded-lg border border-slate-700 bg-slate-900 px-3 text-xs font-semibold text-slate-300 outline-none hover:border-slate-500 focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            {spin ? "Pause orbit" : "Orbit world"}
          </button>
        </div>
      </div>
      <div className="relative h-[32rem]" aria-label="Interactive 3D dependency graph">
        {webGL === false ? (
          <WorldFallback data={data} />
        ) : webGL === null ? (
          <div className="grid size-full place-items-center text-sm text-slate-400">Initialising 3D world…</div>
        ) : (
          <Suspense fallback={<div className="grid size-full place-items-center text-sm text-slate-400">Loading 3D world…</div>}>
            <Canvas
              camera={{ position: [11, 10, 13], fov: 46, near: 0.1, far: 80 }}
              dpr={mobile ? 1 : [1, 1.5]}
              performance={{ min: 0.5 }}
              frameloop={reducedMotion ? "demand" : "always"}
              fallback={<WorldFallback data={data} />}
              onPointerMissed={() => setSelected(null)}
            >
              <CityScene
                data={data}
                mode={mode}
                spin={spin}
                selected={selected}
                onSelect={setSelected}
                reducedMotion={reducedMotion}
              />
            </Canvas>
          </Suspense>
        )}
        <div className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-wrap items-end justify-between gap-3">
          <div className="rounded-xl border border-white/10 bg-slate-950/90 p-3 text-xs text-slate-300 shadow-lg">
            <p className="font-semibold text-white">{selected ?? "Select a building"}</p>
            <p className="mt-1">
              {selectedActivity
                ? `${selectedActivity.teammate} · ${selectedActivity.status}`
                : selectedDirty
                  ? `Git ${selectedDirty.status}`
                  : "Drag to rotate · buildings scale with dependency load"}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-950/90 p-3 text-[11px] text-slate-300 shadow-lg">
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              <span><i className="mr-1 inline-block size-2 rounded-full bg-blue-500" />Working</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-red-500" />Conflict</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-emerald-500" />Done</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-purple-500" />Git change</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
