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

// ---------------------------------------------------------------------------
// Per-emotion body animation parameters
// ---------------------------------------------------------------------------

interface BodyParams {
  swayAmpX: number;
  swayAmpZ: number;
  swayFreqX: number;
  swayFreqZ: number;
  headTiltZ: number;
  headNodX: number;
}

const DEFAULT_BODY: BodyParams = {
  swayAmpX: 0.01,
  swayAmpZ: 0.0035,
  swayFreqX: 0.95,
  swayFreqZ: 0.42,
  headTiltZ: 0,
  headNodX: 0,
};

const EMOTION_BODY: Record<string, BodyParams> = {
  neutral:      { swayAmpX: 0.010, swayAmpZ: 0.0035, swayFreqX: 0.95, swayFreqZ: 0.42, headTiltZ:  0.00, headNodX:  0.00 },
  happy:        { swayAmpX: 0.012, swayAmpZ: 0.0050, swayFreqX: 1.10, swayFreqZ: 0.65, headTiltZ:  0.00, headNodX:  0.00 },
  amused:       { swayAmpX: 0.012, swayAmpZ: 0.0050, swayFreqX: 1.10, swayFreqZ: 0.65, headTiltZ:  0.04, headNodX:  0.00 },
  proud:        { swayAmpX: 0.010, swayAmpZ: 0.0040, swayFreqX: 0.80, swayFreqZ: 0.50, headTiltZ:  0.00, headNodX: -0.03 },
  sympathetic:  { swayAmpX: 0.008, swayAmpZ: 0.0040, swayFreqX: 0.70, swayFreqZ: 0.40, headTiltZ:  0.03, headNodX:  0.00 },
  sad:          { swayAmpX: 0.006, swayAmpZ: 0.0020, swayFreqX: 0.45, swayFreqZ: 0.25, headTiltZ:  0.00, headNodX:  0.05 },
  disappointed: { swayAmpX: 0.005, swayAmpZ: 0.0020, swayFreqX: 0.40, swayFreqZ: 0.20, headTiltZ: -0.03, headNodX:  0.04 },
  angry:        { swayAmpX: 0.013, swayAmpZ: 0.0040, swayFreqX: 1.20, swayFreqZ: 0.90, headTiltZ:  0.00, headNodX:  0.02 },
  disgusted:    { swayAmpX: 0.010, swayAmpZ: 0.0040, swayFreqX: 0.90, swayFreqZ: 0.60, headTiltZ: -0.04, headNodX:  0.00 },
  excited:      { swayAmpX: 0.018, swayAmpZ: 0.0080, swayFreqX: 1.50, swayFreqZ: 1.00, headTiltZ:  0.00, headNodX:  0.00 },
  scared:       { swayAmpX: 0.015, swayAmpZ: 0.0050, swayFreqX: 2.20, swayFreqZ: 1.60, headTiltZ:  0.00, headNodX:  0.03 },
  surprised:    { swayAmpX: 0.014, swayAmpZ: 0.0060, swayFreqX: 1.50, swayFreqZ: 1.00, headTiltZ:  0.00, headNodX: -0.04 },
  nervous:      { swayAmpX: 0.013, swayAmpZ: 0.0050, swayFreqX: 1.80, swayFreqZ: 1.30, headTiltZ:  0.02, headNodX:  0.00 },
  thinking:     { swayAmpX: 0.006, swayAmpZ: 0.0020, swayFreqX: 0.50, swayFreqZ: 0.30, headTiltZ:  0.06, headNodX:  0.01 },
  confused:     { swayAmpX: 0.008, swayAmpZ: 0.0030, swayFreqX: 0.60, swayFreqZ: 0.40, headTiltZ:  0.05, headNodX:  0.02 },
  nostalgic:    { swayAmpX: 0.007, swayAmpZ: 0.0030, swayFreqX: 0.50, swayFreqZ: 0.35, headTiltZ:  0.03, headNodX:  0.00 },
  sarcastic:    { swayAmpX: 0.009, swayAmpZ: 0.0040, swayFreqX: 0.70, swayFreqZ: 0.50, headTiltZ: -0.04, headNodX:  0.00 },
};

const IDLE_SWAY_SPRING = 9;

function randomBlinkDelay() {
  return 2.5 + Math.random() * 5;
}

interface VrmRootProps {
  url: string;
  emotion: string;
  lipSyncLevel: number;
}

function VrmRoot({ url, emotion, lipSyncLevel }: VrmRootProps) {
  const vrmRef = useRef<VRM | null>(null);
  const idleBonesRef = useRef<{ bone: THREE.Object3D; rest: THREE.Quaternion }[]>([]);
  const headBonesRef = useRef<{ bone: THREE.Object3D; rest: THREE.Quaternion }[]>([]);
  const idleSwayRef = useRef({ x: 0, z: 0 });

  // Smoothly interpolated body params (emotion transitions)
  const bodyParamsCurRef = useRef<BodyParams>({ ...DEFAULT_BODY });

  const latestEmotionRef = useRef(emotion);
  latestEmotionRef.current = emotion;

  const targetKeyRef = useRef(normalizeEmotionKey(emotion));
  const blendRef = useRef(1);
  const startSnapRef = useRef(resolveWeights(emotion));
  const endSnapRef = useRef(resolveWeights(emotion));
  const lastRenderedRef = useRef(resolveWeights(emotion));

  const nextBlinkRef = useRef(randomBlinkDelay());
  const blinkPhaseRef = useRef<"open" | "closing" | "opening">("open");
  const blinkValueRef = useRef(0);

  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });

  useEffect(() => {
    const raw = gltf.userData.vrm as VRM | undefined;
    vrmRef.current = raw ?? null;
    idleBonesRef.current = [];
    headBonesRef.current = [];
    if (raw?.humanoid) {
      const h = raw.humanoid;
      for (const name of ["chest", "spine", "hips"] as const) {
        const node = h.getNormalizedBoneNode(name);
        if (node) {
          idleBonesRef.current.push({ bone: node, rest: node.quaternion.clone() });
        }
      }
      for (const name of ["neck", "head"] as const) {
        const node = h.getNormalizedBoneNode(name);
        if (node) {
          headBonesRef.current.push({ bone: node, rest: node.quaternion.clone() });
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
      headBonesRef.current = [];
      idleSwayRef.current = { x: 0, z: 0 };
      nextBlinkRef.current = randomBlinkDelay();
      blinkPhaseRef.current = "open";
      blinkValueRef.current = 0;
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

    // --- Smooth body params toward target emotion ---
    const emoKey = normalizeEmotionKey(latestEmotionRef.current);
    const targetBody = EMOTION_BODY[emoKey] ?? DEFAULT_BODY;
    const cur = bodyParamsCurRef.current;
    const bk = 1 - Math.exp(-delta * 1.5);
    cur.swayAmpX += (targetBody.swayAmpX - cur.swayAmpX) * bk;
    cur.swayAmpZ += (targetBody.swayAmpZ - cur.swayAmpZ) * bk;
    cur.swayFreqX += (targetBody.swayFreqX - cur.swayFreqX) * bk;
    cur.swayFreqZ += (targetBody.swayFreqZ - cur.swayFreqZ) * bk;
    cur.headTiltZ += (targetBody.headTiltZ - cur.headTiltZ) * bk;
    cur.headNodX += (targetBody.headNodX - cur.headNodX) * bk;

    // --- Body sway (spring-damped) ---
    const sway = idleSwayRef.current;
    const targetX = Math.sin(t * cur.swayFreqX) * cur.swayAmpX;
    const targetZ = Math.cos(t * cur.swayFreqZ) * cur.swayAmpZ;
    const k = 1 - Math.exp(-delta * IDLE_SWAY_SPRING);
    sway.x += (targetX - sway.x) * k;
    sway.z += (targetZ - sway.z) * k;
    for (const { bone, rest } of idleBonesRef.current) {
      bone.quaternion.copy(rest);
      bone.rotateX(sway.x);
      bone.rotateZ(sway.z);
    }

    // --- Head animation: sway-follow + emotion tilt ---
    for (const { bone, rest } of headBonesRef.current) {
      bone.quaternion.copy(rest);
      bone.rotateX(sway.x * 0.35 + cur.headNodX);
      bone.rotateZ(sway.z * 0.25 + cur.headTiltZ);
    }

    // --- Emotion expression crossfade ---
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

    // --- Lip sync ---
    const lip = lipSyncLevel > 0.035 ? Math.min(1, lipSyncLevel * 0.95) : 0;
    if (lip > 0) {
      em.setValue("aa", lip);
    }

    // --- Idle blink (random interval, quick close/open) ---
    if (blinkPhaseRef.current === "open") {
      nextBlinkRef.current -= delta;
      if (nextBlinkRef.current <= 0) {
        blinkPhaseRef.current = "closing";
        blinkValueRef.current = 0;
      }
    } else if (blinkPhaseRef.current === "closing") {
      blinkValueRef.current = Math.min(1, blinkValueRef.current + delta / 0.07);
      if (blinkValueRef.current >= 1) {
        blinkPhaseRef.current = "opening";
      }
    } else {
      blinkValueRef.current = Math.max(0, blinkValueRef.current - delta / 0.09);
      if (blinkValueRef.current <= 0) {
        blinkPhaseRef.current = "open";
        nextBlinkRef.current = randomBlinkDelay();
      }
    }
    if (blinkValueRef.current > 0) {
      em.setValue("blink", blinkValueRef.current);
    }
  });

  return (
    <group>
      <primitive object={gltf.scene} />
      <ContactShadows opacity={0.35} scale={12} blur={2.5} far={6} />
    </group>
  );
}

/** Bazowe palety (rodziny) — interpolowane w `AuraLights`. */
const AURA_PALETTE: Record<
  string,
  { hemisphereSky: string; key: string; fill: string }
> = {
  neutral: { hemisphereSky: "#dbe8ff", key: "#d8c8ff", fill: "#5eead4" },
  happy: { hemisphereSky: "#ffeccd", key: "#ffe8aa", fill: "#7bdcff" },
  sad: { hemisphereSky: "#c8d4ff", key: "#aab8ff", fill: "#6a7bc4" },
  angry: { hemisphereSky: "#ffd4cf", key: "#ffb398", fill: "#ff7368" },
  excited: { hemisphereSky: "#ffe8bf", key: "#ffd078", fill: "#8aecbc" },
  thinking: { hemisphereSky: "#d8e4ff", key: "#c4c8ff", fill: "#7ec8dc" },
  surprised: { hemisphereSky: "#fff0d8", key: "#ffdc9a", fill: "#9ae0ff" },
};

const AURA_FAMILY_BY_EMOTION: Record<string, keyof typeof AURA_PALETTE> = {
  neutral: "neutral",
  happy: "happy",
  amused: "happy",
  proud: "happy",
  sarcastic: "happy",
  sympathetic: "sad",
  sad: "sad",
  disappointed: "sad",
  nostalgic: "sad",
  scared: "sad",
  angry: "angry",
  disgusted: "angry",
  excited: "excited",
  surprised: "surprised",
  nervous: "surprised",
  confused: "thinking",
  thinking: "thinking",
};

function auraPaletteForEmotion(emotion: string) {
  const nk = normalizeEmotionKey(emotion);
  const fam = AURA_FAMILY_BY_EMOTION[nk] ?? "neutral";
  return AURA_PALETTE[fam] ?? AURA_PALETTE.neutral;
}

const _auraTargetKey = new THREE.Color();
const _auraTargetFill = new THREE.Color();
const _auraTargetSky = new THREE.Color();

function AuraLights({ emotion }: { emotion: string }) {
  const keyRef = useRef<THREE.PointLight>(null);
  const fillRef = useRef<THREE.PointLight>(null);
  const hemiRef = useRef<THREE.HemisphereLight>(null);

  const keyCur = useRef(new THREE.Color(AURA_PALETTE.neutral.key));
  const fillCur = useRef(new THREE.Color(AURA_PALETTE.neutral.fill));
  const skyCur = useRef(new THREE.Color(AURA_PALETTE.neutral.hemisphereSky));

  useFrame(({ clock }, delta) => {
    const t = clock.elapsedTime;
    const pal = auraPaletteForEmotion(emotion);
    const dk = Math.min(1, delta * 2.6);
    _auraTargetKey.set(pal.key);
    _auraTargetFill.set(pal.fill);
    _auraTargetSky.set(pal.hemisphereSky);
    keyCur.current.lerp(_auraTargetKey, dk);
    fillCur.current.lerp(_auraTargetFill, dk);
    skyCur.current.lerp(_auraTargetSky, dk);

    const key = keyRef.current;
    const fill = fillRef.current;
    const hemi = hemiRef.current;
    if (key) {
      key.color.copy(keyCur.current);
      key.intensity = 0.36 + Math.sin(t * 0.85) * 0.07;
    }
    if (fill) {
      fill.color.copy(fillCur.current);
      fill.intensity = 0.12 + Math.cos(t * 1.12) * 0.04;
    }
    if (hemi) {
      hemi.color.copy(skyCur.current);
    }
  });
  return (
    <>
      <hemisphereLight ref={hemiRef} args={[AURA_PALETTE.neutral.hemisphereSky, "#120824", 0.31]} />
      <pointLight ref={keyRef} position={[0.85, 1.68, 1.18]} color={AURA_PALETTE.neutral.key} distance={7} decay={2} />
      <pointLight ref={fillRef} position={[-1.42, 1.38, 0.92]} color={AURA_PALETTE.neutral.fill} distance={5.8} decay={2} />
    </>
  );
}

interface AvatarCanvasProps {
  vrmUrl: string;
  emotion: string;
  lipSyncLevel: number;
  containerStyle?: React.CSSProperties;
}

export function AvatarCanvas({ vrmUrl, emotion, lipSyncLevel, containerStyle }: AvatarCanvasProps) {
  const trimmed = vrmUrl.trim();

  const defaultStyle: React.CSSProperties = {
    width: "100%",
    height: 340,
    borderRadius: 10,
    overflow: "hidden",
    background: "linear-gradient(180deg, #1a1525 0%, #0d0b12 100%)",
  };

  const mergedStyle = containerStyle ? { ...defaultStyle, ...containerStyle } : defaultStyle;

  return (
    <div style={mergedStyle}>
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
          <AuraLights emotion={emotion} />
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
          Brak modelu VRM — ustaw adres w oknie konfiguracji.
        </div>
      )}
    </div>
  );
}
