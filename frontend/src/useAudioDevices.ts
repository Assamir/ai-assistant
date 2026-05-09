import { useCallback, useEffect, useState } from "react";

export interface AudioDeviceInfo {
  deviceId: string;
  label: string;
}

export function useAudioDevices() {
  const [micDevices, setMicDevices] = useState<AudioDeviceInfo[]>([]);

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
          label: d.label || (d.deviceId === "default" ? "Domyślny mikrofon" : d.deviceId),
        }));
      setMicDevices(mics);
    } catch {
      setMicDevices([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
    navigator.mediaDevices?.addEventListener("devicechange", refresh);
    return () => navigator.mediaDevices?.removeEventListener("devicechange", refresh);
  }, [refresh]);

  return { micDevices, refreshMicDevices: refresh };
}
