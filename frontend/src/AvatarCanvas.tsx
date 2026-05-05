import { OrbitControls, ContactShadows } from "@react-three/drei";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { VRMLoaderPlugin, VRM } from "@pixiv/three-vrm";
import React, { Suspense, useEffect, useRef } from "react";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

import emotionWeights from "./emotions.json";

const emotionMap = emotionWeights as Record<string, Record<string, number>>;

function applyEmotion(vrm: VRM | null, emotion: string) {
  const manager = vrm?.expressionManager;
  if (!manager) {
    return;
  }
  const key = emotion.toLowerCase();
  const weights = emotionMap[key] ?? emotionMap.neutral;
  manager.resetValues();
  for (const [name, w] of Object.entries(weights)) {
    manager.setValue(name, w);
  }
}

interface VrmRootProps {
  url: string;
  emotion: string;
  lipSyncLevel: number;
}

function VrmRoot({ url, emotion, lipSyncLevel }: VrmRootProps) {
  const vrmRef = useRef<VRM | null>(null);
  const idleBonesRef = useRef<{ bone: THREE.Object3D; rest: THREE.Quaternion }[]>([]);

  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });

  useEffect(() => {
    const raw = gltf.userData.vrm as VRM | undefined;
    vrmRef.current = raw ?? null;
    idleBonesRef.current = [];
    if (raw?.humanoid) {
      const h = raw.humanoid;
      for (const name of ["chest", "spine", "hips"] as const) {
        const node = h.getNormalizedBoneNode(name);
        if (node) {
          idleBonesRef.current.push({ bone: node, rest: node.quaternion.clone() });
        }
      }
    }
    if (raw) {
      applyEmotion(raw, emotion);
    }
    return () => {
      vrmRef.current = null;
      idleBonesRef.current = [];
    };
  }, [gltf, emotion]);

  useFrame((state, delta) => {
    const vrm = vrmRef.current;
    if (!vrm) {
      return;
    }
    vrm.update(delta);
    const t = state.clock.elapsedTime;
    for (const { bone, rest } of idleBonesRef.current) {
      bone.quaternion.copy(rest);
      bone.rotateX(Math.sin(t * 0.95) * 0.014);
      bone.rotateZ(Math.cos(t * 0.42) * 0.005);
    }
    const em = vrm.expressionManager;
    if (em) {
      const lip = lipSyncLevel > 0.035 ? Math.min(1, lipSyncLevel * 0.95) : 0;
      if (lip > 0) {
        em.setValue("aa", lip);
      }
    }
  });

  return (
    <group>
      <primitive object={gltf.scene} />
      <ContactShadows opacity={0.35} scale={12} blur={2.5} far={6} />
    </group>
  );
}

function AuraLight() {
  const ref = useRef<THREE.PointLight>(null);
  useFrame(({ clock }) => {
    const L = ref.current;
    if (L) {
      L.intensity = 0.35 + Math.sin(clock.elapsedTime * 0.8) * 0.08;
    }
  });
  return <pointLight ref={ref} position={[0.8, 1.6, 1.2]} color="#c4b5fd" distance={6} />;
}

interface AvatarCanvasProps {
  vrmUrl: string;
  emotion: string;
  lipSyncLevel: number;
}

export function AvatarCanvas({ vrmUrl, emotion, lipSyncLevel }: AvatarCanvasProps) {
  const trimmed = vrmUrl.trim();

  return (
    <div style={{ width: "100%", height: 340, borderRadius: 10, overflow: "hidden", background: "linear-gradient(180deg, #1a1525 0%, #0d0b12 100%)" }}>
      {trimmed ? (
        <Canvas
          dpr={[1, 2]}
          camera={{ position: [0, 1.35, 1.35], fov: 38 }}
          gl={{ alpha: true, antialias: true }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
          }}
          style={{ width: "100%", height: "100%" }}
        >
          <ambientLight intensity={0.55} />
          <directionalLight position={[3, 6, 4]} intensity={1.05} castShadow />
          <AuraLight />
          <Suspense fallback={null}>
            <VrmRoot url={trimmed} emotion={emotion} lipSyncLevel={lipSyncLevel} />
          </Suspense>
          <OrbitControls
            target={[0, 1.1, 0]}
            enablePan={false}
            minDistance={0.85}
            maxDistance={3.2}
            maxPolarAngle={Math.PI * 0.52}
          />
        </Canvas>
      ) : (
        <div style={{ height: "100%", display: "grid", placeItems: "center", color: "#9b92af", fontSize: 14, padding: "0 1.5rem", textAlign: "center" }}>
          Brak modelu VRM — ustaw adres w zakładce „Avatar” (np. URL do pliku .vrm).
        </div>
      )}
    </div>
  );
}
