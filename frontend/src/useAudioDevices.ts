import { useCallback, useEffect, useState } from "react";

export interface AudioDeviceInfo {
  deviceId: string;
  label: string;
}

export function useAudioDevices() {
  const [micDevices, setMicDevices] = useState<AudioDeviceInfo[]>([]);
  const [speakerDevices, setSpeakerDevices] = useState<AudioDeviceInfo[]>([]);

  const refresh = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      return;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const mics = devices
        .filter((d) => d.kind === "audioinput")
        .map((d) => ({
          deviceId: d.deviceId,
          label: d.label || (d.deviceId === "default" ? "Domyslny mikrofon" : d.deviceId),
        }));
      const speakers = devices
        .filter((d) => d.kind === "audiooutput")
        .map((d) => ({
          deviceId: d.deviceId,
          label: d.label || (d.deviceId === "default" ? "Domyslne glosniki" : d.deviceId),
        }));
      setMicDevices(mics);
      setSpeakerDevices(speakers);
    } catch {
      setMicDevices([]);
      setSpeakerDevices([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
    navigator.mediaDevices?.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices?.removeEventListener("devicechange", refresh);
  }, [refresh]);

  return { micDevices, speakerDevices, refreshMicDevices: refresh };
}
