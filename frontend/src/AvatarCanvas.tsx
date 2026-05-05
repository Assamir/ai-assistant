import { OrbitControls, ContactShadows } from "@react-three/drei";
import { Canvas, useFrame, useLoader } from "@react-three/fiber";
import { VRMLoaderPlugin, VRM } from "@pixiv/three-vrm";
import React, { Suspense, useEffect, useRef } from "react";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

import {
  blendRecords,
  easeOutCubic,
  normalizeEmotionKey,
  recordsNearlyEqual,
  resolveWeights,
} from "./emotionBlend";

const EMOTION_CROSSFADE_SEC = 0.42;

interface VrmRootProps {
  url: string;
  emotion: string;
  lipSyncLevel: number;
}

function VrmRoot({ url, emotion, lipSyncLevel }: VrmRootProps) {
  const vrmRef = useRef<VRM | null>(null);
  const idleBonesRef = useRef<{ bone: THREE.Object3D; rest: THREE.Quaternion }[]>([]);

  const latestEmotionRef = useRef(emotion);
  latestEmotionRef.current = emotion;

  const targetKeyRef = useRef(normalizeEmotionKey(emotion));
  const blendRef = useRef(1);
  const startSnapRef = useRef(resolveWeights(emotion));
  const endSnapRef = useRef(resolveWeights(emotion));
  const lastRenderedRef = useRef(resolveWeights(emotion));

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
      const snap = resolveWeights(latestEmotionRef.current);
      targetKeyRef.current = normalizeEmotionKey(latestEmotionRef.current);
      startSnapRef.current = snap;
      endSnapRef.current = snap;
      lastRenderedRef.current = snap;
      blendRef.current = 1;
    }
    return () => {
      vrmRef.current = null;
      idleBonesRef.current = [];
    };
  }, [gltf]);

  useEffect(() => {
    const next = normalizeEmotionKey(emotion);
    const endGoal = resolveWeights(next);
    if (next === targetKeyRef.current && blendRef.current >= 1) {
      return;
    }
    if (recordsNearlyEqual(lastRenderedRef.current, endGoal)) {
      targetKeyRef.current = next;
      startSnapRef.current = endGoal;
      endSnapRef.current = endGoal;
      lastRenderedRef.current = endGoal;
      blendRef.current = 1;
      return;
    }
    startSnapRef.current = { ...lastRenderedRef.current };
    endSnapRef.current = endGoal;
    targetKeyRef.current = next;
    blendRef.current = 0;
  }, [emotion]);

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
    if (!em) {
      return;
    }

    const rate = EMOTION_CROSSFADE_SEC > 1e-4 ? 1 / EMOTION_CROSSFADE_SEC : 1e6;
    blendRef.current = Math.min(1, blendRef.current + delta * rate);
    const u = easeOutCubic(blendRef.current);
    const blended = blendRecords(startSnapRef.current, endSnapRef.current, u);

    em.resetValues();
    for (const [name, w] of Object.entries(blended)) {
      em.setValue(name, w);
    }

    lastRenderedRef.current = blended;

    const lip = lipSyncLevel > 0.035 ? Math.min(1, lipSyncLevel * 0.95) : 0;
    if (lip > 0) {
      em.setValue("aa", lip);
    }
  });

  return (
    <group>
      <primitive object={gltf.scene} />
      <ContactShadows opacity={0.35} scale={12} blur={2.5} far={6} />
    </group>
  );
}

function AuraLights() {
  const keyRef = useRef<THREE.PointLight>(null);
  const fillRef = useRef<THREE.PointLight>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const key = keyRef.current;
    const fill = fillRef.current;
    if (key) {
      key.intensity = 0.38 + Math.sin(t * 0.85) * 0.09;
    }
    if (fill) {
      fill.intensity = 0.13 + Math.cos(t * 1.12) * 0.048;
    }
  });
  return (
    <>
      <hemisphereLight args={["#dbe8ff", "#120824", 0.32]} />
      <pointLight ref={keyRef} position={[0.85, 1.68, 1.18]} color="#d8c8ff" distance={7} decay={2} />
      <pointLight ref={fillRef} position={[-1.42, 1.38, 0.92]} color="#5eead4" distance={5.8} decay={2} />
    </>
  );
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
          <ambientLight intensity={0.52} />
          <directionalLight position={[3, 6, 4]} intensity={1} castShadow />
          <AuraLights />
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
