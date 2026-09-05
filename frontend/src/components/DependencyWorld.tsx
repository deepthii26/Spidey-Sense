import { Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import type { Group } from "three";

import type { ActivityRecord, DashboardPayload } from "../types";

type WorldMode = "all" | "active" | "conflicts";

interface WorldNode {
  id: string;
  language: string;
  zone: string;
  position: [number, number, number];
  height: number;
  color: string;
  activity?: ActivityRecord;
  blocked: boolean;
  dirty: boolean;
}

interface WebZone {
  name: string;
  position: [number, number, number];
  count: number;
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

function zoneForPath(path: string): string {
  const parts = path.split("/");
  if (parts.length === 1) return "root";
  if (["src", "app", "apps", "packages", "lib"].includes(parts[0]) && parts.length > 2) {
    return `${parts[0]}/${parts[1]}`;
  }
  return parts[0];
}

function nodeColor(activity: ActivityRecord | undefined, blocked: boolean, dirty: boolean): string {
  if (blocked) return "#f02d55";
  if (activity?.status === "working") return "#2f7fff";
  if (activity?.status === "done") return "#22d3a6";
  if (activity?.status === "pending") return "#f2a93b";
  if (dirty) return "#b65cff";
  return "#243958";
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
  const visible = prioritized
    .filter((node) => {
      if (mode === "conflicts") return blockedFiles.has(node.id);
      if (mode === "active") return activityByFile.has(node.id) || dirtyFiles.has(node.id);
      return true;
    })
    .slice(0, 72);

  const zoneNames = [...new Set(visible.map((node) => zoneForPath(node.id)))].sort();
  const centers = new Map<string, [number, number, number]>();
  zoneNames.forEach((name, index) => {
    if (zoneNames.length === 1) {
      centers.set(name, [0, 0, 0]);
      return;
    }
    const angle = index * ((Math.PI * 2) / zoneNames.length) - Math.PI / 2;
    const radius = zoneNames.length < 4 ? 4.8 : 6.7;
    centers.set(name, [Math.cos(angle) * radius, 0, Math.sin(angle) * radius]);
  });

  const zoneMembers = new Map<string, typeof visible>();
  for (const node of visible) {
    const zone = zoneForPath(node.id);
    zoneMembers.set(zone, [...(zoneMembers.get(zone) ?? []), node]);
  }

  const nodes: WorldNode[] = [];
  for (const zone of zoneNames) {
    const members = zoneMembers.get(zone) ?? [];
    const center = centers.get(zone) ?? [0, 0, 0];
    const columns = Math.ceil(Math.sqrt(members.length));
    members.forEach((node, index) => {
      const activity = activityByFile.get(node.id);
      const blocked = blockedFiles.has(node.id);
      const dirty = dirtyFiles.has(node.id);
      const height =
        0.8 + Math.min(degree.get(node.id) ?? 0, 10) * 0.24 + (activity ? 0.8 : 0);
      const row = Math.floor(index / columns);
      const column = index % columns;
      const spread = 1.08;
      const width = Math.min(columns, members.length);
      const rows = Math.ceil(members.length / columns);
      nodes.push({
        id: node.id,
        language: node.language,
        zone,
        position: [
          center[0] + (column - (width - 1) / 2) * spread,
          height / 2,
          center[2] + (row - (rows - 1) / 2) * spread,
        ],
        height,
        color: nodeColor(activity, blocked, dirty),
        activity,
        blocked,
        dirty,
      });
    });
  }

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const edges = data.graph.edges
    .map((edge) => ({ source: byId.get(edge.source), target: byId.get(edge.target) }))
    .filter(
      (edge): edge is { source: WorldNode; target: WorldNode } =>
        Boolean(edge.source && edge.target),
    )
    .slice(0, 180);
  const zones: WebZone[] = zoneNames.map((name) => ({
    name,
    position: centers.get(name) ?? [0, 0, 0],
    count: zoneMembers.get(name)?.length ?? 0,
  }));
  return { nodes, edges, zones };
}

function AgentBeacon({ node, animate }: { node: WorldNode; animate: boolean }) {
  const group = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (animate && group.current) {
      group.current.position.y = node.height + 0.62 + Math.sin(clock.elapsedTime * 2.8) * 0.1;
      group.current.rotation.y += 0.018;
    }
  });
  return (
    <group ref={group} position={[node.position[0], node.height + 0.62, node.position[2]]}>
      <mesh>
        <octahedronGeometry args={[0.22, 0]} />
        <meshStandardMaterial color="#ffffff" emissive={node.color} emissiveIntensity={2.2} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.43, 0.024, 8, 32]} />
        <meshBasicMaterial color={node.color} transparent opacity={0.9} />
      </mesh>
      <Html center distanceFactor={12} position={[0, 0.52, 0]}>
        <span className="pointer-events-none whitespace-nowrap rounded border border-blue-300/20 bg-[#050b18]/95 px-2 py-1 font-mono text-[9px] font-bold uppercase tracking-wider text-blue-100 shadow-xl">
          {node.activity?.teammate} · live
        </span>
      </Html>
    </group>
  );
}

function DangerPulse({ node, animate }: { node: WorldNode; animate: boolean }) {
  const group = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (animate && group.current) {
      const pulse = 0.82 + ((clock.elapsedTime * 0.55) % 1) * 1.25;
      group.current.scale.setScalar(pulse);
      group.current.rotation.z += 0.01;
    }
  });
  return (
    <group ref={group} position={[node.position[0], 0.06, node.position[2]]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.42, 0.49, 32]} />
        <meshBasicMaterial color="#ff365f" transparent opacity={0.72} />
      </mesh>
    </group>
  );
}

function Building({
  node,
  selected,
  onSelect,
}: {
  node: WorldNode;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const luminous = Boolean(node.activity || node.dirty || node.blocked);
  return (
    <group position={node.position}>
      <mesh
        scale={selected ? 1.15 : 1}
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
          emissiveIntensity={luminous ? 0.48 : 0.08}
          roughness={0.32}
          metalness={0.62}
        />
      </mesh>
      <mesh position={[0, node.height / 2 + 0.055, 0]}>
        <boxGeometry args={[0.82, 0.1, 0.82]} />
        <meshBasicMaterial color={node.color} />
      </mesh>
      <mesh position={[0, 0, 0.365]}>
        <boxGeometry args={[0.42, Math.max(0.24, node.height * 0.54), 0.01]} />
        <meshBasicMaterial color={luminous ? "#8db8ff" : "#152642"} transparent opacity={0.72} />
      </mesh>
    </group>
  );
}

function RadarGround() {
  return (
    <>
      {[2.5, 5, 7.5, 10].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]}>
          <ringGeometry args={[radius - 0.025, radius + 0.025, 96]} />
          <meshBasicMaterial color="#285fae" transparent opacity={0.35} />
        </mesh>
      ))}
      {Array.from({ length: 12 }, (_, index) => {
        const angle = index * (Math.PI / 6);
        return (
          <Line
            key={angle}
            points={[
              [0, 0.018, 0],
              [Math.cos(angle) * 11.5, 0.018, Math.sin(angle) * 11.5],
            ]}
            color="#234d87"
            lineWidth={0.55}
            transparent
            opacity={0.28}
          />
        );
      })}
    </>
  );
}

function WebScene({
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
      <color attach="background" args={["#030712"]} />
      <fog attach="fog" args={["#030712", 15, 33]} />
      <ambientLight intensity={0.58} />
      <directionalLight position={[8, 15, 7]} intensity={2.3} color="#dbeafe" />
      <pointLight position={[-8, 4, -7]} intensity={38} distance={20} color="#d62950" />
      <pointLight position={[9, 5, 8]} intensity={42} distance={22} color="#246dff" />
      <RadarGround />
      {world.edges.map(({ source, target }, index) => {
        const danger = source.blocked || target.blocked;
        const middleX = (source.position[0] + target.position[0]) / 2;
        const middleZ = (source.position[2] + target.position[2]) / 2;
        const distance = Math.hypot(
          source.position[0] - target.position[0],
          source.position[2] - target.position[2],
        );
        return (
          <Line
            key={`${source.id}-${target.id}-${index}`}
            points={[
              [source.position[0], 0.16, source.position[2]],
              [middleX, Math.min(0.35 + distance * 0.08, 1.25), middleZ],
              [target.position[0], 0.16, target.position[2]],
            ]}
            color={danger ? "#ff365f" : "#3d83ff"}
            lineWidth={danger ? 2.1 : 0.72}
            transparent
            opacity={danger ? 0.92 : 0.36}
          />
        );
      })}
      {world.zones.map((zone) => (
        <Html
          key={zone.name}
          center
          distanceFactor={19}
          position={[zone.position[0], 0.04, zone.position[2] - 2.1]}
        >
          <span className="pointer-events-none whitespace-nowrap rounded border border-blue-300/10 bg-[#030712]/75 px-2 py-1 font-mono text-[8px] font-semibold uppercase tracking-[0.18em] text-blue-300/70">
            {zone.name} · {zone.count}
          </span>
        </Html>
      ))}
      {world.nodes.map((node) => (
        <Building key={node.id} node={node} selected={selected === node.id} onSelect={onSelect} />
      ))}
      {world.nodes
        .filter((node) => node.blocked)
        .map((node) => (
          <DangerPulse key={`danger-${node.id}`} node={node} animate={!reducedMotion} />
        ))}
      {world.nodes
        .filter((node) => node.activity?.status === "working")
        .map((node) => (
          <AgentBeacon key={`agent-${node.id}`} node={node} animate={!reducedMotion} />
        ))}
      <OrbitControls
        makeDefault
        autoRotate={spin && !reducedMotion}
        autoRotateSpeed={0.28}
        enableZoom={false}
        minPolarAngle={0.62}
        maxPolarAngle={1.28}
        target={[0, 0.8, 0]}
      />
    </>
  );
}

function WorldFallback({ data }: { data: DashboardPayload }) {
  return (
    <div className="grid min-h-96 place-items-center bg-[#030712] p-8 text-center text-white">
      <div>
        <p className="web-label text-rose-400">Radar fallback</p>
        <p className="mt-2 font-semibold">3D web unavailable</p>
        <p className="mt-2 text-sm text-slate-400">
          The accessible live view remains available below with {data.graph.stats.nodes} nodes and{" "}
          {data.graph.stats.edges} dependency strands.
        </p>
      </div>
    </div>
  );
}

const modes: Array<{ value: WorldMode; label: string }> = [
  { value: "all", label: "Full web" },
  { value: "active", label: "Live work" },
  { value: "conflicts", label: "Tangles" },
];

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
    <section className="web-panel overflow-hidden" aria-labelledby="world-heading">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-blue-300/10 px-4 py-3.5 sm:px-5">
        <div>
          <p className="web-label">Repository topology // live</p>
          <h2 id="world-heading" className="mt-1 text-lg font-bold text-white text-balance">
            The Dependency Web
          </h2>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="3D graph filters">
          {modes.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setMode(value);
                setSelected(null);
              }}
              className={`min-h-9 rounded-md border px-3 font-mono text-[10px] font-bold uppercase tracking-wider outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                mode === value
                  ? "border-blue-400/70 bg-blue-500/20 text-blue-100"
                  : "border-slate-700/80 bg-[#071020] text-slate-400 hover:border-slate-500"
              }`}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setSpin((value) => !value)}
            className="min-h-9 rounded-md border border-slate-700/80 bg-[#071020] px-3 font-mono text-[10px] font-bold uppercase tracking-wider text-slate-400 outline-none hover:border-slate-500 focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            {spin ? "Hold orbit" : "Orbit web"}
          </button>
        </div>
      </div>
      <div className="relative h-[34rem] sm:h-[39rem]" aria-label="Interactive 3D dependency web">
        {webGL === false ? (
          <WorldFallback data={data} />
        ) : webGL === null ? (
          <div className="grid size-full place-items-center font-mono text-xs uppercase tracking-widest text-blue-300/60">
            Calibrating Spidey Sense…
          </div>
        ) : (
          <Suspense
            fallback={
              <div className="grid size-full place-items-center font-mono text-xs uppercase tracking-widest text-blue-300/60">
                Weaving dependency web…
              </div>
            }
          >
            <Canvas
              camera={{ position: [12, 11, 14], fov: 47, near: 0.1, far: 85 }}
              dpr={mobile ? 1 : [1, 1.5]}
              performance={{ min: 0.5 }}
              frameloop={reducedMotion ? "demand" : "always"}
              fallback={<WorldFallback data={data} />}
              onPointerMissed={() => setSelected(null)}
            >
              <WebScene
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
          <div className="max-w-[75%] rounded-lg border border-blue-300/15 bg-[#030712]/90 p-3 text-xs text-slate-400 shadow-xl backdrop-blur-md">
            <p className="truncate font-mono font-semibold text-white">
              {selected ?? "SELECT A WEB NODE"}
            </p>
            <p className="mt-1">
              {selectedActivity
                ? `${selectedActivity.teammate} · ${selectedActivity.status}`
                : selectedDirty
                  ? `Git ${selectedDirty.status}`
                  : "Drag to rotate · grouped by directory · height shows dependency load"}
            </p>
          </div>
          <div className="hidden rounded-lg border border-blue-300/15 bg-[#030712]/90 p-3 font-mono text-[9px] uppercase tracking-wider text-slate-400 shadow-xl backdrop-blur-md md:block">
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              <span><i className="mr-1 inline-block size-2 rounded-full bg-blue-500" />Working</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-rose-500" />Tangle</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-emerald-400" />Done</span>
              <span><i className="mr-1 inline-block size-2 rounded-full bg-purple-500" />Git change</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
